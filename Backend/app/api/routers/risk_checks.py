"""内容风险审核 HTTP 路由。

覆盖脚本确认后（script）与分发前（pre_publish）两阶段：
列表查询、人工确认放行、发布前元信息校验。
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from sqlalchemy import select

from app.api.deps import get_db
from app.core.exceptions import ApiError, success_response
from app.domain.enums import ArtifactType, RiskStage, RiskStatus, TaskStatus
from app.schemas.domain import ConfirmRiskRequest, PrePublishCheckInput
from app.services.risk_service import (
    build_pre_publish_findings,
    confirm_risk_check,
    get_risk_checks,
    replace_risk_check,
)
from app.services.serializers import risk_check_to_dict
from app.services.task_service import ensure_task
from app.db.models import ArtifactModel

router = APIRouter()


@router.get("/tasks/{task_id}/risk-checks")
def list_checks(task_id: str, stage: RiskStage | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    """列出任务的风险审核记录。

    用途：
        展示历史审核结果与 findings，可按 stage 过滤。

    参数：
        task_id: 任务 ID。
        stage: 可选查询参数 script / pre_publish。
        db: 数据库会话。

    返回：
        riskCheck dict 数组。

    逻辑：
        get_risk_checks 预加载 findings 后 risk_check_to_dict。
    """
    ensure_task(db, task_id)
    return success_response([risk_check_to_dict(item) for item in get_risk_checks(db, task_id, stage)])


@router.post("/tasks/{task_id}/risk-checks/{risk_check_id}/confirm")
def confirm(task_id: str, risk_check_id: str, payload: ConfirmRiskRequest, db: Session = Depends(get_db)) -> dict:
    """人工确认通过某条风险审核。

    用途：
        待人工复核时，填写说明后放行并推进任务至 script_confirmed 或 publish_ready。

    参数：
        task_id: 任务 ID。
        risk_check_id: 风险记录 ID。
        payload: 含 confirmation_note 的请求体。
        db: 数据库会话。

    返回：
        含 task.id 与 riskCheck 对象的 success_response。

    逻辑：
        confirm_risk_check；ValueError 转为 VALIDATION_ERROR ApiError。
    """
    try:
        task, risk_check = confirm_risk_check(db, task_id, risk_check_id, payload.confirmation_note)
    except ValueError as exc:
        raise ApiError("VALIDATION_ERROR", str(exc)) from exc
    return success_response({"task": task.id, "riskCheck": risk_check_to_dict(risk_check)})


@router.post("/tasks/{task_id}/pre-publish-check")
def pre_publish_check(task_id: str, payload: PrePublishCheckInput, db: Session = Depends(get_db)) -> dict:
    """执行发布前风险检查（标题/简介/AI 标识）。

    用途：
        分发前最后一道内容合规校验，不直接创建分发记录。

    参数：
        task_id: 任务 ID。
        payload: PrePublishCheckInput（标题、简介、ai_label_confirmed 等）。
        db: 数据库会话。

    返回：
        本轮 pre_publish 阶段的 riskCheck dict。

    逻辑：
        build_pre_publish_findings → replace_risk_check → commit。
    """
    task = ensure_task(db, task_id)
    if task.status != TaskStatus.completed.value:
        raise ApiError("VALIDATION_ERROR", "请先完成视频生成后再进行发布前检查", 409)
    final_video = db.scalar(
        select(ArtifactModel).where(
            ArtifactModel.task_id == task_id,
            ArtifactModel.type == ArtifactType.final_video.value,
        )
    )
    if not final_video:
        raise ApiError("VALIDATION_ERROR", "未找到成片产物，无法执行发布前检查", 409)
    risk_check = replace_risk_check(db, task_id, RiskStage.pre_publish, build_pre_publish_findings(payload))
    task.status = TaskStatus.publish_checking.value
    db.flush()
    if risk_check.risk_status == RiskStatus.blocked.value:
        task.status = TaskStatus.publish_blocked.value
    elif risk_check.risk_status == RiskStatus.passed.value:
        task.status = TaskStatus.publish_ready.value
    else:
        task.status = TaskStatus.publish_blocked.value
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(risk_check)
    return success_response(risk_check_to_dict(risk_check))
