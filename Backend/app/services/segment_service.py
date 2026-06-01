from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.db.models import ScriptSegmentModel, TaskModel
from app.domain.enums import RiskStage, RiskStatus, SegmentSource, TaskStatus
from app.schemas.domain import UpdateSegmentsRequest
from app.services.id_service import create_id
from app.services.risk_service import build_script_findings, replace_risk_check
from app.services.serializers import segment_to_dict


def list_segments(db: Session, task_id: str) -> list[dict]:
    segments = db.scalars(
        select(ScriptSegmentModel).where(ScriptSegmentModel.task_id == task_id).order_by(ScriptSegmentModel.index)
    ).all()
    return [segment_to_dict(segment) for segment in segments]


def save_segments(db: Session, task_id: str, payload: UpdateSegmentsRequest) -> list[dict]:
    task = db.get(TaskModel, task_id)
    if not task:
        raise ApiError("NOT_FOUND", "任务不存在", 404)
    if not payload.segments:
        raise ApiError("VALIDATION_ERROR", "请至少保留一段文案")
    task.script_generation_mode = payload.script_generation_mode
    task.updated_at = datetime.utcnow()
    db.execute(delete(ScriptSegmentModel).where(ScriptSegmentModel.task_id == task_id))
    for index, item in enumerate(payload.segments, start=1):
        text = item.edited_text.strip()
        if not text:
            raise ApiError("VALIDATION_ERROR", "文案不能为空")
        db.add(
            ScriptSegmentModel(
                id=item.id or create_id("seg"),
                task_id=task_id,
                index=index,
                source_type=SegmentSource.manual_edit.value,
                start_time=item.start_time,
                end_time=item.end_time,
                original_text=item.original_text or text,
                edited_text=text,
                confidence=None,
            )
        )
    db.commit()
    return list_segments(db, task_id)


def confirm_script(db: Session, task_id: str) -> TaskModel:
    task = db.get(TaskModel, task_id)
    if not task:
        raise ApiError("NOT_FOUND", "任务不存在", 404)
    segments = db.scalars(select(ScriptSegmentModel).where(ScriptSegmentModel.task_id == task_id)).all()
    if not segments:
        raise ApiError("VALIDATION_ERROR", "没有可确认的文案段落")
    script_text = "\n".join(segment.edited_text or segment.original_text for segment in segments)
    risk_check = replace_risk_check(db, task_id, RiskStage.script, build_script_findings(task_id, script_text))
    if risk_check.risk_status == RiskStatus.blocked.value:
        task.status = TaskStatus.content_rejected.value
    elif risk_check.risk_status == RiskStatus.passed.value:
        task.status = TaskStatus.script_confirmed.value
    else:
        task.status = TaskStatus.content_review_required.value
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task
