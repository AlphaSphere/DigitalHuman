from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import ApiError, success_response
from app.services.task_service import get_artifact, list_artifacts

router = APIRouter()


@router.get("/tasks/{task_id}/artifacts")
def artifacts(task_id: str, db: Session = Depends(get_db)) -> dict:
    return success_response(list_artifacts(db, task_id))


@router.get("/artifacts/{artifact_id}/download")
def download(artifact_id: str, db: Session = Depends(get_db)) -> FileResponse:
    artifact = get_artifact(db, artifact_id)
    if not artifact.path or not Path(artifact.path).exists():
        raise ApiError("NOT_FOUND", "产物文件不存在", 404)
    return FileResponse(artifact.path, filename=Path(artifact.path).name)
