import httpx

from app.core.config import get_settings
from app.services.script_parser import DEFAULT_SCRIPT


class WhisperAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    def transcribe(self, source_video_path: str | None) -> list[dict]:
        if self.settings.use_stub_model_adapters:
            return [{"start_time": 0, "end_time": 6, "text": DEFAULT_SCRIPT, "confidence": 0.92}]
        with httpx.Client(timeout=self.settings.model_http_timeout_seconds) as client:
            response = client.post(f"{self.settings.whisper_base_url}/transcribe", json={"path": source_video_path})
            response.raise_for_status()
            return response.json()["segments"]
