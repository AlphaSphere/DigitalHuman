from datetime import datetime

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ApiError
from app.db.models import (
    ArtifactModel,
    AuthorizationRecordModel,
    ScriptSegmentModel,
    TaskModel,
)
from app.domain.enums import (
    ArtifactType,
    AuthorizationAssetType,
    AuthorizationSource,
    GenerationVideoMode,
    GenerationVoiceMode,
    ScriptSource,
    SegmentSource,
    TaskStatus,
)
from app.domain.status import build_progress
from app.schemas.domain import CreateScriptTaskRequest, SaveGenerationConfigRequest
from app.services.id_service import create_id
from app.services.script_parser import build_segments
from app.services.serializers import artifact_to_dict, task_to_dict
from app.services.storage_service import save_upload, write_text


def ensure_task(db: Session, task_id: str) -> TaskModel:
    task = db.scalar(select(TaskModel).where(TaskModel.id == task_id))
    if not task:
        raise ApiError("NOT_FOUND", "任务不存在", 404)
    return task


def create_video_task(db: Session, upload: UploadFile | None, source_url: str | None, aspect_ratio: str) -> TaskModel:
    if not upload and not source_url:
        raise ApiError("VALIDATION_ERROR", "请上传参考视频或填写视频链接")
    task_id = create_id("task")
    source_path = source_url
    if upload:
        source_path = save_upload(task_id, upload, "source")
    task = TaskModel(
        id=task_id,
        script_source=ScriptSource.video_asr.value,
        script_generation_mode="full_script",
        status=TaskStatus.uploaded.value,
        source_video_path=source_path,
        duration=62.5,
        aspect_ratio=aspect_ratio,
        error_code=None,
        error_message=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(task)
    db.flush()
    for item in build_segments(task_id, SegmentSource.whisper):
        db.add(ScriptSegmentModel(**item))
    if source_path:
        db.add(
            ArtifactModel(
                id=create_id("artifact"),
                task_id=task_id,
                type=ArtifactType.source_video.value,
                path=source_path,
                meta={"format": "mp4", "label": "参考视频"},
                created_at=datetime.utcnow(),
            )
        )
    db.commit()
    db.refresh(task)
    return task


def create_script_task(db: Session, payload: CreateScriptTaskRequest) -> TaskModel:
    if not payload.content.strip():
        raise ApiError("VALIDATION_ERROR", "请先粘贴字幕或口播文案")
    task_id = create_id("task")
    write_text(task_id, "input/pasted_script.txt", payload.content)
    task = TaskModel(
        id=task_id,
        script_source=payload.content_type,
        script_generation_mode="full_script",
        status=TaskStatus.script_parsed.value,
        duration=None,
        aspect_ratio=payload.aspect_ratio,
        error_code=None,
        error_message=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(task)
    db.flush()
    for item in build_segments(task_id, SegmentSource(payload.content_type), payload.content):
        db.add(ScriptSegmentModel(**item))
    db.commit()
    db.refresh(task)
    return task


def get_task_payload(task: TaskModel) -> dict:
    return {**task_to_dict(task), "progress": build_progress(TaskStatus(task.status))}


def save_generation_config(db: Session, task_id: str, payload: SaveGenerationConfigRequest) -> TaskModel:
    task = ensure_task(db, task_id)
    if payload.generation_voice_mode == GenerationVoiceMode.uploaded_voice.value and not payload.custom_voice_file_name:
        raise ApiError("VALIDATION_ERROR", "请先上传自己的音色样本")
    if payload.generation_video_mode == GenerationVideoMode.uploaded_video.value and not payload.custom_video_file_name:
        raise ApiError("VALIDATION_ERROR", "请先上传自己拍摄的视频素材")
    if (
        payload.generation_voice_mode == GenerationVoiceMode.uploaded_voice.value
        or payload.generation_video_mode == GenerationVideoMode.uploaded_video.value
    ) and not payload.authorization_confirmed:
        raise ApiError("VALIDATION_ERROR", "请先确认上传素材授权")

    task.voice_profile_id = payload.voice_profile_id
    task.avatar_profile_id = payload.avatar_profile_id
    task.generation_voice_mode = payload.generation_voice_mode
    task.custom_voice_path = (
        f"storage/tasks/{task_id}/input/{payload.custom_voice_file_name}"
        if payload.generation_voice_mode == GenerationVoiceMode.uploaded_voice.value
        else None
    )
    task.generation_video_mode = payload.generation_video_mode
    task.custom_video_path = (
        f"storage/tasks/{task_id}/input/{payload.custom_video_file_name}"
        if payload.generation_video_mode == GenerationVideoMode.uploaded_video.value
        else None
    )
    task.aspect_ratio = payload.aspect_ratio
    task.subtitle_style = payload.subtitle_style.model_dump()
    task.updated_at = datetime.utcnow()

    db.execute(delete(AuthorizationRecordModel).where(AuthorizationRecordModel.task_id == task_id))
    assets: list[AuthorizationAssetType] = []
    if payload.generation_voice_mode == GenerationVoiceMode.uploaded_voice.value:
        assets.append(AuthorizationAssetType.voice)
    if payload.generation_video_mode == GenerationVideoMode.uploaded_video.value:
        assets.append(AuthorizationAssetType.video)
    for asset in assets:
        db.add(
            AuthorizationRecordModel(
                id=create_id("auth"),
                task_id=task_id,
                asset_type=asset.value,
                source=AuthorizationSource.user_upload.value,
                authorization_confirmed=True,
                authorization_note="用户确认拥有素材使用授权，且内容可用于 AI 生成和对外发布。",
                confirmed_at=datetime.utcnow(),
            )
        )
    db.commit()
    db.refresh(task)
    return task


def start_generate(db: Session, task_id: str) -> TaskModel:
    task = ensure_task(db, task_id)
    if task.status in {TaskStatus.content_review_required.value, TaskStatus.content_rejected.value}:
        raise ApiError("CONTENT_BLOCKED", "请先处理内容风险后再开始生成", 409)
    task.status = TaskStatus.dubbing.value
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


def retry_task(db: Session, task_id: str) -> TaskModel:
    task = ensure_task(db, task_id)
    task.status = TaskStatus.retrying.value
    task.error_code = None
    task.error_message = None
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


def list_artifacts(db: Session, task_id: str) -> list[dict]:
    ensure_task(db, task_id)
    artifacts = db.scalars(select(ArtifactModel).where(ArtifactModel.task_id == task_id)).all()
    return [artifact_to_dict(artifact) for artifact in artifacts]


def get_artifact(db: Session, artifact_id: str) -> ArtifactModel:
    artifact = db.get(ArtifactModel, artifact_id)
    if not artifact:
        raise ApiError("NOT_FOUND", "产物不存在", 404)
    return artifact


def task_with_relationships(db: Session, task_id: str) -> TaskModel:
    task = db.scalar(
        select(TaskModel)
        .options(selectinload(TaskModel.segments), selectinload(TaskModel.artifacts))
        .where(TaskModel.id == task_id)
    )
    if not task:
        raise ApiError("NOT_FOUND", "任务不存在", 404)
    return task
