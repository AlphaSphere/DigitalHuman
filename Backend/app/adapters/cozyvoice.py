import httpx

from app.core.config import get_settings
from app.services.storage_service import touch_file


class CozyVoiceAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    def synthesize(self, task_id: str, script: str, voice_profile_id: str | None, custom_voice_path: str | None) -> str:
        if self.settings.use_stub_model_adapters:
            return touch_file(task_id, "intermediate/tts_audio.wav", b"stub tts audio")
        output_path = self.settings.storage_root / "tasks" / task_id / "intermediate" / "tts_audio.wav"
        with httpx.Client(timeout=self.settings.model_http_timeout_seconds) as client:
            response = client.post(
                f"{self.settings.cozyvoice_base_url}/synthesize",
                json={
                    "task_id": task_id,
                    "text": script,
                    "script": script,
                    "voice_profile_id": voice_profile_id,
                    "custom_voice_path": custom_voice_path,
                    "output_path": str(output_path),
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"CosyVoice 服务调用失败: {_response_detail(response)}") from exc
            payload = response.json()
            audio_path = payload.get("audio_path") or payload.get("path") or payload.get("output_path")
            if not audio_path:
                raise ValueError("CosyVoice 未返回 audio_path")
            return audio_path


def _response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text
    return str(payload.get("detail") or payload)
