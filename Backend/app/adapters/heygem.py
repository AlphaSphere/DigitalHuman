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
        with httpx.Client(timeout=self.settings.model_http_timeout_seconds) as client:
            response = client.post(
                f"{self.settings.heygem_base_url}/generate",
                json={"audio_path": audio_path, "avatar_profile_id": avatar_profile_id},
            )
            response.raise_for_status()
            return response.json()["video_path"]
