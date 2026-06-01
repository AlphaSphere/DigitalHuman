from app.db.models import (
    ArtifactModel,
    AvatarProfileModel,
    RiskCheckModel,
    RiskFindingModel,
    ScriptSegmentModel,
    TaskModel,
    VoiceProfileModel,
)


def task_to_dict(task: TaskModel) -> dict:
    return {
        "id": task.id,
        "script_source": task.script_source,
        "script_generation_mode": task.script_generation_mode,
        "status": task.status,
        "source_video_path": task.source_video_path,
        "duration": task.duration,
        "aspect_ratio": task.aspect_ratio,
        "generation_voice_mode": task.generation_voice_mode,
        "custom_voice_path": task.custom_voice_path,
        "generation_video_mode": task.generation_video_mode,
        "custom_video_path": task.custom_video_path,
        "voice_profile_id": task.voice_profile_id,
        "avatar_profile_id": task.avatar_profile_id,
        "subtitle_style": task.subtitle_style,
        "error_code": task.error_code,
        "error_message": task.error_message,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def segment_to_dict(segment: ScriptSegmentModel) -> dict:
    return {
        "id": segment.id,
        "task_id": segment.task_id,
        "index": segment.index,
        "source_type": segment.source_type,
        "start_time": segment.start_time,
        "end_time": segment.end_time,
        "original_text": segment.original_text,
        "edited_text": segment.edited_text,
        "confidence": segment.confidence,
    }


def artifact_to_dict(artifact: ArtifactModel) -> dict:
    return {
        "id": artifact.id,
        "task_id": artifact.task_id,
        "type": artifact.type,
        "path": artifact.path,
        "meta": artifact.meta,
        "created_at": artifact.created_at,
    }


def finding_to_dict(finding: RiskFindingModel) -> dict:
    return {
        "id": finding.id,
        "type": finding.type,
        "target": finding.target,
        "text": finding.text,
        "position": finding.position,
        "suggestion": finding.suggestion,
    }


def risk_check_to_dict(risk_check: RiskCheckModel) -> dict:
    return {
        "id": risk_check.id,
        "task_id": risk_check.task_id,
        "stage": risk_check.stage,
        "risk_status": risk_check.risk_status,
        "risk_level": risk_check.risk_level,
        "risk_types": risk_check.risk_types,
        "findings": [finding_to_dict(finding) for finding in risk_check.findings],
        "reviewed_by": risk_check.reviewed_by,
        "reviewed_at": risk_check.reviewed_at,
        "created_at": risk_check.created_at,
    }


def voice_profile_to_dict(voice: VoiceProfileModel) -> dict:
    return {
        "id": voice.id,
        "name": voice.name,
        "provider": voice.provider,
        "sample_path": voice.sample_path,
        "config": voice.config,
    }


def avatar_profile_to_dict(avatar: AvatarProfileModel) -> dict:
    return {"id": avatar.id, "name": avatar.name, "provider": avatar.provider, "config": avatar.config}
