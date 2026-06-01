from datetime import datetime

from sqlalchemy import select

from app.adapters.cozyvoice import CozyVoiceAdapter
from app.adapters.ffmpeg import FFmpegAdapter
from app.adapters.heygem import HeyGemAdapter
from app.adapters.whisper import WhisperAdapter
from app.db.models import ArtifactModel, ScriptSegmentModel, TaskModel
from app.db.session import SessionLocal
from app.domain.enums import ArtifactType, SegmentSource, TaskStatus
from app.services.id_service import create_id
from app.services.script_parser import build_segments
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
            raw_segments = WhisperAdapter().transcribe(task.source_video_path)
            db.query(ScriptSegmentModel).filter(ScriptSegmentModel.task_id == task_id).delete()
            content = "\n".join(segment["text"] for segment in raw_segments)
            for item in build_segments(task_id, SegmentSource.whisper, content):
                db.add(ScriptSegmentModel(**item))
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
            script = _script_text(db, task_id)
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
            subtitle_path = FFmpegAdapter().generate_subtitle(task_id, script)
            _add_artifact(db, task_id, ArtifactType.subtitle, subtitle_path, "字幕文件", "srt")

            _set_status(db, task, TaskStatus.composing)
            final_path = FFmpegAdapter().compose_final(task_id, base_video_path, audio_path, subtitle_path)
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
