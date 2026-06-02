from pathlib import Path
from typing import Any

import whisper
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    whisper_model: str = "base"
    whisper_device: str | None = None
    whisper_language: str | None = None
    storage_root: Path = Path("/app/storage")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("whisper_device", "whisper_language", mode="before")
    @classmethod
    def empty_string_to_none(cls, value):
        return None if value == "" else value


class TranscribeRequest(BaseModel):
    path: str = Field(..., min_length=1)
    language: str | None = None
    model: str | None = None


class Segment(BaseModel):
    start_time: float
    end_time: float
    text: str
    confidence: float | None = None


class TranscribeResponse(BaseModel):
    segments: list[Segment]


settings = Settings()
app = FastAPI(title="DigitalHuman Whisper Service")
_model_cache: dict[str, Any] = {}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "whisper", "model": settings.whisper_model}


@app.post("/transcribe", response_model=TranscribeResponse)
def transcribe(payload: TranscribeRequest) -> TranscribeResponse:
    media_path = Path(payload.path)
    if not media_path.exists():
        raise HTTPException(status_code=400, detail=f"音视频文件不存在: {payload.path}")

    model_name = payload.model or settings.whisper_model
    try:
        model = _load_model(model_name)
        result = model.transcribe(
            str(media_path),
            language=payload.language or settings.whisper_language,
            fp16=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Whisper 识别失败: {exc}") from exc

    segments = [_normalize_segment(index, segment) for index, segment in enumerate(result.get("segments", []))]
    segments = [segment for segment in segments if segment.text]
    if not segments:
        raise HTTPException(status_code=422, detail="Whisper 未返回可用文案")
    return TranscribeResponse(segments=segments)


def _load_model(model_name: str) -> Any:
    if model_name not in _model_cache:
        # 模型常驻进程缓存，避免每次识别都重复加载大模型。
        _model_cache[model_name] = whisper.load_model(model_name, device=settings.whisper_device)
    return _model_cache[model_name]


def _normalize_segment(index: int, segment: dict) -> Segment:
    start = float(segment.get("start", index * 4))
    end = float(segment.get("end", start + 4))
    text = str(segment.get("text", "")).strip()
    no_speech_prob = segment.get("no_speech_prob")
    confidence = None if no_speech_prob is None else max(0.0, min(1.0, 1 - float(no_speech_prob)))
    return Segment(start_time=start, end_time=end, text=text, confidence=confidence)
