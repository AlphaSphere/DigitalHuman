"""文案段落解析服务（ASR/粘贴文案 → 结构化段落）。

在任务创建或脚本导入阶段，将整段口播文案切分为带时间轴的 ScriptSegment 草稿，
供后续编辑、确认与风险扫描使用。
"""

from app.domain.enums import SegmentSource
from app.services.id_service import create_id


# 无用户输入时的演示默认口播文案
DEFAULT_SCRIPT = (
    "大家好，今天介绍一个数字人口播视频生成流程。\n"
    "系统会先识别或解析文案，再生成配音和数字人视频。\n"
    "最后合成字幕并导出成片。"
)


def build_segments(task_id: str, source_type: SegmentSource, content: str | None = None) -> list[dict]:
    """将口播全文解析为段落字典列表（尚未落库）。

    用途：
        在「视频 ASR」或「粘贴字幕/文案」创建任务时，生成初始 ScriptSegment 字段集合。

    参数：
        task_id: 所属视频任务 ID。
        source_type: 段落来源枚举（如 whisper 识别、manual 粘贴等）。
        content: 原始文案；为空时使用内置 DEFAULT_SCRIPT。

    返回：
        可直接展开为 ScriptSegmentModel 的 dict 列表，含 index、时间轴、原文/编辑文等。

    逻辑：
        统一中英文句号后按「。」切句；无有效句时整段作为一句；
        whisper 来源附带递减的 confidence，其它来源 confidence 为 None。
    """
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
