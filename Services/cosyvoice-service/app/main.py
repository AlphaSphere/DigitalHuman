"""CosyVoice 语音合成微服务入口。

用途：封装多种 TTS 调用方式（上游 HTTP、官方 FastAPI、本地模型、Shell 命令），
对外提供统一的 /synthesize 合成接口。
"""

import shlex
import subprocess
import wave
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
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
    cosyvoice_timeout_seconds: float = 600
    allow_stub_output: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator(
        "cosyvoice_upstream_url",
        "cosyvoice_command_template",
        "cosyvoice_model_dir",
        "cosyvoice_prompt_text",
        "cosyvoice_workdir",
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
    output_path: str = Field(..., min_length=1)


class SynthesizeResponse(BaseModel):
    """语音合成响应体。

    用途：返回生成音频在存储中的路径。
    """

    audio_path: str


settings = Settings()
app = FastAPI(title="DigitalHuman CosyVoice Service")
_local_model: Any | None = None


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
        mode = "unconfigured"
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
        # 仅供本地联调协议使用；真实生成时必须关闭并配置 CosyVoice 仓库命令或上游服务。
        output_path.write_bytes(b"stub cosyvoice audio")
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
        with httpx.Client(timeout=settings.cosyvoice_timeout_seconds) as client:
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
    endpoint, data, files = _official_fastapi_payload(payload)
    try:
        with httpx.Client(timeout=settings.cosyvoice_timeout_seconds) as client:
            response = client.post(
                f"{settings.cosyvoice_upstream_url.rstrip('/')}/{endpoint}",
                data=data,
                files=files,
            )
            response.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"CosyVoice 官方 FastAPI 调用失败: {exc}") from exc
    finally:
        for file_tuple in files.values():
            file_tuple[1].close()

    # 官方 FastAPI 返回的是 16-bit PCM 流，这里转成标准 WAV，方便后续 FFmpeg/HeyGem 读取。
    _write_pcm_wav(output_path, response.content, settings.cosyvoice_target_sample_rate)
    return SynthesizeResponse(audio_path=str(output_path))


def _official_fastapi_payload(payload: SynthesizeRequest):
    """构造官方 FastAPI 请求的 endpoint、表单字段与文件附件。

    用途：根据是否提供 custom_voice_path 与 prompt_text 选择推理模式。

    参数:
        payload: 合成请求体。

    返回:
        (endpoint 路径, form data 字典, files 字典) 三元组。

    逻辑:
        有自定义音色样本时优先 zero_shot（需 prompt_text）或 cross_lingual；
        否则走 SFT 预设说话人 inference_sft。
    """
    if payload.custom_voice_path:
        prompt_wav = Path(payload.custom_voice_path)
        if not prompt_wav.exists():
            raise HTTPException(status_code=400, detail=f"自定义音色样本不存在: {payload.custom_voice_path}")
        files = {"prompt_wav": ("prompt_wav", prompt_wav.open("rb"), "application/octet-stream")}
        if settings.cosyvoice_prompt_text:
            return "inference_zero_shot", {"tts_text": payload.text, "prompt_text": settings.cosyvoice_prompt_text}, files
        return "inference_cross_lingual", {"tts_text": payload.text}, files
    return "inference_sft", {"tts_text": payload.text, "spk_id": payload.voice_profile_id or settings.cosyvoice_sft_spk_id}, {}


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
            if settings.cosyvoice_prompt_text:
                model_output = model.inference_zero_shot(payload.text, settings.cosyvoice_prompt_text, str(prompt_wav))
            else:
                model_output = model.inference_cross_lingual(payload.text, str(prompt_wav))
        else:
            model_output = model.inference_sft(payload.text, payload.voice_profile_id or settings.cosyvoice_sft_spk_id)
        _save_model_output(model_output, output_path, model.sample_rate)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CosyVoice 本地模型推理失败: {exc}") from exc
    return SynthesizeResponse(audio_path=str(output_path))


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
