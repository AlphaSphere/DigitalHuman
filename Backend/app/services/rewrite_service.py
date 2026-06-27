"""DeepSeek 文案仿写与发布元信息服务。"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.llm import DeepSeekAdapter
from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.db.models import ScriptSegmentModel
from app.domain.enums import SegmentSource, TaskStatus
from app.services.id_service import create_id
from app.services.serializers import segment_to_dict
from app.services.task_service import ensure_task


def _apply_rewritten_text(segments: list[ScriptSegmentModel], rewritten: str) -> None:
    """将仿写结果写回段落：单段整段写入，多段按空行拆分。"""
    text = rewritten.strip()
    if not text:
        raise ApiError("VALIDATION_ERROR", "DeepSeek 返回空文案，请重试或调整指令")

    if len(segments) <= 1:
        if not segments:
            return
        segments[0].edited_text = text
        segments[0].source_type = SegmentSource.manual_edit.value
        return

    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    if len(blocks) == 1:
        blocks = [line.strip() for line in text.splitlines() if line.strip()]
    if not blocks:
        blocks = [text]

    for index, segment in enumerate(segments):
        segment.edited_text = blocks[index] if index < len(blocks) else blocks[-1]
        segment.source_type = SegmentSource.manual_edit.value


def rewrite_script(
    db: Session,
    task_id: str,
    mode: str = "auto",
    instruction: str | None = None,
    style: str | None = None,
) -> dict:
    """仿写任务脚本并更新分段。"""
    settings = get_settings()
    if not settings.enable_llm_rewrite:
        raise ApiError("FEATURE_DISABLED", "文案仿写功能未启用", 403)

    adapter = DeepSeekAdapter()
    if not adapter.is_configured():
        raise ApiError(
            "DEEPSEEK_NOT_CONFIGURED",
            "DeepSeek 未在服务端配置，请在项目根 .env 设置 DEEPSEEK_API_KEY 后重启应用。",
            503,
        )

    task = ensure_task(db, task_id)
    if task.status not in {
        TaskStatus.transcribed.value,
        TaskStatus.script_parsed.value,
        TaskStatus.script_confirmed.value,
        TaskStatus.content_review_required.value,
    }:
        raise ApiError("VALIDATION_ERROR", "当前任务状态不允许仿写", 409)

    segments = list(
        db.scalars(
            select(ScriptSegmentModel).where(ScriptSegmentModel.task_id == task_id).order_by(ScriptSegmentModel.index)
        ).all()
    )
    if not segments:
        raise ApiError("VALIDATION_ERROR", "没有可仿写的文案，请先完成识别或粘贴文案", 400)

    original = "\n".join(segment.edited_text or segment.original_text for segment in segments)
    if not original.strip():
        raise ApiError("VALIDATION_ERROR", "当前文案为空，无法仿写", 400)

    if mode == "instruction" and not (instruction or "").strip():
        raise ApiError("VALIDATION_ERROR", "按指令仿写时请填写改写要求", 400)

    try:
        rewritten = adapter.rewrite_script(
            original,
            mode,
            instruction,
            style,
            segment_count=len(segments),
        )
    except RuntimeError as exc:
        raise ApiError("DEEPSEEK_FAILED", str(exc), 502) from exc

    _apply_rewritten_text(segments, rewritten)

    # 仿写后回到「待确认」状态，风险检查留给用户点击「确认文案」
    task.status = TaskStatus.transcribed.value
    task.updated_at = datetime.utcnow()
    db.commit()

    all_segments = list(
        db.scalars(
            select(ScriptSegmentModel).where(ScriptSegmentModel.task_id == task_id).order_by(ScriptSegmentModel.index)
        ).all()
    )
    return {
        "segments": [segment_to_dict(segment) for segment in all_segments],
        "rewrite_summary": f"DeepSeek 仿写完成（{settings.deepseek_model}），请检查下方文案后保存或确认。",
    }


def generate_publish_metadata(
    db: Session,
    task_id: str,
    platform: str | None = None,
    tone: str = "viral",
) -> dict:
    """生成发布标题、描述与标签。"""
    task = ensure_task(db, task_id)
    script = "\n".join(
        segment.edited_text or segment.original_text for segment in sorted(task.segments, key=lambda s: s.index)
    )
    return DeepSeekAdapter().generate_publish_metadata(script, platform, tone)
