"""生成产物 HTTP 路由。

Celery 流水线写入的中间/最终文件（源视频、配音、数字人片段、成片等）
通过本路由列表查询与按 artifact_id 下载。
"""

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
    """列出任务关联的全部产物元数据。

    用途：
        前端展示生成进度与可下载文件列表（path 由下载接口使用）。

    参数：
        task_id: 任务 ID。
        db: 数据库会话。

    返回：
        artifact dict 数组。

    逻辑：
        list_artifacts 内部 ensure_task。
    """
    return success_response(list_artifacts(db, task_id))


@router.get("/artifacts/{artifact_id}/download")
def download(artifact_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """按产物 ID 流式下载本地文件。

    用途：
        用户下载最终成片或中间产物。

    参数：
        artifact_id: 产物 ID。
        db: 数据库会话。

    返回：
        FileResponse，Content-Disposition 使用本地文件名。

    逻辑：
        get_artifact 后校验 path 存在，否则 404。
    """
    artifact = get_artifact(db, artifact_id)
    if not artifact.path or not Path(artifact.path).exists():
        raise ApiError("NOT_FOUND", "产物文件不存在", 404)
    return FileResponse(artifact.path, filename=Path(artifact.path).name)
