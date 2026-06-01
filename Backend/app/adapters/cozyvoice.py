import httpx

from app.core.config import get_settings
from app.services.storage_service import touch_file


class CozyVoiceAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    def synthesize(self, task_id: str, script: str, voice_profile_id: str | None, custom_voice_path: str | None) -> str:
        if self.settings.use_stub_model_adapters:
            return touch_file(task_id, "intermediate/tts_audio.wav", b"stub tts audio")
        with httpx.Client(timeout=self.settings.model_http_timeout_seconds) as client:
            response = client.post(
                f"{self.settings.cozyvoice_base_url}/synthesize",
                json={"script": script, "voice_profile_id": voice_profile_id, "custom_voice_path": custom_voice_path},
            )
            response.raise_for_status()
            return response.json()["audio_path"]
