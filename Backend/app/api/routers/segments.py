from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import success_response
from app.schemas.domain import UpdateSegmentsRequest
from app.services.segment_service import confirm_script, list_segments, save_segments
from app.services.serializers import task_to_dict

router = APIRouter()


@router.get("/tasks/{task_id}/segments")
def get_segments(task_id: str, db: Session = Depends(get_db)) -> dict:
    return success_response(list_segments(db, task_id))


@router.put("/tasks/{task_id}/segments")
def update_segments(task_id: str, payload: UpdateSegmentsRequest, db: Session = Depends(get_db)) -> dict:
    return success_response(save_segments(db, task_id, payload))


@router.post("/tasks/{task_id}/confirm-script")
def confirm(task_id: str, db: Session = Depends(get_db)) -> dict:
    return success_response(task_to_dict(confirm_script(db, task_id)))
