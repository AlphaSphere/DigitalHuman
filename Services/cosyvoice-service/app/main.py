"""CosyVoice 语音合成微服务入口。

用途：封装多种 TTS 调用方式（上游 HTTP、官方 FastAPI、本地模型、Shell 命令），
对外提供统一的 /synthesize 合成接口。
"""

import shlex
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import AliasChoices, BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """CosyVoice 服务运行配置，从环境变量与 .env 文件加载。

    用途：控制上游地址、本地模型路径、命令模板、默认说话人与超时等参数。
    """

    cosyvoice_upstream_url: str | None = None
    cosyvoice_upstream_mode: str = "digitalhuman"
    cosyvoice_command_template: str | None = None
    cosyvoice_model_dir: str | None = None
    cosyvoice_sft_spk_id: str = "中文女"
    cosyvoice_prompt_text: str | None = None
    cosyvoice_target_sample_rate: int = 22050
    cosyvoice_workdir: Path | None = None
    cosyvoice_repo_path: Path | None = None
    cosyvoice_timeout_seconds: float = 600
    allow_stub_output: bool = Field(
        default=False,
        validation_alias=AliasChoices("ALLOW_STUB_OUTPUT", "ALLOW_MODEL_SERVICE_STUB_OUTPUT"),
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator(
        "cosyvoice_upstream_url",
        "cosyvoice_command_template",
        "cosyvoice_model_dir",
        "cosyvoice_prompt_text",
        "cosyvoice_workdir",
        "cosyvoice_repo_path",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value):
        """将空字符串规范化为 None。

        用途：允许通过空环境变量表示「未配置该项」。

        参数:
            value: 原始配置值。

        返回:
            非空字符串原样返回，空字符串转为 None。

        逻辑:
            在 Pydantic 校验前执行，便于下游分支判断使用哪种合成模式。
        """
        return None if value == "" else value


class SynthesizeRequest(BaseModel):
    """语音合成请求体。

    用途：描述任务 ID、待合成文本、音色配置与输出路径。
    """

    task_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    voice_profile_id: str | None = None
    custom_voice_path: str | None = None
    custom_voice_prompt_text: str | None = None
    output_path: str = Field(..., min_length=1)


class SynthesizeResponse(BaseModel):
    """语音合成响应体。

    用途：返回生成音频在存储中的路径。
    """

    audio_path: str


VOICE_PROFILE_SPK_MAP = {
    "voice_default_female": "中文女",
    "voice_default_male": "中文男",
}


def _resolve_spk_id(voice_profile_id: str | None) -> str:
    """将业务音色 ID 映射为 CosyVoice 官方 SFT 说话人 ID。"""
    if not voice_profile_id:
        return settings.cosyvoice_sft_spk_id
    return VOICE_PROFILE_SPK_MAP.get(voice_profile_id, voice_profile_id)


def _write_stub_wav(path: Path, sample_rate: int = 22050, duration_seconds: float = 2.0) -> None:
    """写入短静音 WAV，供本地无 GPU 时跑通 FFmpeg / HeyGem 链路。"""
    frame_count = int(sample_rate * duration_seconds)
    _write_pcm_wav(path, b"\x00\x00" * frame_count, sample_rate)


settings = Settings()
app = FastAPI(title="DigitalHuman CosyVoice Service")
_local_model: Any | None = None
# 克隆音色样本转 16k WAV 结果缓存，避免每段分段合成都跑 ffmpeg
_prompt_wav_cache: dict[str, tuple[Path, bool]] = {}


@app.get("/health")
def health() -> dict:
    """健康检查端点。

    用途：供编排系统探测服务状态及当前合成模式。

    返回:
        包含 status、service 名称与 mode（upstream-http/local-model/command/unconfigured）的字典。

    逻辑:
        按配置优先级推断当前生效的合成后端，不实际调用模型。
    """
    mode = "upstream-http" if settings.cosyvoice_upstream_url else "local-model"
    if not settings.cosyvoice_upstream_url and not settings.cosyvoice_model_dir:
        mode = "command"
    if not settings.cosyvoice_upstream_url and not settings.cosyvoice_model_dir and not settings.cosyvoice_command_template:
        mode = "stub" if settings.allow_stub_output else "unconfigured"
    return {"status": "ok", "service": "cosyvoice", "mode": mode}


@app.post("/synthesize", response_model=SynthesizeResponse)
def synthesize(payload: SynthesizeRequest) -> SynthesizeResponse:
    """将文本合成为语音并写入指定路径。

    用途：主业务入口，按配置自动选择上游/本地/命令/stub 合成方式。

    参数:
        payload: 包含文本、音色与输出路径的合成请求。

    返回:
        含 audio_path 的 SynthesizeResponse。

    逻辑:
        1. 确保输出目录存在；
        2. 按 upstream → local_model → command → stub 优先级路由；
        3. 均未配置且未允许 stub 时返回 503。
    """
    output_path = Path(payload.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if settings.cosyvoice_upstream_url:
        return _synthesize_upstream(payload)
    if settings.cosyvoice_model_dir:
        return _synthesize_local_model(payload, output_path)
    if settings.cosyvoice_command_template:
        return _synthesize_command(payload, output_path)
    if settings.allow_stub_output:
        # 本地无 CosyVoice 上游时写入标准静音 WAV，便于后续 FFmpeg/HeyGem 继续处理。
        _write_stub_wav(output_path, settings.cosyvoice_target_sample_rate)
        return SynthesizeResponse(audio_path=str(output_path))
    raise HTTPException(status_code=503, detail="CosyVoice 服务未配置：请设置 COSYVOICE_COMMAND_TEMPLATE 或 COSYVOICE_UPSTREAM_URL")


def _synthesize_upstream(payload: SynthesizeRequest) -> SynthesizeResponse:
    """通过 HTTP 上游服务执行语音合成。

    用途：将合成请求转发至外部 CosyVoice 或 DigitalHuman 兼容上游。

    参数:
        payload: 合成请求体。

    返回:
        上游返回的 audio_path 封装为 SynthesizeResponse。

    逻辑:
        official_fastapi 模式走专用 multipart 流程；否则 POST JSON 到 /synthesize 并解析路径字段。
    """
    assert settings.cosyvoice_upstream_url
    if settings.cosyvoice_upstream_mode == "official_fastapi":
        return _synthesize_official_fastapi(payload)
    try:
        with httpx.Client(timeout=settings.cosyvoice_timeout_seconds, trust_env=False) as client:
            response = client.post(f"{settings.cosyvoice_upstream_url.rstrip('/')}/synthesize", json=payload.model_dump())
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"CosyVoice 上游调用失败: {exc}") from exc
    audio_path = data.get("audio_path") or data.get("path") or data.get("output_path")
    if not audio_path:
        raise HTTPException(status_code=502, detail="CosyVoice 上游未返回 audio_path")
    return SynthesizeResponse(audio_path=audio_path)


def _synthesize_official_fastapi(payload: SynthesizeRequest) -> SynthesizeResponse:
    """调用 CosyVoice 官方 FastAPI 推理端点。

    用途：对接官方 zero_shot / cross_lingual / sft 三类接口，并将 PCM 转为 WAV。

    参数:
        payload: 合成请求体。

    返回:
        写入本地 WAV 后的 SynthesizeResponse。

    逻辑:
        1. 构造 endpoint、form data 与可选 prompt_wav 文件；
        2. POST 上游并读取 PCM 字节流；
        3. finally 中关闭已打开的文件句柄；
        4. 调用 _write_pcm_wav 落盘。
    """
    output_path = Path(payload.output_path)
    endpoint, data, files, temp_paths = _official_fastapi_payload(payload)
    pcm_bytes = b""
    try:
        # trust_env=False：禁用系统 HTTP 代理，避免代理拦截本地服务请求返回 403
        # 使用 stream() 模式逐块读取 PCM 音频流，避免 CosyVoice 官方 FastAPI 的
        # StreamingResponse 在 chunked transfer 末尾提前关闭连接时 httpx 报错。
        with httpx.Client(timeout=settings.cosyvoice_timeout_seconds, trust_env=False) as client:
            url = f"{settings.cosyvoice_upstream_url.rstrip('/')}/{endpoint}"
            if files:
                req_kwargs = {"data": data, "files": files}
            else:
                req_kwargs = {"data": data}

            with client.stream("POST", url, **req_kwargs) as response:
                if response.status_code >= 400:
                    response.read()  # 读取错误详情
                    raise httpx.HTTPStatusError(
                        message=f"Server error '{response.status_code}'",
                        request=response.request,
                        response=response,
                    )
                for chunk in response.iter_bytes():
                    pcm_bytes += chunk
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"CosyVoice 官方 FastAPI 调用失败: {exc}") from exc
    except Exception as exc:
        if pcm_bytes:
            # 连接提前关闭但已接收到部分数据，仍可继续写入 WAV
            pass
        else:
            raise HTTPException(status_code=502, detail=f"CosyVoice 官方 FastAPI 调用失败: {exc}") from exc
    finally:
        for file_tuple in files.values():
            file_tuple[1].close()
        # 清理 ffmpeg 转码产生的临时 WAV 文件
        for tmp_path in temp_paths:
            tmp_path.unlink(missing_ok=True)

    # 官方 FastAPI 返回的是 16-bit PCM 流，这里转成标准 WAV，方便后续 FFmpeg/HeyGem 读取。
    _write_pcm_wav(output_path, pcm_bytes, settings.cosyvoice_target_sample_rate)
    return SynthesizeResponse(audio_path=str(output_path))


def _convert_to_wav_16k(src: Path) -> tuple[Path, bool]:
    """将音频文件转换为 CosyVoice 所需的 16kHz 单声道 WAV 格式。

    用途：CosyVoice 官方 FastAPI 使用 soundfile 加载音色样本，soundfile 不支持 MP3/AAC
    等有损格式，且要求 16kHz 单声道。通过 ffmpeg 统一转换，避免上游 500 错误。

    参数:
        src: 原始音频文件路径。

    返回:
        (wav_path, is_temp) 元组：
          - wav_path: 可用的 16kHz WAV 路径（若已符合则为原路径）；
          - is_temp: True 表示 wav_path 是临时文件，调用方需在用完后删除。

    逻辑:
        1. 已是 WAV 则先探测采样率，符合则直接返回原路径；
        2. 否则用 ffmpeg 转为 16kHz 单声道 WAV 临时文件。
    """
    suffix = src.suffix.lower()

    # 尝试探测现有 WAV 是否已是 16kHz 单声道且不超过 5 秒（可直接使用）
    if suffix == ".wav":
        try:
            with wave.open(str(src), "rb") as wf:
                duration = wf.getnframes() / wf.getframerate()
                if wf.getframerate() == 16000 and wf.getnchannels() == 1 and duration <= 5.0:
                    return src, False
        except Exception:
            pass  # 损坏或非标准 WAV，交给 ffmpeg 重新转换

    # 用 ffmpeg 转为 16kHz 单声道 WAV 临时文件
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-t", "5",        # 截取前 5 秒，降低 zero-shot/cross_lingual 前处理负担
        "-ar", "16000",   # 采样率 16kHz
        "-ac", "1",       # 单声道
        "-sample_fmt", "s16",
        str(tmp_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            tmp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail=f"音色样本转码失败（需安装 ffmpeg）: {result.stderr[-300:]}",
            )
    except FileNotFoundError:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="ffmpeg 未安装，无法转换音色样本格式")
    except subprocess.TimeoutExpired:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="音色样本转码超时")

    return tmp_path, True


def _official_fastapi_payload(payload: SynthesizeRequest) -> tuple:
    """构造官方 FastAPI 请求的 endpoint、表单字段、文件附件与临时文件列表。

    用途：根据是否提供 custom_voice_path 与 prompt_text 选择推理模式。

    参数:
        payload: 合成请求体。

    返回:
        (endpoint 路径, form data 字典, files 字典, temp_paths 列表) 四元组。
        temp_paths 为需要在请求结束后删除的临时文件路径列表。

    逻辑:
        有自定义音色样本时先转为 16kHz WAV，再优先 zero_shot（需 prompt_text）
        或 cross_lingual；否则走 SFT 预设说话人 inference_sft。
    """
    if payload.custom_voice_path:
        src_path = Path(payload.custom_voice_path)
        if not src_path.exists():
            raise HTTPException(status_code=400, detail=f"自定义音色样本不存在: {payload.custom_voice_path}")

        # 确保上传给 CosyVoice 的是 16kHz WAV，soundfile 才能正确解析（同文件复用缓存）
        cache_key = f"{src_path.resolve()}:{src_path.stat().st_mtime_ns}"
        cached = _prompt_wav_cache.get(cache_key)
        if cached:
            wav_path, is_temp = cached
            temp_paths = []
        else:
            wav_path, is_temp = _convert_to_wav_16k(src_path)
            _prompt_wav_cache[cache_key] = (wav_path, is_temp)
            temp_paths = []  # 缓存供多段配音复用，不在 finally 删除

        files = {"prompt_wav": ("prompt_wav.wav", wav_path.open("rb"), "audio/wav")}
        prompt_text = (payload.custom_voice_prompt_text or settings.cosyvoice_prompt_text or "").strip()
        if prompt_text:
            return "inference_zero_shot", {"tts_text": payload.text, "prompt_text": prompt_text}, files, temp_paths
        return "inference_cross_lingual", {"tts_text": payload.text}, files, temp_paths
    return "inference_sft", {"tts_text": payload.text, "spk_id": _resolve_spk_id(payload.voice_profile_id)}, {}, []


def _synthesize_local_model(payload: SynthesizeRequest, output_path: Path) -> SynthesizeResponse:
    """使用进程内加载的 CosyVoice 本地模型推理。

    用途：在无上游 HTTP 时直接调用 cosyvoice Python SDK 生成音频。

    参数:
        payload: 合成请求体。
        output_path: 音频输出路径。

    返回:
        本地保存后的 SynthesizeResponse。

    逻辑:
        按 custom_voice_path 是否存在选择 zero_shot/cross_lingual/sft；
        调用 _save_model_output 将 tensor 片段拼接并写入文件。
    """
    model = _load_local_model()
    try:
        if payload.custom_voice_path:
            prompt_wav = Path(payload.custom_voice_path)
            if not prompt_wav.exists():
                raise HTTPException(status_code=400, detail=f"自定义音色样本不存在: {payload.custom_voice_path}")
            prompt_text = (payload.custom_voice_prompt_text or settings.cosyvoice_prompt_text or "").strip()
            if prompt_text:
                model_output = model.inference_zero_shot(payload.text, prompt_text, str(prompt_wav))
            else:
                model_output = model.inference_cross_lingual(payload.text, str(prompt_wav))
        else:
            model_output = model.inference_sft(payload.text, _resolve_spk_id(payload.voice_profile_id))
        _save_model_output(model_output, output_path, model.sample_rate)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CosyVoice 本地模型推理失败: {exc}") from exc
    return SynthesizeResponse(audio_path=str(output_path))


def _ensure_cosyvoice_repo_on_path() -> None:
    """将 CosyVoice 源码目录加入 sys.path，便于本地 AutoModel 加载。"""
    repo_path = settings.cosyvoice_repo_path
    if not repo_path:
        return
    repo = Path(repo_path).resolve()
    if not repo.exists():
        return
    for candidate in (repo, repo / "third_party" / "Matcha-TTS"):
        candidate_str = str(candidate)
        if candidate.exists() and candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)


def _load_local_model():
    """懒加载并缓存 CosyVoice AutoModel 实例。

    用途：首次本地推理时加载模型，后续请求复用同一实例。

    返回:
        已初始化的 CosyVoice AutoModel。

    逻辑:
        全局 _local_model 非空则直接返回；否则 import AutoModel 并按 model_dir 构造。
    """
    global _local_model
    if _local_model is not None:
        return _local_model
    _ensure_cosyvoice_repo_on_path()
    try:
        from cosyvoice.cli.cosyvoice import AutoModel
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="未安装 CosyVoice Python 依赖，请使用官方 runtime 镜像或配置 COSYVOICE_UPSTREAM_URL",
        ) from exc
    _local_model = AutoModel(model_dir=settings.cosyvoice_model_dir)
    return _local_model


def _save_model_output(model_output, output_path: Path, sample_rate: int) -> None:
    """将模型推理输出的 tensor 片段拼接并保存为音频文件。

    用途：统一本地推理结果的落盘格式。

    参数:
        model_output: 模型返回的可迭代结果，每项含 tts_speech tensor。
        output_path: 目标音频路径。
        sample_rate: 采样率，传给 torchaudio.save。

    逻辑:
        提取各 chunk 的 tts_speech，torch.cat 拼接后写入 output_path；空结果抛 500。
    """
    try:
        import torch
        import torchaudio
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="本地 CosyVoice 推理需要安装 torch 和 torchaudio") from exc

    chunks = [item["tts_speech"] for item in model_output]
    if not chunks:
        raise HTTPException(status_code=500, detail="CosyVoice 本地模型未返回音频")
    audio = torch.cat(chunks, dim=-1)
    torchaudio.save(str(output_path), audio, sample_rate)


def _synthesize_command(payload: SynthesizeRequest, output_path: Path) -> SynthesizeResponse:
    """通过 Shell 命令模板调用外部 CosyVoice 脚本。

    用途：对接官方仓库 CLI 或自定义合成脚本。

    参数:
        payload: 合成请求体。
        output_path: 音频输出路径。

    返回:
        命令成功且文件存在时的 SynthesizeResponse。

    逻辑:
        1. 将文本写入同目录 .txt 临时文件；
        2. format 命令模板并 subprocess.run；
        3. 校验 output_path 是否生成。
    """
    text_path = output_path.with_suffix(".txt")
    text_path.write_text(payload.text, encoding="utf-8")
    values = {
        "task_id": payload.task_id,
        "text_file": str(text_path),
        "output_path": str(output_path),
        "voice_profile_id": payload.voice_profile_id or "",
        "custom_voice_path": payload.custom_voice_path or "",
        "custom_voice_prompt_text": payload.custom_voice_prompt_text or "",
    }
    command = settings.cosyvoice_command_template.format(**values)
    try:
        subprocess.run(
            shlex.split(command),
            cwd=str(settings.cosyvoice_workdir) if settings.cosyvoice_workdir else None,
            check=True,
            capture_output=True,
            text=True,
            timeout=settings.cosyvoice_timeout_seconds,
        )
    except subprocess.CalledProcessError as exc:
        message = exc.stderr or exc.stdout or str(exc)
        raise HTTPException(status_code=500, detail=f"CosyVoice 命令执行失败: {message}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CosyVoice 命令启动失败: {exc}") from exc
    if not output_path.exists():
        raise HTTPException(status_code=500, detail=f"CosyVoice 命令未生成音频: {output_path}")
    return SynthesizeResponse(audio_path=str(output_path))


def _write_pcm_wav(path: Path, pcm: bytes, sample_rate: int) -> None:
    """将 16-bit 单声道 PCM 字节流写入标准 WAV 文件。

    用途：适配官方 FastAPI 返回的裸 PCM，供 FFmpeg/HeyGem 读取。

    参数:
        path: 目标 WAV 路径。
        pcm: 原始 PCM 字节。
        sample_rate: 采样率（Hz）。

    逻辑:
        空 pcm 抛 502；使用 wave 模块写入 mono 16-bit WAV。
    """
    if not pcm:
        raise HTTPException(status_code=502, detail="CosyVoice 官方 FastAPI 返回空音频")
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
