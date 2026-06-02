"""Celery 异步任务：转写、生成流水线、视频分发。

各任务通过 SessionLocal 独立开启 DB 会话，按 TaskStatus 状态机推进，
并调用 adapters 包中的 HTTP/CLI/Stub 适配器完成重计算步骤。
"""

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
    """更新任务状态并提交数据库。

    用途：
        流水线各阶段切换 TaskStatus，供 API 与前端展示进度。

    参数：
        db: SQLAlchemy 会话。
        task: 当前任务 ORM 对象。
        status: 目标枚举状态。

    返回：
        None（就地修改 task 并 commit）。
    """
    task.status = status.value
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)


def _script_text(db, task_id: str) -> str:
    """按 index 顺序拼接任务下所有分段的编辑后/原文案。

    参数：
        db: 数据库会话。
        task_id: 任务 ID。

    返回：
        换行分隔的完整脚本文本。
    """
    segments = db.scalars(
        select(ScriptSegmentModel).where(ScriptSegmentModel.task_id == task_id).order_by(ScriptSegmentModel.index)
    ).all()
    return "\n".join(segment.edited_text or segment.original_text for segment in segments)


def _script_segments(db, task_id: str) -> list[ScriptSegmentModel]:
    """查询任务下全部脚本分段（有序）。

    参数：
        db: 数据库会话。
        task_id: 任务 ID。

    返回：
        ScriptSegmentModel 列表。
    """
    return list(
        db.scalars(
            select(ScriptSegmentModel).where(ScriptSegmentModel.task_id == task_id).order_by(ScriptSegmentModel.index)
        ).all()
    )


def _add_artifact(db, task_id: str, artifact_type: ArtifactType, path: str, label: str, fmt: str) -> ArtifactModel:
    """登记任务产出物（音频、视频、字幕等）到 artifacts 表。

    用途：
        每完成一步适配器调用，持久化文件路径与元数据，供下载与审计。

    参数：
        db: 数据库会话。
        task_id: 所属任务 ID。
        artifact_type: 产出类型枚举。
        path: 文件绝对路径。
        label: 中文展示名。
        fmt: 文件格式（wav/mp4/srt 等）。

    返回：
        新创建的 ArtifactModel 实例。
    """
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
    """异步任务：从上传视频提取音频并用 Whisper 转写为脚本分段。

    用途：
        用户上传源视频并触发转写后，由 Celery Worker 执行本任务。

    参数：
        task_id: 任务主键。

    返回：
        None；结果写入 DB（ScriptSegment、Artifact、TaskStatus）。

    逻辑：
        1. 加载任务，若非 uploaded 状态则直接返回（幂等/防重入）。
        2. 状态 → transcribing；FFmpeg 抽轨 → 登记 audio 产出 → audio_extracted。
        3. 状态 → transcribing；Whisper 转写 → 保存 JSON 产出 → 删除旧分段。
        4. 按 Whisper 结果插入 ScriptSegmentModel（source=whisper）。
        5. 状态 → transcribed；异常时标记 failed + TRANSCRIBE_FAILED。
    """
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
    """异步任务：TTS → 数字人视频 → 字幕 → 合成成片。

    用途：
        用户确认脚本并启动生成后，串联 CosyVoice、HeyGem、FFmpeg 适配器。

    参数：
        task_id: 任务主键。

    返回：
        None；各阶段产出写入 artifacts，最终状态 completed 或 failed。

    逻辑：
        1. 加载任务与脚本分段，拼接 script 文本。
        2. dubbing：CozyVoice 合成 → tts_audio 产出 → dubbed。
        3. avatar_generating：HeyGem（或上传视频直通）→ avatar_video → avatar_generated。
        4. subtitle_generating：FFmpeg 生成 SRT → subtitle 产出。
        5. composing：FFmpeg 合成最终 mp4（含可选 BGM）→ final_video → completed。
        6. 异常时 failed + GENERATION_FAILED。
    """
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
    """异步任务：将成片上传到社交平台（B 站等）。

    用途：
        用户对已完成任务发起分发后，通过 DistributorAdapter（sau CLI）上传。

    参数：
        distribution_id: DistributionRecordModel 主键。

    返回：
        None；更新 record 的 status、external_url、error_message、raw_result。

    逻辑：
        1. 加载分发记录，不存在则返回。
        2. 状态 → running；从 raw_result 读取 final_video_path。
        3. 调用 DistributorAdapter.upload_video（平台、文件、标题、描述、标签）。
        4. 写回结果字段；异常时 status=failed 并记录 error_message。
    """
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
