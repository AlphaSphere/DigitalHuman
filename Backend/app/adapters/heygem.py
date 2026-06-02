import httpx

from app.core.config import get_settings
from app.domain.enums import GenerationVideoMode
from app.services.storage_service import touch_file


class HeyGemAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_avatar_video(
        self,
        task_id: str,
        audio_path: str,
        avatar_profile_id: str | None,
        generation_video_mode: str | None,
        custom_video_path: str | None,
    ) -> str:
        if generation_video_mode == GenerationVideoMode.uploaded_video.value and custom_video_path:
            return custom_video_path
        if self.settings.use_stub_model_adapters:
            return touch_file(task_id, "intermediate/avatar_video.mp4", b"stub avatar video")
        output_path = self.settings.storage_root / "tasks" / task_id / "intermediate" / "avatar_video.mp4"
        with httpx.Client(timeout=self.settings.model_http_timeout_seconds) as client:
            response = client.post(
                f"{self.settings.heygem_base_url}/generate",
                json={
                    "task_id": task_id,
                    "audio_path": audio_path,
                    "avatar_profile_id": avatar_profile_id,
                    "output_path": str(output_path),
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"HeyGem 服务调用失败: {_response_detail(response)}") from exc
            payload = response.json()
            video_path = payload.get("video_path") or payload.get("path") or payload.get("output_path")
            if not video_path:
                raise ValueError("HeyGem 未返回 video_path")
            return video_path


def _response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text
    return str(payload.get("detail") or payload)
