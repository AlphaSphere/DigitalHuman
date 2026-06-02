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
        return None if value == "" else value


class SynthesizeRequest(BaseModel):
    task_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    voice_profile_id: str | None = None
    custom_voice_path: str | None = None
    output_path: str = Field(..., min_length=1)


class SynthesizeResponse(BaseModel):
    audio_path: str


settings = Settings()
app = FastAPI(title="DigitalHuman CosyVoice Service")
_local_model: Any | None = None


@app.get("/health")
def health() -> dict:
    mode = "upstream-http" if settings.cosyvoice_upstream_url else "local-model"
    if not settings.cosyvoice_upstream_url and not settings.cosyvoice_model_dir:
        mode = "command"
    if not settings.cosyvoice_upstream_url and not settings.cosyvoice_model_dir and not settings.cosyvoice_command_template:
        mode = "unconfigured"
    return {"status": "ok", "service": "cosyvoice", "mode": mode}


@app.post("/synthesize", response_model=SynthesizeResponse)
def synthesize(payload: SynthesizeRequest) -> SynthesizeResponse:
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
    if not pcm:
        raise HTTPException(status_code=502, detail="CosyVoice 官方 FastAPI 返回空音频")
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
