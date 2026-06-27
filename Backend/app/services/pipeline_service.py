"""一键追爆款流水线编排服务。"""

from datetime import datetime

from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.db.models import TaskModel
from app.domain.enums import BackgroundMusicMode, GenerationVoiceMode, PipelineMode, TaskStatus
from app.domain.status import build_progress
from app.schemas.domain import OneClickPipelineRequest, SaveGenerationConfigRequest, SubtitleStyle
from app.services.serializers import task_to_dict
from app.services.storage_service import save_upload, task_dir
from app.services.task_service import create_video_task, ensure_task, save_generation_config


def _default_generation_preset(payload: OneClickPipelineRequest) -> SaveGenerationConfigRequest:
    voice_mode = payload.generation_voice_mode or GenerationVoiceMode.preset_voice.value
    return SaveGenerationConfigRequest(
        voice_profile_id="voice_default_female",
        avatar_profile_id="avatar_studio_a",
        generation_voice_mode=voice_mode,
        generation_video_mode="preset_avatar",
        authorization_confirmed=voice_mode == GenerationVoiceMode.preset_voice.value,
        aspect_ratio=payload.aspect_ratio,
        subtitle_style=SubtitleStyle(enabled=True, font_size=20, position="bottom", color="#FFFFFF", stroke=True),
        background_music_mode=payload.background_music_mode,
        background_music_volume=0.18,
        voice_speed=payload.voice_speed,
        ai_watermark_enabled=payload.ai_watermark_enabled,
        export_without_subtitle=payload.export_without_subtitle,
        avatar_engine=payload.avatar_engine,
        generation_quality=payload.generation_quality,
    )


def update_pipeline_stage(db: Session, task: TaskModel, stage: str, message: str, percent: int) -> None:
    """更新一键流程子进度。"""
    stage_data = dict(task.pipeline_stage or {})
    stage_data.update({"stage": stage, "message": message, "percent": percent})
    task.pipeline_stage = stage_data
    task.updated_at = datetime.utcnow()
    db.commit()


def get_pipeline_status(db: Session, task_id: str) -> dict:
    """查询流水线状态。"""
    task = ensure_task(db, task_id)
    stage = task.pipeline_stage or {"stage": task.status, "message": "", "percent": 0}
    return {
        "task_id": task.id,
        "stage": stage.get("stage", task.status),
        "message": stage.get("message", ""),
        "percent": stage.get("percent", 0),
        "stage_timings": stage.get("stage_timings"),
        "status": task.status,
        "progress": build_progress(TaskStatus(task.status)),
    }


def _needs_config_before_generate(task: TaskModel, payload: OneClickPipelineRequest) -> bool:
    """一键流程是否需在生成前补全音色/形象配置。"""
    if not payload.require_config_before_generate:
        return False
    if task.generation_voice_mode == GenerationVoiceMode.uploaded_voice.value and not task.custom_voice_path:
        return True
    return False


def start_one_click_pipeline(
    db: Session,
    payload: OneClickPipelineRequest,
    upload: UploadFile | None = None,
    voice_upload: UploadFile | None = None,
) -> TaskModel:
    """创建任务并投递一键全流程 Celery。"""
    if not payload.source_url and not upload:
        raise ApiError("VALIDATION_ERROR", "请提供对标链接或上传视频")
    task = create_video_task(db, upload, payload.source_url, payload.aspect_ratio)
    task.source_url = payload.source_url
    task.pipeline_mode = PipelineMode.one_click.value
    task.pipeline_stage = {"stage": "download", "message": "准备下载对标视频", "percent": 5}
    task.voice_speed = payload.voice_speed
    task.background_music_mode = payload.background_music_mode
    task.ai_watermark_enabled = payload.ai_watermark_enabled
    task.export_without_subtitle = payload.export_without_subtitle
    task.avatar_engine = payload.avatar_engine
    task.generation_quality = payload.generation_quality
    db.commit()
    db.refresh(task)

    if payload.generation_preset:
        save_generation_config(db, task.id, payload.generation_preset)
    else:
        preset = _default_generation_preset(payload)
        if voice_upload:
            stored_path = save_upload(task.id, voice_upload, "custom_voice")
            preset.generation_voice_mode = GenerationVoiceMode.uploaded_voice.value
            preset.custom_voice_file_name = Path(stored_path).name
            preset.authorization_confirmed = True
            save_generation_config(db, task.id, preset)
        else:
            save_generation_config(db, task.id, preset)

    if _needs_config_before_generate(task, payload):
        task.pipeline_stage = {
            "stage": "await_config",
            "message": "请先上传音色样本并保存生成配置",
            "percent": 45,
        }
        task.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(task)

    return task


def list_tasks(db: Session, limit: int = 50) -> list[dict]:
    """任务列表（批量/历史）。"""
    tasks = db.scalars(select(TaskModel).order_by(TaskModel.created_at.desc()).limit(limit)).all()
    return [task_to_dict(task) for task in tasks]
