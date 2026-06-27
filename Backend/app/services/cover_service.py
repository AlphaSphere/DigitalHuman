"""封面生成服务。"""

from datetime import datetime

from sqlalchemy import select

from app.adapters.cover import CoverAdapter
from app.core.exceptions import ApiError
from app.db.models import ArtifactModel
from app.domain.enums import ArtifactType
from app.services.id_service import create_id
from app.services.task_service import ensure_task


def _final_video_path(db, task_id: str) -> str:
    artifact = db.scalar(
        select(ArtifactModel)
        .where(ArtifactModel.task_id == task_id, ArtifactModel.type == ArtifactType.final_video.value)
        .order_by(ArtifactModel.created_at.desc())
    )
    if not artifact or not artifact.path:
        raise ApiError("VALIDATION_ERROR", "请先生成最终视频再制作封面", 409)
    return artifact.path


def list_cover_candidates(db, task_id: str) -> list[dict]:
    """列出封面候选帧。"""
    video_path = _final_video_path(db, task_id)
    paths = CoverAdapter().extract_frame_candidates(task_id, video_path)
    return [{"index": index + 1, "path": path} for index, path in enumerate(paths)]


def generate_cover(db, task_id: str, payload: dict) -> dict:
    """生成封面并登记 artifact。"""
    ensure_task(db, task_id)
    video_path = _final_video_path(db, task_id)
    adapter = CoverAdapter()
    frame_path = payload.get("frame_path")
    if not frame_path:
        candidates = adapter.extract_frame_candidates(task_id, video_path, count=1)
        frame_path = candidates[0]

    cover_path = adapter.generate_cover(
        task_id,
        frame_path,
        text=payload.get("cover_text", ""),
        highlight_words=payload.get("highlight_words"),
        font_size=payload.get("font_size", 60),
        font_color=payload.get("font_color", "#FFFFFF"),
        highlight_color=payload.get("highlight_color", "#FFD600"),
        position=payload.get("position", "bottom"),
        use_ai_copy=payload.get("use_ai_copy", False),
        script=payload.get("script"),
    )
    artifact = ArtifactModel(
        id=create_id("artifact"),
        task_id=task_id,
        type=ArtifactType.cover.value,
        path=cover_path,
        meta={"label": "封面图", "format": "jpg"},
        created_at=datetime.utcnow(),
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return {"artifact_id": artifact.id, "path": cover_path}


def upload_cover(db, task_id: str, file_path: str) -> dict:
    """登记用户上传的封面。"""
    ensure_task(db, task_id)
    artifact = ArtifactModel(
        id=create_id("artifact"),
        task_id=task_id,
        type=ArtifactType.cover.value,
        path=file_path,
        meta={"label": "上传封面", "format": "jpg"},
        created_at=datetime.utcnow(),
    )
    db.add(artifact)
    db.commit()
    return {"artifact_id": artifact.id, "path": file_path}
