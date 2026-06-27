"""视频任务核心服务（创建 → 配置 → 触发生成）。

承载主业务链路：
1. create_video_task / create_script_task：任务创建与初始段落；
2. save_generation_config：配音/形象/字幕/音乐与授权；
3. start_generate / retry_task：校验风险后投递 Celery run_generation_pipeline；
4. artifacts 查询供流水线产物下载。
"""

from datetime import datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.adapters.url_download import UrlDownloadAdapter
from app.core.config import get_settings
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
    RiskStage,
    RiskStatus,
    ReviewedBy,
    ScriptSource,
    SegmentSource,
    TaskStatus,
)
from app.domain.status import build_progress
from app.schemas.domain import CreateScriptTaskRequest, SaveGenerationConfigRequest
from app.services.id_service import create_id
from app.services.risk_service import get_risk_checks
from app.services.script_parser import build_segments
from app.services.serializers import artifact_to_dict, task_to_dict
from app.services.storage_service import save_upload, task_dir, write_text
from app.services.task_guards import assert_can_retry_generation, is_stale_generation


def ensure_task(db: Session, task_id: str) -> TaskModel:
    """按 ID 加载任务，不存在则抛 404。

    用途：
        各 task 相关写操作的前置校验。

    参数：
        db: 数据库会话。
        task_id: 任务 ID。

    返回：
        TaskModel 实例。

    逻辑：
        scalar 查询，缺失时 ApiError NOT_FOUND。
    """
    task = db.scalar(select(TaskModel).where(TaskModel.id == task_id))
    if not task:
        raise ApiError("NOT_FOUND", "任务不存在", 404)
    return task


def create_video_task(db: Session, upload: UploadFile | None, source_url: str | None, aspect_ratio: str) -> TaskModel:
    """创建「参考视频 → ASR 文案」类任务。

    用途：
        POST /tasks/video 入口；创建后由 Celery transcribe_video_task 做 ASR（当前为模拟段落）。

    参数：
        db: 数据库会话。
        upload: 可选，本地上传参考视频。
        source_url: 可选，远程视频链接（与 upload 二选一）。
        aspect_ratio: 画幅比例，默认 9:16。

    返回：
        已 commit 的 TaskModel（status=uploaded，等待 transcribe_video_task 写入段落）。

    逻辑：
        生成 task_id，有 upload 则 save_upload；
        写入 TaskModel 与可选 source_video 产物记录；ASR 段落由 transcribe_video_task 生成。
    """
    if not upload and not source_url:
        raise ApiError("VALIDATION_ERROR", "请上传参考视频或填写视频链接")
    task_id = create_id("task")
    stored_url = source_url if source_url and not upload else None
    source_path = source_url
    if upload:
        source_path = save_upload(task_id, upload, "source")
    task = TaskModel(
        id=task_id,
        script_source=ScriptSource.video_asr.value,
        script_generation_mode="full_script",
        status=TaskStatus.uploaded.value,
        source_video_path=source_path,
        source_url=stored_url,
        duration=62.5,
        aspect_ratio=aspect_ratio,
        error_code=None,
        error_message=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(task)
    db.flush()
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
    """创建「粘贴字幕/文案」类任务（跳过视频 ASR）。

    用途：
        POST /tasks/script；直接进入 script_parsed，段落来自用户粘贴内容。

    参数：
        db: 数据库会话。
        payload: 含 content_type、content、aspect_ratio 等。

    返回：
        已 commit 的 TaskModel（status=script_parsed）。

    逻辑：
        校验 content 非空，write_text 备份原文，按 content_type 解析 build_segments 并落库。
    """
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
    """组装带进度信息的任务 API 载荷。

    用途：
        需要同时返回任务字段与流水线 progress 的接口（若路由层选用）。

    参数：
        task: TaskModel 实例。

    返回：
        task_to_dict 结果合并 build_progress(TaskStatus) 的字典。

    逻辑：
        由当前 task.status 枚举推导前端进度条状态。
    """
    return {**task_to_dict(task), "progress": build_progress(TaskStatus(task.status))}


def _resolve_stored_file(path_value: str | None) -> Path | None:
    """将任务素材路径解析为绝对路径并校验文件是否存在。"""
    if not path_value:
        return None
    settings = get_settings()
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    if path_value.startswith("storage/"):
        candidate = settings.storage_root.parent / path_value
    else:
        candidate = settings.storage_root / path_value
    candidate = candidate.resolve()
    return candidate if candidate.exists() else None


def save_generation_config(db: Session, task_id: str, payload: SaveGenerationConfigRequest) -> TaskModel:
    """保存生成配置（音色/形象/字幕/音乐）及上传素材授权记录。

    用途：
        脚本与风险通过后，用户选定生成参数，为 Celery 流水线提供 Task 字段。

    参数：
        db: 数据库会话。
        task_id: 任务 ID。
        payload: SaveGenerationConfigRequest（含模式、profile、字幕样式等）。

    返回：
        已 commit 的 TaskModel。

    逻辑：
        校验上传模式需文件名与 authorization_confirmed；
        更新 Task 生成相关字段，删除旧授权记录后按 voice/video 资产重建 AuthorizationRecordModel。
    """
    task = ensure_task(db, task_id)
    existing_voice = _resolve_stored_file(task.custom_voice_path)
    existing_video = _resolve_stored_file(task.custom_video_path)

    if payload.generation_voice_mode == GenerationVoiceMode.uploaded_voice.value:
        if not payload.custom_voice_file_name and not existing_voice:
            raise ApiError("VALIDATION_ERROR", "请先上传自己的音色样本")
    if payload.generation_video_mode == GenerationVideoMode.uploaded_video.value:
        if not payload.custom_video_file_name and not existing_video:
            raise ApiError("VALIDATION_ERROR", "请先上传自己拍摄的视频素材")
    if (
        payload.generation_voice_mode == GenerationVoiceMode.uploaded_voice.value
        or payload.generation_video_mode == GenerationVideoMode.uploaded_video.value
    ) and not payload.authorization_confirmed:
        raise ApiError("VALIDATION_ERROR", "请先确认上传素材授权")

    task.voice_profile_id = payload.voice_profile_id
    task.avatar_profile_id = payload.avatar_profile_id
    task.generation_voice_mode = payload.generation_voice_mode
    if payload.generation_voice_mode == GenerationVoiceMode.uploaded_voice.value:
        if payload.custom_voice_file_name:
            task.custom_voice_path = str((task_dir(task_id) / "input" / payload.custom_voice_file_name).resolve())
        elif existing_voice:
            task.custom_voice_path = str(existing_voice)
        task.custom_voice_prompt_text = payload.custom_voice_prompt_text.strip() if payload.custom_voice_prompt_text else None
    else:
        task.custom_voice_path = None
        task.custom_voice_prompt_text = None
    task.generation_video_mode = payload.generation_video_mode
    if payload.generation_video_mode == GenerationVideoMode.uploaded_video.value:
        if payload.custom_video_file_name:
            task.custom_video_path = str((task_dir(task_id) / "input" / payload.custom_video_file_name).resolve())
        elif existing_video:
            task.custom_video_path = str(existing_video)
    else:
        task.custom_video_path = None
    task.aspect_ratio = payload.aspect_ratio
    task.subtitle_style = payload.subtitle_style.model_dump()
    task.background_music_path = payload.background_music_path
    task.background_music_mode = payload.background_music_mode
    task.background_music_volume = payload.background_music_volume
    task.voice_speed = payload.voice_speed
    task.ai_watermark_enabled = payload.ai_watermark_enabled
    task.export_without_subtitle = payload.export_without_subtitle
    task.avatar_engine = payload.avatar_engine
    task.generation_quality = payload.generation_quality
    task.tuilionnx_sync_offset = payload.tuilionnx_sync_offset
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


def _ensure_ready_for_generation(db: Session, task: TaskModel) -> None:
    """校验文案合规门禁，必要时将任务推进到 script_confirmed。"""
    if task.status == TaskStatus.content_rejected.value:
        raise ApiError("CONTENT_BLOCKED", "内容已被阻断，请返回修改文案", 409)

    checks = get_risk_checks(db, task.id, RiskStage.script)
    latest = checks[0] if checks else None

    if task.status == TaskStatus.content_review_required.value:
        if not latest:
            raise ApiError("CONTENT_BLOCKED", "请先完成文案合规检查", 409)
        if latest.risk_status == RiskStatus.blocked.value:
            raise ApiError("CONTENT_BLOCKED", "内容已被阻断，请返回修改文案", 409)
        if latest.risk_status in {RiskStatus.warning.value, RiskStatus.manual_review.value}:
            if latest.reviewed_by != ReviewedBy.user.value:
                raise ApiError(
                    "CONTENT_REVIEW_REQUIRED",
                    "文案合规待人工确认，请返回「文案与合规」页填写确认说明",
                    409,
                )
        task.status = TaskStatus.script_confirmed.value
        return

    if task.status == TaskStatus.transcribed.value or task.status == TaskStatus.script_parsed.value:
        if latest and latest.risk_status == RiskStatus.passed.value:
            task.status = TaskStatus.script_confirmed.value
            return
        raise ApiError("VALIDATION_ERROR", "请先完成文案确认与合规检查", 409)

    if task.status == TaskStatus.failed.value:
        if task.error_code == "TRANSCRIBE_FAILED":
            raise ApiError("TRANSCRIBE_FAILED", "请先完成文案识别后再生成", 409)
        if latest and latest.risk_status == RiskStatus.blocked.value:
            raise ApiError("CONTENT_BLOCKED", "内容已被阻断，请返回修改文案", 409)
        # 已进入过生成流水线的失败任务，允许直接重试，无需再次跑合规。
        task.status = TaskStatus.script_confirmed.value
        task.error_code = None
        task.error_message = None
        return

    if task.status != TaskStatus.script_confirmed.value:
        raise ApiError("VALIDATION_ERROR", "请先完成文案确认后再开始生成", 409)


GENERATION_ARTIFACT_TYPES = (
    ArtifactType.tts_audio.value,
    ArtifactType.avatar_video.value,
    ArtifactType.subtitle.value,
    ArtifactType.final_video.value,
    ArtifactType.final_video_no_subtitle.value,
)


def clear_generation_artifacts(db: Session, task_id: str) -> None:
    """重试前清理旧生成产物记录，避免下载/预览取到过期文件。"""
    db.execute(
        delete(ArtifactModel).where(
            ArtifactModel.task_id == task_id,
            ArtifactModel.type.in_(GENERATION_ARTIFACT_TYPES),
        )
    )


def prepare_for_generation(db: Session, task_id: str) -> TaskModel:
    """校验合规并推进到 script_confirmed，但不进入 dubbing。"""
    task = ensure_task(db, task_id)
    _ensure_ready_for_generation(db, task)
    _ensure_generation_voice_ready(task)
    db.commit()
    db.refresh(task)
    return task


def _ensure_generation_voice_ready(task: TaskModel) -> None:
    """生成前校验音色配置，避免「已上传样本却仍走默认音色」。"""
    if not task.generation_voice_mode:
        raise ApiError("VALIDATION_ERROR", "请先在配置页保存生成参数（音色、数字人、字幕等）")
    if task.generation_voice_mode != GenerationVoiceMode.uploaded_voice.value:
        return
    voice_file = _resolve_stored_file(task.custom_voice_path)
    if not voice_file:
        raise ApiError(
            "VALIDATION_ERROR",
            "已选择上传自己的音色，但未找到有效音频样本，请回到配置页重新上传并保存",
        )


def mark_generation_started(db: Session, task_id: str) -> TaskModel:
    """投递流水线成功后，将任务标记为 dubbing。"""
    task = ensure_task(db, task_id)
    task.status = TaskStatus.dubbing.value
    task.error_code = None
    task.error_message = None
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


def start_generate(db: Session, task_id: str) -> TaskModel:
    """将任务置为生成中状态（配音阶段入口）。

    用途：
        POST /tasks/{id}/generate 在投递 Celery 前的同步状态更新。

    参数：
        db: 数据库会话。
        task_id: 任务 ID。

    返回：
        status=dubbing 的 TaskModel。

    逻辑：
        校验文案合规与任务状态；由路由层 enqueue 后再 mark_generation_started。
    """
    return prepare_for_generation(db, task_id)


def retry_task(db: Session, task_id: str) -> TaskModel:
    """重置失败任务为重试状态并清空错误信息。

    用途：
        POST /tasks/{id}/retry 后再次投递 run_generation_pipeline。

    参数：
        db: 数据库会话。
        task_id: 任务 ID。

    返回：
        status=retrying 的 TaskModel。

    逻辑：
        卡住超时的生成任务强制重置；校验 error_code；清理旧产物；置 retrying。
    """
    task = ensure_task(db, task_id)
    if is_stale_generation(task):
        task.status = TaskStatus.failed.value
        task.error_code = "GENERATION_FAILED"
        task.error_message = "生成阶段长时间无更新，已允许强制重试"
        task.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
    assert_can_retry_generation(task)
    _ensure_ready_for_generation(db, task)
    clear_generation_artifacts(db, task_id)
    task.status = TaskStatus.retrying.value
    task.error_code = None
    task.error_message = None
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


def list_artifacts(db: Session, task_id: str) -> list[dict]:
    """列出任务关联的全部生成产物。

    用途：
        流水线各阶段产物查询与下载入口的数据源。

    参数：
        db: 数据库会话。
        task_id: 任务 ID。

    返回：
        artifact dict 列表。

    逻辑：
        ensure_task 后按 task_id 查询 ArtifactModel 并 artifact_to_dict。
    """
    ensure_task(db, task_id)
    artifacts = db.scalars(select(ArtifactModel).where(ArtifactModel.task_id == task_id)).all()
    return [artifact_to_dict(artifact) for artifact in artifacts]


def get_artifact(db: Session, artifact_id: str) -> ArtifactModel:
    """按产物 ID 加载单条 Artifact。

    用途：
        下载接口校验产物存在性。

    参数：
        db: 数据库会话。
        artifact_id: 产物 ID。

    返回：
        ArtifactModel 实例。

    逻辑：
        db.get，缺失抛 NOT_FOUND。
    """
    artifact = db.get(ArtifactModel, artifact_id)
    if not artifact:
        raise ApiError("NOT_FOUND", "产物不存在", 404)
    return artifact


def task_with_relationships(db: Session, task_id: str) -> TaskModel:
    """加载任务并预加载 segments、artifacts 关系。

    用途：
        需要一次性返回任务及关联数据的内部或扩展 API。

    参数：
        db: 数据库会话。
        task_id: 任务 ID。

    返回：
        含 segments、artifacts 的 TaskModel。

    逻辑：
        selectinload 预加载，不存在则 404。
    """
    task = db.scalar(
        select(TaskModel)
        .options(selectinload(TaskModel.segments), selectinload(TaskModel.artifacts))
        .where(TaskModel.id == task_id)
    )
    if not task:
        raise ApiError("NOT_FOUND", "任务不存在", 404)
    return task


def resolve_source_video_file(task: TaskModel) -> Path | None:
    """解析任务参考视频的本地文件路径（URL 或未落盘时返回 None）。"""
    if not task.source_video_path:
        return None
    adapter = UrlDownloadAdapter()
    if adapter.is_remote_url(task.source_video_path):
        return None

    candidate = Path(task.source_video_path)
    if candidate.exists():
        return candidate

    storage_path = get_settings().storage_root / str(task.source_video_path).replace("\\", "/")
    if storage_path.exists():
        return storage_path
    return None
