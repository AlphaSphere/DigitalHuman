from app.domain.enums import SegmentSource
from app.services.id_service import create_id


DEFAULT_SCRIPT = (
    "大家好，今天介绍一个数字人口播视频生成流程。\n"
    "系统会先识别或解析文案，再生成配音和数字人视频。\n"
    "最后合成字幕并导出成片。"
)


def build_segments(task_id: str, source_type: SegmentSource, content: str | None = None) -> list[dict]:
    text = content or DEFAULT_SCRIPT
    parts = [part.strip() for part in text.replace("！", "。").replace("？", "。").split("。") if part.strip()]
    if not parts:
        parts = [text.strip()]
    return [
        {
            "id": create_id("seg"),
            "task_id": task_id,
            "index": index + 1,
            "source_type": source_type.value,
            "start_time": index * 4,
            "end_time": index * 4 + 3.6,
            "original_text": f"{part}。",
            "edited_text": f"{part}。",
            "confidence": max(0.78, 0.96 - index * 0.04) if source_type == SegmentSource.whisper else None,
        }
        for index, part in enumerate(parts)
    ]
