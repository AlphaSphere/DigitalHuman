import json

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import success_response
from app.schemas.domain import CreateScriptTaskRequest, SaveGenerationConfigRequest
from app.services.serializers import task_to_dict
from app.services.storage_service import save_upload
from app.services.task_service import (
    create_script_task,
    create_video_task,
    ensure_task,
    retry_task,
    save_generation_config,
    start_generate,
)
from app.workers.tasks import run_generation_pipeline, transcribe_video_task

router = APIRouter()


@router.post("/tasks/video")
def create_video(
    db: Session = Depends(get_db),
    file: UploadFile | None = File(default=None),
    source_url: str | None = Form(default=None),
    aspect_ratio: str = Form(default="9:16"),
) -> dict:
    task = create_video_task(db, file, source_url, aspect_ratio)
    transcribe_video_task.delay(task.id)
    return success_response(task_to_dict(task))


@router.post("/tasks/script")
def create_script(payload: CreateScriptTaskRequest, db: Session = Depends(get_db)) -> dict:
    return success_response(task_to_dict(create_script_task(db, payload)))


@router.get("/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)) -> dict:
    return success_response(task_to_dict(ensure_task(db, task_id)))


@router.post("/tasks/{task_id}/generation-config")
def save_config(
    task_id: str,
    config: str = Form(...),
    custom_voice_file: UploadFile | None = File(default=None),
    custom_video_file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> dict:
    payload = SaveGenerationConfigRequest.model_validate(json.loads(config))
    task = save_generation_config(db, task_id, payload)
    if custom_voice_file:
        task.custom_voice_path = save_upload(task_id, custom_voice_file, "custom_voice")
    if custom_video_file:
        task.custom_video_path = save_upload(task_id, custom_video_file, "custom_video")
    db.commit()
    db.refresh(task)
    return success_response(task_to_dict(task))


@router.post("/tasks/{task_id}/generate")
def generate(task_id: str, db: Session = Depends(get_db)) -> dict:
    task = start_generate(db, task_id)
    run_generation_pipeline.delay(task_id)
    return success_response(task_to_dict(task))


@router.post("/tasks/{task_id}/retry")
def retry(task_id: str, db: Session = Depends(get_db)) -> dict:
    task = retry_task(db, task_id)
    run_generation_pipeline.delay(task_id)
    return success_response(task_to_dict(task))
