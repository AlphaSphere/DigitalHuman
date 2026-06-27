"""TuiliONNX 数字人桥接服务（本地 ONNX / HTTP 上游 / Stub）。"""

from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import AliasChoices, BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.onnx_inference import probe_audio_duration, render_avatar_video

app = FastAPI(title="DigitalHuman TuiliONNX Service")


class Settings(BaseSettings):
    tuilionnx_upstream_url: str | None = None
    tuilionnx_repo_path: Path | None = None
    tuilionnx_default_data_path: Path | None = None
    tuilionnx_avatar_profile_map: str | None = None
    tuilionnx_execution_provider: str = "auto"
    tuilionnx_timeout_seconds: float = 1800
    allow_stub_output: bool = Field(
        default=False,
        validation_alias=AliasChoices("ALLOW_STUB_OUTPUT", "ALLOW_MODEL_SERVICE_STUB_OUTPUT"),
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator(
        "tuilionnx_upstream_url",
        "tuilionnx_repo_path",
        "tuilionnx_default_data_path",
        "tuilionnx_avatar_profile_map",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value):
        return None if value == "" else value


class GenerateRequest(BaseModel):
    task_id: str = Field(..., min_length=1)
    audio_path: str = Field(..., min_length=1)
    avatar_profile_id: str | None = None
    output_path: str = Field(..., min_length=1)
    compress_inference: bool = False
    sync_offset: int = Field(default=0, ge=-10, le=10)
    inference_scale: float = Field(default=1.0, ge=0.5, le=1.0)


settings = Settings()
_profile_cache: dict[str, Path] | None = None


def _repo_configured() -> bool:
    repo = settings.tuilionnx_repo_path
    return bool(repo and Path(repo).exists() and (Path(repo) / "dihuman_run.py").exists())


def _resolve_mode() -> str:
    if settings.tuilionnx_upstream_url:
        return "upstream-http"
    if _repo_configured():
        return "local-onnx" if _local_onnx_ready() else "local-onnx-avatar-missing"
    if settings.allow_stub_output:
        return "stub"
    return "unconfigured"


def _local_onnx_ready() -> bool:
    repo = settings.tuilionnx_repo_path
    data = settings.tuilionnx_default_data_path
    if not repo or not data:
        return False
    repo = Path(repo)
    data = Path(data)
    return (
        (repo / "dihuman_run.py").exists()
        and (data / "unet.onnx").exists()
        and (data / "encoder.onnx").exists()
        and (data / "img_inference").exists()
        and (data / "lms_inference").exists()
    )


def _avatar_profile_map() -> dict[str, Path]:
    global _profile_cache
    if _profile_cache is not None:
        return _profile_cache
    mapping: dict[str, Path] = {}
    if settings.tuilionnx_avatar_profile_map:
        try:
            raw = json.loads(settings.tuilionnx_avatar_profile_map)
            if isinstance(raw, dict):
                mapping = {str(key): Path(str(value)) for key, value in raw.items()}
        except json.JSONDecodeError:
            pass
    if settings.tuilionnx_default_data_path:
        mapping.setdefault("default", Path(settings.tuilionnx_default_data_path))
    _profile_cache = mapping
    return mapping


def _resolve_data_path(avatar_profile_id: str | None) -> Path:
    mapping = _avatar_profile_map()
    if avatar_profile_id and avatar_profile_id in mapping:
        return mapping[avatar_profile_id]
    if settings.tuilionnx_default_data_path:
        return Path(settings.tuilionnx_default_data_path)
    raise HTTPException(status_code=400, detail="未配置 TuiliONNX 数字人素材路径")


@app.get("/health")
def health() -> dict:
    mode = _resolve_mode()
    payload = {"status": "ok", "service": "tuilionnx", "mode": mode}
    if _repo_configured():
        payload["execution_provider"] = settings.tuilionnx_execution_provider
        payload["avatar_ready"] = _local_onnx_ready()
        if settings.tuilionnx_default_data_path:
            payload["default_data_path"] = str(settings.tuilionnx_default_data_path)
    return payload


def _write_stub_video(output_path: Path, audio_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    duration = probe_audio_duration(audio_path)
    if ffmpeg:
        command = [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s=1080x1920:d={duration:.2f}",
            "-i",
            str(audio_path),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            if output_path.exists() and output_path.stat().st_size > 0:
                return
        except subprocess.CalledProcessError as exc:
            message = exc.stderr or exc.stdout or str(exc)
            raise HTTPException(status_code=503, detail=f"TuiliONNX 占位视频生成失败（需 ffmpeg）: {message}") from exc
    raise HTTPException(status_code=503, detail="TuiliONNX 未配置且本机未安装 ffmpeg，无法生成占位视频")


def _generate_upstream(payload: GenerateRequest) -> dict:
    assert settings.tuilionnx_upstream_url
    with httpx.Client(timeout=settings.tuilionnx_timeout_seconds, trust_env=False) as client:
        response = client.post(
            f"{settings.tuilionnx_upstream_url.rstrip('/')}/generate",
            json=payload.model_dump(),
        )
        response.raise_for_status()
        return response.json()


def _generate_local_onnx(payload: GenerateRequest) -> dict:
    repo_path = Path(settings.tuilionnx_repo_path or "")
    data_path = _resolve_data_path(payload.avatar_profile_id)
    audio_path = Path(payload.audio_path)
    output_path = Path(payload.output_path)
    if not audio_path.exists():
        raise HTTPException(status_code=400, detail=f"配音音频不存在: {payload.audio_path}")
    try:
        video_path, synced_audio_path = render_avatar_video(
            repo_path=repo_path,
            data_path=data_path,
            audio_path=audio_path,
            output_path=output_path,
            execution_provider=settings.tuilionnx_execution_provider,
            compress_inference=payload.compress_inference,
            sync_offset=payload.sync_offset,
            inference_scale=payload.inference_scale,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "video_path": str(video_path),
        "synced_audio_path": str(synced_audio_path),
        "status": "success",
    }


@app.post("/generate")
def generate(payload: GenerateRequest) -> dict:
    audio_path = Path(payload.audio_path)
    if not audio_path.exists():
        raise HTTPException(status_code=400, detail=f"配音音频不存在: {payload.audio_path}")
    output_path = Path(payload.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    mode = _resolve_mode()
    if mode == "upstream-http":
        try:
            return _generate_upstream(payload)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail=f"TuiliONNX 上游调用失败: {exc}") from exc
    if mode in {"local-onnx", "local-onnx-avatar-missing"}:
        if mode == "local-onnx-avatar-missing":
            raise HTTPException(
                status_code=503,
                detail=(
                    "TuiliONNX ONNX 已安装，但数字人素材未就绪。"
                    "请运行: python scripts/windows/setup_tuilionnx.py prepare --video 你的口播视频.mp4"
                ),
            )
        return _generate_local_onnx(payload)
    if mode == "stub":
        _write_stub_video(output_path, audio_path)
        return {"video_path": str(output_path), "status": "success"}
    raise HTTPException(
        status_code=503,
        detail="TuiliONNX 未配置：请运行 scripts/windows/安装TuiliONNX.bat 或设置 TUILIONNX_UPSTREAM_URL",
    )
