"""Whisper 语音识别微服务入口。

用途：封装 OpenAI Whisper 模型，对外提供健康检查与音视频转写 HTTP API。
"""

from pathlib import Path
from typing import Any

import whisper
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Whisper 服务运行配置，从环境变量与 .env 文件加载。

    用途：集中管理模型名称、推理设备、默认语言与存储根目录。
    """

    whisper_model: str = "base"
    whisper_device: str | None = None
    whisper_language: str | None = None
    storage_root: Path = Path("/app/storage")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("whisper_device", "whisper_language", mode="before")
    @classmethod
    def empty_string_to_none(cls, value):
        """将空字符串规范化为 None。

        用途：允许通过空环境变量表示「使用 Whisper 默认行为」。

        参数:
            value: 原始配置值。

        返回:
            非空字符串原样返回，空字符串转为 None。

        逻辑:
            在 Pydantic 校验前执行，避免 "" 与 None 语义混淆。
        """
        return None if value == "" else value


class TranscribeRequest(BaseModel):
    """转写请求体。

    用途：描述待识别媒体路径及可选的模型/语言覆盖参数。
    """

    path: str = Field(..., min_length=1)
    language: str | None = None
    model: str | None = None


class Segment(BaseModel):
    """单段识别结果。

    用途：统一对外返回的时间轴片段结构，含起止时间与可选置信度。
    """

    start_time: float
    end_time: float
    text: str
    confidence: float | None = None


class TranscribeResponse(BaseModel):
    """转写响应体。

    用途：包装识别后的全部有效片段列表。
    """

    segments: list[Segment]


settings = Settings()
app = FastAPI(title="DigitalHuman Whisper Service")
_model_cache: dict[str, Any] = {}


@app.get("/health")
def health() -> dict:
    """健康检查端点。

    用途：供编排系统或负载均衡探测服务是否存活。

    返回:
        包含 status、service 名称与当前默认模型的字典。

    逻辑:
        不加载模型，仅返回静态配置信息。
    """
    return {"status": "ok", "service": "whisper", "model": settings.whisper_model}


@app.post("/transcribe", response_model=TranscribeResponse)
def transcribe(payload: TranscribeRequest) -> TranscribeResponse:
    """对指定音视频文件执行 Whisper 语音识别。

    用途：主业务入口，将媒体文件转为带时间轴的文本片段。

    参数:
        payload: 包含媒体路径及可选 language/model 的请求体。

    返回:
        过滤空文本后的 TranscribeResponse。

    逻辑:
        1. 校验文件存在；
        2. 加载（或复用缓存）Whisper 模型并调用 transcribe；
        3. 规范化各片段并过滤空文本；
        4. 无有效片段时返回 422。
    """
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
    """加载并缓存 Whisper 模型实例。

    用途：避免每次识别请求重复加载大模型，降低延迟。

    参数:
        model_name: Whisper 模型标识，如 base、small、medium。

    返回:
        已加载的 whisper 模型对象。

    逻辑:
        按 model_name 键查进程内缓存，未命中则调用 whisper.load_model 并写入缓存。
    """
    if model_name not in _model_cache:
        # 模型常驻进程缓存，避免每次识别都重复加载大模型。
        _model_cache[model_name] = whisper.load_model(model_name, device=settings.whisper_device)
    return _model_cache[model_name]


def _normalize_segment(index: int, segment: dict) -> Segment:
    """将 Whisper 原始片段字典转为 Segment 模型。

    用途：统一起止时间、文本与置信度字段，补全缺失值。

    参数:
        index: 片段序号，用于缺省时间估算。
        segment: Whisper transcribe 返回的单段 dict。

    返回:
        规范化后的 Segment 实例。

    逻辑:
        缺失 start/end 时用 index 推算 4 秒窗口；confidence 由 no_speech_prob 反算并 clamp 到 [0,1]。
    """
    start = float(segment.get("start", index * 4))
    end = float(segment.get("end", start + 4))
    text = str(segment.get("text", "")).strip()
    no_speech_prob = segment.get("no_speech_prob")
    confidence = None if no_speech_prob is None else max(0.0, min(1.0, 1 - float(no_speech_prob)))
    return Segment(start_time=start, end_time=end, text=text, confidence=confidence)
