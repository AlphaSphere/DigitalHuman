"""封面 API 路由。"""

import json

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import get_db
from app.core.exceptions import success_response
from app.schemas.domain import GenerateCoverRequest
from app.services.cover_service import generate_cover, list_cover_candidates, upload_cover
from app.services.storage_service import save_upload

router = APIRouter()


@router.get("/tasks/{task_id}/covers/candidates")
def cover_candidates(task_id: str, db=Depends(get_db)) -> dict:
    return success_response(list_cover_candidates(db, task_id))


@router.post("/tasks/{task_id}/covers/generate")
def create_cover(task_id: str, payload: GenerateCoverRequest, db=Depends(get_db)) -> dict:
    return success_response(generate_cover(db, task_id, payload.model_dump()))


@router.post("/tasks/{task_id}/covers/upload")
def upload_cover_file(task_id: str, file: UploadFile = File(...), db=Depends(get_db)) -> dict:
    path = save_upload(task_id, file, "cover")
    return success_response(upload_cover(db, task_id, path))
