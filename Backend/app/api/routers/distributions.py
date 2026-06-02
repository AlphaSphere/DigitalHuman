from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import success_response
from app.schemas.domain import CreateDistributionRequest
from app.services.distribution_service import create_distribution, get_distribution, list_distributions
from app.services.serializers import distribution_to_dict
from app.workers.tasks import run_distribution_task

router = APIRouter()


@router.get("/tasks/{task_id}/distributions")
def distributions(task_id: str, db: Session = Depends(get_db)) -> dict:
    return success_response(list_distributions(db, task_id))


@router.post("/tasks/{task_id}/distributions")
def create(task_id: str, payload: CreateDistributionRequest, db: Session = Depends(get_db)) -> dict:
    record = create_distribution(db, task_id, payload)
    run_distribution_task.delay(record.id)
    return success_response(distribution_to_dict(record))


@router.post("/distributions/{distribution_id}/retry")
def retry(distribution_id: str, db: Session = Depends(get_db)) -> dict:
    record = get_distribution(db, distribution_id)
    record.status = "pending"
    record.error_message = None
    db.commit()
    db.refresh(record)
    run_distribution_task.delay(record.id)
    return success_response(distribution_to_dict(record))
