import json
import shlex
import shutil
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    heygem_upstream_url: str | None = None
    heygem_video_base_url: str | None = None
    heygem_command_template: str | None = None
    heygem_default_video_path: str | None = None
    heygem_avatar_profile_map: str | None = None
    heygem_result_dir: Path | None = None
    heygem_poll_interval_seconds: float = 5
    heygem_poll_timeout_seconds: float = 1800
    heygem_workdir: Path | None = None
    heygem_timeout_seconds: float = 1800
    allow_stub_output: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator(
        "heygem_upstream_url",
        "heygem_video_base_url",
        "heygem_command_template",
        "heygem_default_video_path",
        "heygem_avatar_profile_map",
        "heygem_result_dir",
        "heygem_workdir",
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


class GenerateResponse(BaseModel):
    video_path: str


settings = Settings()
app = FastAPI(title="DigitalHuman HeyGem Service")


@app.get("/health")
def health() -> dict:
    mode = "official-video-api" if settings.heygem_video_base_url else "upstream-http"
    if not settings.heygem_video_base_url and not settings.heygem_upstream_url:
        mode = "command"
    if not settings.heygem_video_base_url and not settings.heygem_upstream_url and not settings.heygem_command_template:
        mode = "unconfigured"
    return {"status": "ok", "service": "heygem", "mode": mode}


@app.post("/generate", response_model=GenerateResponse)
def generate(payload: GenerateRequest) -> GenerateResponse:
    audio_path = Path(payload.audio_path)
    if not audio_path.exists():
        raise HTTPException(status_code=400, detail=f"配音音频不存在: {payload.audio_path}")

    output_path = Path(payload.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if settings.heygem_video_base_url:
        return _generate_official_video(payload, output_path)
    if settings.heygem_upstream_url:
        return _generate_upstream(payload)
    if settings.heygem_command_template:
        return _generate_command(payload, output_path)
    if settings.allow_stub_output:
        # 仅供本地联调协议使用；真实生成时必须关闭并配置 HeyGem 仓库命令或上游服务。
        output_path.write_bytes(b"stub heygem video")
        return GenerateResponse(video_path=str(output_path))
    raise HTTPException(status_code=503, detail="HeyGem 服务未配置：请设置 HEYGEM_COMMAND_TEMPLATE 或 HEYGEM_UPSTREAM_URL")


def _generate_upstream(payload: GenerateRequest) -> GenerateResponse:
    assert settings.heygem_upstream_url
    try:
        with httpx.Client(timeout=settings.heygem_timeout_seconds) as client:
            response = client.post(f"{settings.heygem_upstream_url.rstrip('/')}/generate", json=payload.model_dump())
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HeyGem 上游调用失败: {exc}") from exc
    video_path = data.get("video_path") or data.get("path") or data.get("output_path")
    if not video_path:
        raise HTTPException(status_code=502, detail="HeyGem 上游未返回 video_path")
    return GenerateResponse(video_path=video_path)


def _generate_official_video(payload: GenerateRequest, output_path: Path) -> GenerateResponse:
    video_path = _resolve_avatar_video_path(payload.avatar_profile_id)
    if not video_path:
        raise HTTPException(
            status_code=400,
            detail="HeyGem 官方视频合成需要 avatar_profile_id 指向视频路径，或配置 HEYGEM_DEFAULT_VIDEO_PATH",
        )

    task_code = uuid4().hex
    submit_payload = {
        "audio_url": payload.audio_path,
        "video_url": video_path,
        "code": task_code,
        "chaofen": 0,
        "watermark_switch": 0,
        "pn": 1,
    }
    try:
        with httpx.Client(timeout=settings.heygem_timeout_seconds) as client:
            submit_response = client.post(
                f"{settings.heygem_video_base_url.rstrip('/')}/easy/submit",
                json=submit_payload,
            )
            submit_response.raise_for_status()
            submit_data = _json_or_text(submit_response)
            query_data = _poll_official_video(client, task_code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HeyGem 官方视频合成调用失败: {exc}") from exc

    resolved = _extract_video_path(query_data) or _extract_video_path(submit_data) or _find_result_file(task_code)
    if not resolved:
        raise HTTPException(status_code=502, detail=f"HeyGem 合成完成但未找到输出视频: {query_data}")
    return GenerateResponse(video_path=_copy_or_return_video(resolved, output_path))


def _poll_official_video(client: httpx.Client, task_code: str):
    deadline = time.monotonic() + settings.heygem_poll_timeout_seconds
    last_payload = None
    while time.monotonic() < deadline:
        response = client.get(f"{settings.heygem_video_base_url.rstrip('/')}/easy/query", params={"code": task_code})
        response.raise_for_status()
        payload = _json_or_text(response)
        last_payload = payload
        if _is_failed(payload):
            raise RuntimeError(f"HeyGem 任务失败: {payload}")
        if _is_finished(payload):
            return payload
        time.sleep(settings.heygem_poll_interval_seconds)
    raise TimeoutError(f"HeyGem 任务超时，最后状态: {last_payload}")


def _resolve_avatar_video_path(avatar_profile_id: str | None) -> str | None:
    if avatar_profile_id and Path(avatar_profile_id).exists():
        return avatar_profile_id
    mapped_path = _avatar_profile_map().get(avatar_profile_id or "")
    if mapped_path and Path(mapped_path).exists():
        return mapped_path
    if settings.heygem_default_video_path and Path(settings.heygem_default_video_path).exists():
        return settings.heygem_default_video_path
    return None


def _avatar_profile_map() -> dict[str, str]:
    if not settings.heygem_avatar_profile_map:
        return {}
    try:
        value = json.loads(settings.heygem_avatar_profile_map)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"HEYGEM_AVATAR_PROFILE_MAP 不是合法 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=500, detail="HEYGEM_AVATAR_PROFILE_MAP 必须是对象，例如 {\"avatar_studio_a\":\"/path/a.mp4\"}")
    return {str(key): str(path) for key, path in value.items()}


def _generate_command(payload: GenerateRequest, output_path: Path) -> GenerateResponse:
    values = {
        "task_id": payload.task_id,
        "audio_path": payload.audio_path,
        "output_path": str(output_path),
        "avatar_profile_id": payload.avatar_profile_id or "",
    }
    command = settings.heygem_command_template.format(**values)
    try:
        subprocess.run(
            shlex.split(command),
            cwd=str(settings.heygem_workdir) if settings.heygem_workdir else None,
            check=True,
            capture_output=True,
            text=True,
            timeout=settings.heygem_timeout_seconds,
        )
    except subprocess.CalledProcessError as exc:
        message = exc.stderr or exc.stdout or str(exc)
        raise HTTPException(status_code=500, detail=f"HeyGem 命令执行失败: {message}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"HeyGem 命令启动失败: {exc}") from exc
    if not output_path.exists():
        raise HTTPException(status_code=500, detail=f"HeyGem 命令未生成视频: {output_path}")
    return GenerateResponse(video_path=str(output_path))


def _json_or_text(response: httpx.Response):
    try:
        return response.json()
    except ValueError:
        return {"text": response.text}


def _is_finished(payload) -> bool:
    values = _flatten_values(payload)
    success_markers = {"success", "succeeded", "complete", "completed", "finish", "finished", "done", "2", 2}
    return any(value in success_markers for value in values)


def _is_failed(payload) -> bool:
    values = _flatten_values(payload)
    failed_markers = {"fail", "failed", "error", "exception", "-1", -1}
    return any(value in failed_markers for value in values)


def _flatten_values(payload) -> list:
    if isinstance(payload, Mapping):
        values = []
        for value in payload.values():
            values.extend(_flatten_values(value))
        return values
    if isinstance(payload, list):
        values = []
        for item in payload:
            values.extend(_flatten_values(item))
        return values
    if isinstance(payload, str):
        return [payload.lower()]
    return [payload]


def _extract_video_path(payload) -> str | None:
    if isinstance(payload, Mapping):
        for key in ("video_path", "video_url", "output_path", "result_path", "path", "url"):
            value = payload.get(key)
            if isinstance(value, str) and _looks_like_video(value):
                return value
        for value in payload.values():
            found = _extract_video_path(value)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _extract_video_path(item)
            if found:
                return found
    if isinstance(payload, str) and _looks_like_video(payload):
        return payload
    return None


def _looks_like_video(value: str) -> bool:
    return value.lower().endswith((".mp4", ".mov", ".mkv", ".avi"))


def _find_result_file(task_code: str) -> str | None:
    if not settings.heygem_result_dir or not settings.heygem_result_dir.exists():
        return None
    candidates = sorted(
        settings.heygem_result_dir.rglob(f"*{task_code}*.mp4"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return str(candidates[0]) if candidates else None


def _copy_or_return_video(source: str, output_path: Path) -> str:
    source_path = Path(source)
    if source_path.exists():
        if source_path.resolve() != output_path.resolve():
            shutil.copyfile(source_path, output_path)
        return str(output_path)
    return source
