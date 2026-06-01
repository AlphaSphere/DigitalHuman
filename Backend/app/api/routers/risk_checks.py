from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import ApiError, success_response
from app.domain.enums import RiskStage
from app.schemas.domain import ConfirmRiskRequest, PrePublishCheckInput
from app.services.risk_service import (
    build_pre_publish_findings,
    confirm_risk_check,
    get_risk_checks,
    replace_risk_check,
)
from app.services.serializers import risk_check_to_dict

router = APIRouter()


@router.get("/tasks/{task_id}/risk-checks")
def list_checks(task_id: str, stage: RiskStage | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    return success_response([risk_check_to_dict(item) for item in get_risk_checks(db, task_id, stage)])


@router.post("/tasks/{task_id}/risk-checks/{risk_check_id}/confirm")
def confirm(task_id: str, risk_check_id: str, payload: ConfirmRiskRequest, db: Session = Depends(get_db)) -> dict:
    try:
        task, risk_check = confirm_risk_check(db, task_id, risk_check_id, payload.confirmation_note)
    except ValueError as exc:
        raise ApiError("VALIDATION_ERROR", str(exc)) from exc
    return success_response({"task": task.id, "riskCheck": risk_check_to_dict(risk_check)})


@router.post("/tasks/{task_id}/pre-publish-check")
def pre_publish_check(task_id: str, payload: PrePublishCheckInput, db: Session = Depends(get_db)) -> dict:
    risk_check = replace_risk_check(db, task_id, RiskStage.pre_publish, build_pre_publish_findings(payload))
    db.commit()
    db.refresh(risk_check)
    return success_response(risk_check_to_dict(risk_check))
