"""TuiliONNX 数字人 HTTP 桥接适配器。"""

from pathlib import Path

import httpx

from app.core.config import get_settings
from app.domain.enums import GenerationQuality
from app.services.storage_service import touch_file


class TuiliONNXAdapter:
    """TuiliONNX 数字人生成服务适配器。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_avatar_video(
        self,
        task_id: str,
        audio_path: str,
        avatar_profile_id: str | None,
        generation_video_mode: str | None,
        custom_video_path: str | None,
        generation_quality: str | None = GenerationQuality.full.value,
        sync_offset: int = 0,
    ) -> str:
        """生成数字人口播视频。"""
        if generation_video_mode == "uploaded_video" and custom_video_path:
            return custom_video_path

        if self.settings.use_stub_model_adapters:
            return touch_file(task_id, "intermediate/avatar_video.mp4", b"stub tuilionnx avatar video")

        output_path = self.settings.storage_root / "tasks" / task_id / "intermediate" / "avatar_video.mp4"
        is_fast = generation_quality == GenerationQuality.fast.value
        # trust_env=False：禁用系统代理，防止代理拦截本地服务请求
        with httpx.Client(timeout=self.settings.model_http_timeout_seconds, trust_env=False) as client:
            try:
                response = client.post(
                    f"{self.settings.tuilionnx_base_url.rstrip('/')}/generate",
                    json={
                        "task_id": task_id,
                        "audio_path": audio_path,
                        "avatar_profile_id": avatar_profile_id,
                        "output_path": str(output_path),
                        "compress_inference": is_fast,
                        "sync_offset": sync_offset,
                        "inference_scale": 0.85 if is_fast else 1.0,
                    },
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"TuiliONNX 服务调用失败: {_response_detail(response)}") from exc
            except httpx.RequestError as exc:
                raise RuntimeError(
                    f"TuiliONNX 服务不可达（{self.settings.tuilionnx_base_url}）。"
                    "请重启一键启动脚本以拉起 8004 端口服务，或在配置页改用 HeyGem 引擎。"
                ) from exc
            payload = response.json()
            video_path = payload.get("video_path") or payload.get("path") or str(output_path)
            resolved = Path(video_path)
            if not resolved.exists():
                raise RuntimeError(f"TuiliONNX 未生成有效视频文件: {video_path}")
            return str(resolved)


def _response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
        detail = payload.get("detail") or payload
        text = str(detail).strip()
        if text:
            return text
    except ValueError:
        pass
    text = (response.text or "").strip()
    if text:
        return text[:500]
    return f"HTTP {response.status_code}，无响应正文"
