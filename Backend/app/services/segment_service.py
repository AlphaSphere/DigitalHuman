"""口播文案段落（ScriptSegment）管理服务。

对应流程中 ASR/解析后的「脚本编辑 → 确认」环节：
用户可增删改段落，确认后触发脚本阶段风险扫描并更新任务状态。
"""

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
    """查询任务下全部文案段落（按 index 排序）。

    用途：
        前端脚本编辑页加载当前段落列表。

    参数：
        db: 数据库会话。
        task_id: 任务 ID。

    返回：
        段落 dict 列表（segment_to_dict 序列化）。

    逻辑：
        按 ScriptSegmentModel.index 升序查询并转换。
    """
    segments = db.scalars(
        select(ScriptSegmentModel).where(ScriptSegmentModel.task_id == task_id).order_by(ScriptSegmentModel.index)
    ).all()
    return [segment_to_dict(segment) for segment in segments]


def save_segments(db: Session, task_id: str, payload: UpdateSegmentsRequest) -> list[dict]:
    """全量替换任务的文案段落（用户编辑保存）。

    用途：
        PUT segments 时持久化用户调整后的分段与时间轴。

    参数：
        db: 数据库会话。
        task_id: 任务 ID。
        payload: 含 script_generation_mode 与 segments 列表的请求体。

    返回：
        保存后最新的段落 dict 列表。

    逻辑：
        校验任务存在、至少一段、每段 edited_text 非空；
        删除旧段落再按序插入，source_type 标记为 manual_edit，最后 commit 并 list。
    """
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
    """确认口播脚本并触发脚本阶段风险审核。

    用途：
        用户完成文案编辑后提交，进入风险检查分支（通过 / 待审 / 拒绝）。

    参数：
        db: 数据库会话。
        task_id: 任务 ID。

    返回：
        状态已更新的 TaskModel。

    逻辑：
        合并各段 edited_text 为全文，replace_risk_check(script)；
        按 risk_status 设置 content_rejected / script_confirmed / content_review_required。
    """
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
