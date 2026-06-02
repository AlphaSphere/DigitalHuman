import json
from datetime import datetime

from sqlalchemy import select

from app.adapters.cozyvoice import CozyVoiceAdapter
from app.adapters.distributor import DistributorAdapter
from app.adapters.ffmpeg import FFmpegAdapter
from app.adapters.heygem import HeyGemAdapter
from app.adapters.whisper import WhisperAdapter
from app.db.models import ArtifactModel, DistributionRecordModel, ScriptSegmentModel, TaskModel
from app.db.session import SessionLocal
from app.domain.enums import ArtifactType, SegmentSource, TaskStatus
from app.services.id_service import create_id
from app.services.storage_service import write_text
from app.workers.celery_app import celery_app


def _set_status(db, task: TaskModel, status: TaskStatus) -> None:
    task.status = status.value
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)


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


@celery_app.task(name="tasks.transcribe_video")
def transcribe_video_task(task_id: str) -> None:
    with SessionLocal() as db:
        task = db.get(TaskModel, task_id)
        if not task or task.status != TaskStatus.uploaded.value:
            return
        try:
            _set_status(db, task, TaskStatus.transcribing)
            if not task.source_video_path:
                raise ValueError("视频识别任务缺少 source_video_path")
            audio_path = FFmpegAdapter().extract_audio(task.id, task.source_video_path)
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
            db.query(ScriptSegmentModel).filter(ScriptSegmentModel.task_id == task_id).delete()
            for index, segment in enumerate(raw_segments, start=1):
                text = segment["text"]
                db.add(
                    ScriptSegmentModel(
                        id=create_id("seg"),
                        task_id=task_id,
                        index=index,
                        source_type=SegmentSource.whisper.value,
                        start_time=segment.get("start_time"),
                        end_time=segment.get("end_time"),
                        original_text=text,
                        edited_text=text,
                        confidence=segment.get("confidence"),
                    )
                )
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
        try:
            segments = _script_segments(db, task_id)
            script = "\n".join(segment.edited_text or segment.original_text for segment in segments)
            _set_status(db, task, TaskStatus.dubbing)
            audio_path = CozyVoiceAdapter().synthesize(task_id, script, task.voice_profile_id, task.custom_voice_path)
            _add_artifact(db, task_id, ArtifactType.tts_audio, audio_path, "AI 配音", "wav")

            _set_status(db, task, TaskStatus.dubbed)
            _set_status(db, task, TaskStatus.avatar_generating)
            base_video_path = HeyGemAdapter().generate_avatar_video(
                task_id, audio_path, task.avatar_profile_id, task.generation_video_mode, task.custom_video_path
            )
            _add_artifact(db, task_id, ArtifactType.avatar_video, base_video_path, "数字人/自拍视频口播", "mp4")

            _set_status(db, task, TaskStatus.avatar_generated)
            _set_status(db, task, TaskStatus.subtitle_generating)
            ffmpeg = FFmpegAdapter()
            subtitle_path = ffmpeg.generate_subtitle(task_id, script, segments)
            _add_artifact(db, task_id, ArtifactType.subtitle, subtitle_path, "字幕文件", "srt")

            _set_status(db, task, TaskStatus.composing)
            final_path = ffmpeg.compose_final(
                task_id,
                base_video_path,
                audio_path,
                subtitle_path,
                task.background_music_path,
                task.background_music_volume,
            )
            _add_artifact(db, task_id, ArtifactType.final_video, final_path, "最终成片", "mp4")

            task.status = TaskStatus.completed.value
            task.updated_at = datetime.utcnow()
            db.commit()
        except Exception as exc:
            task.status = TaskStatus.failed.value
            task.error_code = "GENERATION_FAILED"
            task.error_message = str(exc)
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
            file_path = (record.raw_result or {}).get("final_video_path")
            if not file_path:
                raise ValueError("分发记录缺少最终视频路径")
            result = DistributorAdapter().upload_video(
                record.platform,
                file_path,
                record.title,
                record.description or "",
                record.tags,
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
