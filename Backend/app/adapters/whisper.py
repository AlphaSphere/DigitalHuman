import json
import subprocess
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.services.script_parser import DEFAULT_SCRIPT
from app.services.storage_service import task_dir


class WhisperAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    def transcribe(self, source_video_path: str | None, task_id: str | None = None) -> list[dict]:
        if self.settings.use_stub_model_adapters:
            return [{"start_time": 0, "end_time": 6, "text": DEFAULT_SCRIPT, "confidence": 0.92}]
        if not source_video_path:
            raise ValueError("Whisper 识别需要 source_video_path")
        if self.settings.whisper_base_url:
            return self._transcribe_http(source_video_path)
        return self._transcribe_cli(source_video_path, task_id)

    def _transcribe_http(self, source_video_path: str) -> list[dict]:
        with httpx.Client(timeout=self.settings.model_http_timeout_seconds) as client:
            response = client.post(
                f"{self.settings.whisper_base_url}/transcribe",
                json={
                    "path": source_video_path,
                    "language": self.settings.whisper_language,
                    "model": self.settings.whisper_model,
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"Whisper 服务调用失败: {_response_detail(response)}") from exc
            payload = response.json()
            return self._normalize_segments(payload.get("segments", payload))

    def _transcribe_cli(self, source_video_path: str, task_id: str | None) -> list[dict]:
        output_dir = task_dir(task_id or "manual") / "intermediate"
        subprocess.run(
            [
                self.settings.whisper_command,
                source_video_path,
                "--model",
                self.settings.whisper_model,
                "--output_format",
                "json",
                "--output_dir",
                str(output_dir),
            ],
            check=True,
        )
        json_path = output_dir / f"{Path(source_video_path).stem}.json"
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        return self._normalize_segments(payload.get("segments", []))

    def _normalize_segments(self, segments: list[dict]) -> list[dict]:
        normalized = []
        for index, segment in enumerate(segments):
            text = segment.get("text") or segment.get("sentence") or ""
            if text.strip():
                normalized.append(
                    {
                        "start_time": float(segment.get("start", segment.get("start_time", index * 4))),
                        "end_time": float(segment.get("end", segment.get("end_time", index * 4 + 3.6))),
                        "text": text.strip(),
                        "confidence": segment.get("confidence"),
                    }
                )
        if not normalized:
            raise ValueError("Whisper 未返回可用文案")
        return normalized


def _response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text
    return str(payload.get("detail") or payload)
