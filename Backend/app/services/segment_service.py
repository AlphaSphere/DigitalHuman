"""口播文案段落（ScriptSegment）管理服务。"""

import json
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.db.models import ScriptSegmentModel, TaskModel
from app.domain.enums import ReviewedBy, RiskStage, RiskStatus, SegmentSource, TaskStatus
from app.schemas.domain import UpdateSegmentsRequest
from app.services.id_service import create_id
from app.services.risk_service import (
    build_script_findings_for_check,
    confirm_risk_check,
    get_risk_checks,
    replace_risk_check,
)

DEFAULT_SCRIPT_CONFIRM_NOTE = "已阅读风险提示，确认可以继续生成。"
from app.services.serializers import risk_check_to_dict, segment_to_dict, task_to_dict
from app.services.task_guards import assert_not_in_generation


def _load_segments_from_transcript_file(task_id: str) -> list[dict]:
    """从 whisper_segments.json 恢复段落（DB 为空时的兜底）。"""
    transcript_path = get_settings().storage_root / "tasks" / task_id / "intermediate" / "whisper_segments.json"
    if not transcript_path.exists():
        return []
    try:
        raw_segments = json.loads(transcript_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw_segments, list):
        return []

    restored: list[dict] = []
    next_index = 1
    for segment in raw_segments:
        text = str(segment.get("text") or segment.get("sentence") or "").strip()
        if not text:
            continue
        restored.append(
            {
                "id": create_id("seg"),
                "task_id": task_id,
                "index": next_index,
                "source_type": SegmentSource.whisper.value,
                "start_time": segment.get("start_time", segment.get("start")),
                "end_time": segment.get("end_time", segment.get("end")),
                "original_text": text,
                "edited_text": text,
                "confidence": segment.get("confidence"),
            }
        )
        next_index += 1
    return restored


def list_segments(db: Session, task_id: str) -> list[dict]:
    """查询任务下全部文案段落（按 index 排序）。"""
    task = db.get(TaskModel, task_id)
    if not task:
        raise ApiError("NOT_FOUND", "任务不存在", 404)
    segments = db.scalars(
        select(ScriptSegmentModel).where(ScriptSegmentModel.task_id == task_id).order_by(ScriptSegmentModel.index)
    ).all()
    if segments:
        return [segment_to_dict(segment) for segment in segments]
    return _load_segments_from_transcript_file(task_id)


def save_segments(db: Session, task_id: str, payload: UpdateSegmentsRequest) -> list[dict]:
    """全量替换任务的文案段落（用户编辑保存）。"""
    task = db.get(TaskModel, task_id)
    if not task:
        raise ApiError("NOT_FOUND", "任务不存在", 404)
    assert_not_in_generation(task, "保存文案")
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
    # 编辑已确认文案后撤销确认，需重新走合规
    if task.status in {TaskStatus.script_confirmed.value, TaskStatus.publish_ready.value}:
        task.status = TaskStatus.transcribed.value
    db.commit()
    return list_segments(db, task_id)


def _apply_script_risk_status(task: TaskModel, risk_status: str) -> None:
    """根据合规结果更新任务状态（检查阶段不自动 script_confirmed）。"""
    if risk_status == RiskStatus.blocked.value:
        task.status = TaskStatus.content_rejected.value
    elif risk_status == RiskStatus.passed.value:
        if task.status == TaskStatus.script_confirmed.value:
            return
        if task.status not in {TaskStatus.script_parsed.value, TaskStatus.transcribed.value}:
            task.status = TaskStatus.transcribed.value
    else:
        task.status = TaskStatus.content_review_required.value


def check_script_risk(db: Session, task_id: str) -> dict:
    """对当前文案运行合规检查，结果展示在文案页，不自动进入配置步骤。"""
    task = db.get(TaskModel, task_id)
    if not task:
        raise ApiError("NOT_FOUND", "任务不存在", 404)
    assert_not_in_generation(task, "执行合规检查")
    segments = db.scalars(select(ScriptSegmentModel).where(ScriptSegmentModel.task_id == task_id)).all()
    if not segments:
        raise ApiError("VALIDATION_ERROR", "没有可检查的文案段落", 400)
    script_text = "\n".join(segment.edited_text or segment.original_text for segment in segments)
    if not script_text.strip():
        raise ApiError("VALIDATION_ERROR", "文案为空，无法执行合规检查", 400)

    findings, risk_status, reviewed_by = build_script_findings_for_check(task_id, script_text)
    risk_check = replace_risk_check(
        db,
        task_id,
        RiskStage.script,
        findings,
        risk_status_override=risk_status,
        reviewed_by=reviewed_by,
    )
    _apply_script_risk_status(task, risk_check.risk_status)
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    db.refresh(risk_check)
    return {"task": task_to_dict(task), "riskCheck": risk_check_to_dict(risk_check)}


def confirm_script(db: Session, task_id: str, confirmation_note: str | None = None) -> TaskModel:
    """确认口播脚本：通过或带提示项时均可一键进入配置（仅 blocked 需改文案）。"""
    task = db.get(TaskModel, task_id)
    if not task:
        raise ApiError("NOT_FOUND", "任务不存在", 404)
    assert_not_in_generation(task, "确认文案")
    if task.status == TaskStatus.script_confirmed.value:
        return task

    note = (confirmation_note or "").strip() or DEFAULT_SCRIPT_CONFIRM_NOTE
    checks = get_risk_checks(db, task_id, RiskStage.script)
    latest = checks[0] if checks else None

    if latest and latest.risk_status == RiskStatus.blocked.value:
        raise ApiError("VALIDATION_ERROR", "内容存在高风险，请修改文案标注的问题后重新检查", 409)

    if latest and latest.risk_status in {RiskStatus.warning.value, RiskStatus.manual_review.value}:
        task, _ = confirm_risk_check(db, task_id, latest.id, note)
        return task

    if latest and latest.risk_status == RiskStatus.passed.value:
        task.status = TaskStatus.script_confirmed.value
        task.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
        return task

    segments = db.scalars(select(ScriptSegmentModel).where(ScriptSegmentModel.task_id == task_id)).all()
    if not segments:
        raise ApiError("VALIDATION_ERROR", "没有可确认的文案段落")
    script_text = "\n".join(segment.edited_text or segment.original_text for segment in segments)
    findings, risk_status, reviewed_by = build_script_findings_for_check(task_id, script_text)
    risk_check = replace_risk_check(
        db,
        task_id,
        RiskStage.script,
        findings,
        risk_status_override=risk_status,
        reviewed_by=reviewed_by,
    )
    if risk_check.risk_status == RiskStatus.blocked.value:
        task.status = TaskStatus.content_rejected.value
        task.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
        raise ApiError("VALIDATION_ERROR", "内容存在高风险，请修改文案标注的问题后重新检查", 409)
    if risk_check.risk_status == RiskStatus.passed.value:
        task.status = TaskStatus.script_confirmed.value
        task.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
        return task
    if risk_check.risk_status in {RiskStatus.warning.value, RiskStatus.manual_review.value}:
        task, _ = confirm_risk_check(db, task_id, risk_check.id, note)
        return task

    task.status = TaskStatus.content_review_required.value
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    raise ApiError("VALIDATION_ERROR", "合规检查未通过，请稍后重试", 409)
