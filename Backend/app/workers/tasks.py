"""Celery 异步任务：转写、生成流水线、视频分发、一键追爆款。"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.adapters.cozyvoice import CozyVoiceAdapter
from app.adapters.distributor import DistributorAdapter
from app.adapters.ffmpeg import FFmpegAdapter
from app.adapters.heygem import HeyGemAdapter
from app.adapters.tuilionnx import TuiliONNXAdapter
from app.adapters.url_download import resolve_local_video_path
from app.adapters.whisper import WhisperAdapter
from app.db.models import ArtifactModel, DistributionRecordModel, ScriptSegmentModel, TaskModel
from app.db.session import SessionLocal
from app.domain.enums import ArtifactType, AvatarEngine, GenerationQuality, GenerationVoiceMode, SegmentSource, TaskStatus
from app.services.cover_service import generate_cover
from app.services.id_service import create_id
from app.services.music_service import resolve_background_music_path
from app.services.rewrite_service import generate_publish_metadata, rewrite_script
from app.services.segment_service import check_script_risk, confirm_script
from app.services.storage_service import write_text
from app.services.task_guards import GENERATION_PHASE_STATUSES
from app.services.task_service import clear_generation_artifacts
from app.services.risk_service import get_risk_checks
from app.domain.enums import RiskStage, RiskStatus
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _set_status(db, task: TaskModel, status: TaskStatus) -> None:
    task.status = status.value
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)


def _set_pipeline(db, task: TaskModel, stage: str, message: str, percent: int) -> None:
    stage_data = dict(task.pipeline_stage or {})
    stage_data.update({"stage": stage, "message": message, "percent": percent})
    task.pipeline_stage = stage_data
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)


def _record_stage_timing(task: TaskModel, stage: str, duration_ms: int) -> None:
    """记录流水线各阶段耗时，供进度页展示优化效果。"""
    stage_data = dict(task.pipeline_stage or {})
    timings = dict(stage_data.get("stage_timings") or {})
    timings[stage] = {
        "duration_ms": duration_ms,
        "finished_at": datetime.utcnow().isoformat(),
    }
    stage_data["stage_timings"] = timings
    task.pipeline_stage = stage_data


def _resolve_generation_quality(task: TaskModel) -> str:
    return task.generation_quality or GenerationQuality.full.value


def _script_text(db, task_id: str) -> str:
    segments = db.scalars(
        select(ScriptSegmentModel).where(ScriptSegmentModel.task_id == task_id).order_by(ScriptSegmentModel.index)
    ).all()
    return "\n".join(segment.edited_text or segment.original_text for segment in segments)


def _script_segments(db, task_id: str) -> list[ScriptSegmentModel]:
    return list(
        db.scalars(
            select(ScriptSegmentModel).where(ScriptSegmentModel.task_id == task_id).order_by(ScriptSegmentModel.index)
        ).all()
    )


def _add_artifact(db, task_id: str, artifact_type: ArtifactType, path: str, label: str, fmt: str) -> ArtifactModel:
    artifact = ArtifactModel(
        id=create_id("artifact"),
        task_id=task_id,
        type=artifact_type.value,
        path=path,
        meta={"label": label, "format": fmt},
        created_at=datetime.utcnow(),
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


def _avatar_adapter(task: TaskModel):
    if task.avatar_engine == AvatarEngine.tuilionnx.value:
        return TuiliONNXAdapter()
    return HeyGemAdapter()


@celery_app.task(name="tasks.transcribe_video")
def transcribe_video_task(task_id: str) -> None:
    with SessionLocal() as db:
        task = db.get(TaskModel, task_id)
        retryable_statuses = {TaskStatus.uploaded.value, TaskStatus.failed.value}
        if not task:
            return
        if task.status not in retryable_statuses:
            if task.status == TaskStatus.transcribing.value:
                logger.warning("transcribe_video_task skipped: task %s already transcribing", task_id)
            return
        if task.status == TaskStatus.failed.value:
            task.error_code = None
            task.error_message = None
            db.commit()
        try:
            _set_status(db, task, TaskStatus.transcribing)
            if not task.source_video_path:
                raise ValueError("视频识别任务缺少 source_video_path")

            local_video = resolve_local_video_path(task.id, task.source_video_path)
            task.source_video_path = local_video
            db.commit()
            db.refresh(task)

            # 同步参考视频产物路径，供前端预览与下载
            source_artifact = db.scalar(
                select(ArtifactModel).where(
                    ArtifactModel.task_id == task_id,
                    ArtifactModel.type == ArtifactType.source_video.value,
                )
            )
            if source_artifact:
                source_artifact.path = local_video
                db.commit()

            audio_path = FFmpegAdapter().extract_audio(task.id, local_video)
            _add_artifact(db, task_id, ArtifactType.audio, audio_path, "提取音频", "wav")
            _set_status(db, task, TaskStatus.audio_extracted)

            _set_status(db, task, TaskStatus.transcribing)
            raw_segments = WhisperAdapter().transcribe(audio_path, task.id)
            transcript_path = write_text(
                task_id,
                "intermediate/whisper_segments.json",
                json.dumps(raw_segments, ensure_ascii=False, indent=2),
            )
            _add_artifact(db, task_id, ArtifactType.transcript, transcript_path, "Whisper 识别结果", "json")

            new_segments: list[ScriptSegmentModel] = []
            next_index = 1
            for segment in raw_segments:
                text = str(segment.get("text") or "").strip()
                if not text:
                    continue
                new_segments.append(
                    ScriptSegmentModel(
                        id=create_id("seg"),
                        task_id=task_id,
                        index=next_index,
                        source_type=SegmentSource.whisper.value,
                        start_time=segment.get("start_time"),
                        end_time=segment.get("end_time"),
                        original_text=text,
                        edited_text=text,
                        confidence=segment.get("confidence"),
                    )
                )
                next_index += 1
            if not new_segments:
                raise ValueError("Whisper 未返回可用文案")

            db.query(ScriptSegmentModel).filter(ScriptSegmentModel.task_id == task_id).delete()
            for segment_model in new_segments:
                db.add(segment_model)
            duration = FFmpegAdapter().probe_duration(local_video)
            if duration:
                task.duration = duration
            task.status = TaskStatus.transcribed.value
            task.updated_at = datetime.utcnow()
            db.commit()
        except Exception as exc:
            task.status = TaskStatus.failed.value
            task.error_code = "TRANSCRIBE_FAILED"
            task.error_message = str(exc)
            db.commit()


@celery_app.task(name="tasks.run_generation_pipeline")
def run_generation_pipeline(task_id: str) -> None:
    with SessionLocal() as db:
        task = db.get(TaskModel, task_id)
        if not task:
            return
        if task.status not in GENERATION_PHASE_STATUSES:
            logger.warning(
                "run_generation_pipeline skipped: task %s status=%s",
                task_id,
                task.status,
            )
            return
        try:
            segments = _script_segments(db, task_id)
            script = "\n".join(segment.edited_text or segment.original_text for segment in segments)
            generation_quality = _resolve_generation_quality(task)
            _set_status(db, task, TaskStatus.dubbing)
            _set_pipeline(db, task, "dubbing", "正在生成配音", 35)

            dubbing_started = time.perf_counter()
            # 预设音色走 SFT（秒级）；克隆音色才传 custom_voice_path（cross_lingual，较慢）
            custom_voice = task.custom_voice_path
            if task.generation_voice_mode == GenerationVoiceMode.preset_voice.value:
                custom_voice = None
            audio_path = CozyVoiceAdapter().synthesize(
                task_id,
                script,
                task.voice_profile_id,
                custom_voice,
                task.custom_voice_prompt_text if custom_voice else None,
                task.voice_speed,
                generation_quality,
            )
            dubbing_ms = int((time.perf_counter() - dubbing_started) * 1000)
            _record_stage_timing(task, "dubbing", dubbing_ms)
            db.commit()
            db.refresh(task)
            _add_artifact(db, task_id, ArtifactType.tts_audio, audio_path, "AI 配音", "wav")

            _set_status(db, task, TaskStatus.dubbed)
            _set_status(db, task, TaskStatus.avatar_generating)
            _set_pipeline(db, task, "avatar_generating", "正在生成数字人口播", 55)
            avatar_started = time.perf_counter()
            avatar = _avatar_adapter(task)
            if task.avatar_engine == AvatarEngine.tuilionnx.value:
                base_video_path = avatar.generate_avatar_video(
                    task_id,
                    audio_path,
                    task.avatar_profile_id,
                    task.generation_video_mode,
                    task.custom_video_path,
                    generation_quality,
                    task.tuilionnx_sync_offset or 0,
                )
            else:
                base_video_path = avatar.generate_avatar_video(
                    task_id, audio_path, task.avatar_profile_id, task.generation_video_mode, task.custom_video_path
                )
            avatar_ms = int((time.perf_counter() - avatar_started) * 1000)
            _record_stage_timing(task, "avatar_generating", avatar_ms)
            db.commit()
            db.refresh(task)
            _add_artifact(db, task_id, ArtifactType.avatar_video, base_video_path, "数字人/自拍视频口播", "mp4")

            # TuiliONNX 口型驱动会产出与画面严格对齐的音频，成片必须使用它而非原始 TTS
            compose_audio_path = audio_path
            if task.avatar_engine == AvatarEngine.tuilionnx.value:
                synced_audio = Path(base_video_path).parent / "avatar_synced_audio.wav"
                if synced_audio.exists():
                    compose_audio_path = str(synced_audio)

            _set_status(db, task, TaskStatus.avatar_generated)
            _set_status(db, task, TaskStatus.subtitle_generating)
            _set_pipeline(db, task, "subtitle_generating", "正在生成字幕", 75)
            subtitle_started = time.perf_counter()
            ffmpeg = FFmpegAdapter()
            subtitle_path = ffmpeg.generate_subtitle(task_id, script, segments)
            subtitle_ms = int((time.perf_counter() - subtitle_started) * 1000)
            _record_stage_timing(task, "subtitle_generating", subtitle_ms)
            db.commit()
            db.refresh(task)
            _add_artifact(db, task_id, ArtifactType.subtitle, subtitle_path, "字幕文件", "srt")

            bgm_path = resolve_background_music_path(task.background_music_mode, task.background_music_path)

            _set_status(db, task, TaskStatus.composing)
            _set_pipeline(db, task, "composing", "正在合成最终视频", 90)
            compose_started = time.perf_counter()
            final_path = ffmpeg.compose_final(
                task_id,
                base_video_path,
                compose_audio_path,
                subtitle_path,
                bgm_path,
                task.background_music_volume,
                task.subtitle_style,
                task.aspect_ratio,
                bool(task.ai_watermark_enabled),
                bool(task.export_without_subtitle),
            )
            compose_ms = int((time.perf_counter() - compose_started) * 1000)
            _record_stage_timing(task, "composing", compose_ms)
            db.commit()
            db.refresh(task)
            _add_artifact(db, task_id, ArtifactType.final_video, final_path, "最终成片", "mp4")
            if task.export_without_subtitle:
                from app.core.config import get_settings

                no_sub = str(get_settings().storage_root / "tasks" / task_id / "output" / "final_no_subtitle.mp4")
                _add_artifact(db, task_id, ArtifactType.final_video_no_subtitle, no_sub, "无字幕成片", "mp4")

            task.status = TaskStatus.completed.value
            task.updated_at = datetime.utcnow()
            db.commit()
        except Exception as exc:
            task.status = TaskStatus.failed.value
            task.error_code = "GENERATION_FAILED"
            task.error_message = str(exc)
            task.updated_at = datetime.utcnow()
            db.commit()


@celery_app.task(name="tasks.generate_cover")
def generate_cover_task(task_id: str, payload: dict) -> None:
    with SessionLocal() as db:
        task = db.get(TaskModel, task_id)
        try:
            generate_cover(db, task_id, payload)
        except Exception as exc:
            if task:
                task.error_message = f"封面生成失败: {exc}"
                task.updated_at = datetime.utcnow()
                db.commit()


@celery_app.task(name="tasks.run_distribution")
def run_distribution_task(distribution_id: str) -> None:
    with SessionLocal() as db:
        record = db.get(DistributionRecordModel, distribution_id)
        if not record:
            return
        try:
            record.status = "running"
            record.updated_at = datetime.utcnow()
            db.commit()
            raw = record.raw_result or {}
            file_path = raw.get("final_video_path")
            if not file_path:
                raise ValueError("分发记录缺少最终视频路径")
            cover_path = None
            if record.cover_artifact_id:
                cover = db.get(ArtifactModel, record.cover_artifact_id)
                cover_path = cover.path if cover else None
            result = DistributorAdapter().upload_video(
                record.platform,
                file_path,
                record.title,
                record.description or "",
                record.tags,
                cover_path,
                bool(cover_path),
            )
            record.status = result.get("status", "failed")
            record.external_url = result.get("external_url")
            record.error_message = result.get("error_message")
            record.raw_result = result
            record.updated_at = datetime.utcnow()
            db.commit()
        except Exception as exc:
            record.status = "failed"
            record.error_message = str(exc)
            record.updated_at = datetime.utcnow()
            db.commit()


@celery_app.task(name="tasks.run_batch_distribution")
def run_batch_distribution_task(task_id: str, distribution_ids: list[str]) -> None:
    for distribution_id in distribution_ids:
        run_distribution_task.delay(distribution_id)


@celery_app.task(name="tasks.run_full_pipeline")
def run_full_pipeline_task(task_id: str, options: dict) -> None:
    """一键追爆款：转写 → 仿写 → 生成 → 封面 → 元信息 → 批量发布。"""
    transcribe_video_task(task_id)

    with SessionLocal() as db:
        task = db.get(TaskModel, task_id)
        if not task or task.status == TaskStatus.failed.value:
            return
        _set_pipeline(db, task, "transcribe", "文案识别完成", 20)

    if options.get("rewrite_enabled"):
        with SessionLocal() as db:
            rewrite_script(
                db,
                task_id,
                mode=options.get("rewrite_mode", "auto"),
                instruction=options.get("rewrite_instruction"),
                style=options.get("rewrite_style"),
            )
            task = db.get(TaskModel, task_id)
            if task:
                _set_pipeline(db, task, "rewrite", "文案仿写完成", 35)

    def _ensure_pipeline_script_ready(db) -> TaskModel | None:
        task = db.get(TaskModel, task_id)
        if not task or task.status in {TaskStatus.failed.value, TaskStatus.content_rejected.value}:
            return None
        if task.status == TaskStatus.script_confirmed.value:
            return task
        checks = get_risk_checks(db, task_id, RiskStage.script)
        if not checks:
            check_script_risk(db, task_id)
            task = db.get(TaskModel, task_id)
        if not task:
            return None
        if task.status == TaskStatus.content_review_required.value:
            _set_pipeline(db, task, "risk_check", "等待人工确认风险", 40)
            return None
        if task.status == TaskStatus.content_rejected.value:
            return None
        latest = get_risk_checks(db, task_id, RiskStage.script)
        latest_check = latest[0] if latest else None
        if not latest_check:
            return None
        if latest_check.risk_status == RiskStatus.blocked.value:
            task.status = TaskStatus.content_rejected.value
            task.updated_at = datetime.utcnow()
            db.commit()
            return None
        if latest_check.risk_status == RiskStatus.passed.value:
            confirm_script(db, task_id)
            return db.get(TaskModel, task_id)
        task.status = TaskStatus.content_review_required.value
        task.updated_at = datetime.utcnow()
        db.commit()
        _set_pipeline(db, task, "risk_check", "等待人工确认风险", 40)
        return None

    try:
        with SessionLocal() as db:
            task = _ensure_pipeline_script_ready(db)
            if not task:
                return
            if options.get("await_config"):
                _set_pipeline(db, task, "await_config", "请先上传音色并保存生成配置", 45)
                return
            if task.generation_voice_mode == GenerationVoiceMode.uploaded_voice.value and not task.custom_voice_path:
                _set_pipeline(db, task, "await_config", "请先上传音色并保存生成配置", 45)
                return
            if task.status != TaskStatus.script_confirmed.value:
                raise ValueError("文案尚未确认，无法继续一键生成")
            clear_generation_artifacts(db, task_id)
            task.status = TaskStatus.dubbing.value
            task.error_code = None
            task.error_message = None
            task.updated_at = datetime.utcnow()
            db.commit()

        run_generation_pipeline.run(task_id)

        with SessionLocal() as db:
            task = db.get(TaskModel, task_id)
            if not task or task.status != TaskStatus.completed.value:
                return
            _set_pipeline(db, task, "generate", "视频生成完成", 70)
    except Exception as exc:
        with SessionLocal() as db:
            task = db.get(TaskModel, task_id)
            if task:
                task.status = TaskStatus.failed.value
                task.error_code = "PIPELINE_FAILED"
                task.error_message = str(exc)
                task.updated_at = datetime.utcnow()
                db.commit()
        return

    if options.get("auto_generate_cover"):
        with SessionLocal() as db:
            script = _script_text(db, task_id)
            metadata = generate_publish_metadata(db, task_id) if options.get("auto_generate_metadata") else {}
            highlight_words = metadata.get("tags", [])[:3] if metadata else []
            generate_cover(
                db,
                task_id,
                {
                    "use_ai_copy": True,
                    "script": script,
                    "highlight_words": highlight_words,
                    "font_size": 72,
                    "highlight_color": "#FFD600",
                },
            )
            task = db.get(TaskModel, task_id)
            if task:
                _set_pipeline(db, task, "cover", "封面生成完成", 80)

    metadata = {}
    if options.get("auto_generate_metadata"):
        with SessionLocal() as db:
            metadata = generate_publish_metadata(db, task_id)

    platforms = options.get("publish_platforms") or []
    if platforms and metadata:
        with SessionLocal() as db:
            from app.services.distribution_service import create_batch_distributions

            ids = create_batch_distributions(
                db,
                task_id,
                platforms,
                metadata.get("title", "AI 数字人口播视频"),
                metadata.get("description", ""),
                metadata.get("tags", []),
                options.get("cover_artifact_id"),
            )
            run_batch_distribution_task.delay(task_id, ids)
            task = db.get(TaskModel, task_id)
            if task:
                _set_pipeline(db, task, "publish", "已提交多平台发布", 95)
