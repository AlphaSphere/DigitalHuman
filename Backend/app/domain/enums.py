from enum import StrEnum


class ScriptSource(StrEnum):
    video_asr = "video_asr"
    pasted_subtitle = "pasted_subtitle"
    pasted_script = "pasted_script"


class TaskStatus(StrEnum):
    uploaded = "uploaded"
    audio_extracted = "audio_extracted"
    transcribing = "transcribing"
    transcribed = "transcribed"
    script_pasted = "script_pasted"
    script_parsing = "script_parsing"
    script_parsed = "script_parsed"
    script_confirmed = "script_confirmed"
    content_checking = "content_checking"
    content_review_required = "content_review_required"
    content_rejected = "content_rejected"
    dubbing = "dubbing"
    dubbed = "dubbed"
    avatar_generating = "avatar_generating"
    avatar_generated = "avatar_generated"
    subtitle_generating = "subtitle_generating"
    composing = "composing"
    publish_checking = "publish_checking"
    publish_blocked = "publish_blocked"
    publish_ready = "publish_ready"
    completed = "completed"
    failed = "failed"
    retrying = "retrying"


class SegmentSource(StrEnum):
    whisper = "whisper"
    pasted_subtitle = "pasted_subtitle"
    pasted_script = "pasted_script"
    manual_edit = "manual_edit"


class ScriptGenerationMode(StrEnum):
    full_script = "full_script"
    timed_segments = "timed_segments"


class ArtifactType(StrEnum):
    source_video = "source_video"
    audio = "audio"
    transcript = "transcript"
    confirmed_script = "confirmed_script"
    timeline = "timeline"
    tts_audio = "tts_audio"
    avatar_video = "avatar_video"
    subtitle = "subtitle"
    final_video = "final_video"


class AspectRatio(StrEnum):
    portrait = "9:16"
    landscape = "16:9"
    square = "1:1"


class GenerationVoiceMode(StrEnum):
    uploaded_voice = "uploaded_voice"
    preset_voice = "preset_voice"


class GenerationVideoMode(StrEnum):
    uploaded_video = "uploaded_video"
    preset_avatar = "preset_avatar"


class RiskStatus(StrEnum):
    passed = "passed"
    warning = "warning"
    blocked = "blocked"
    manual_review = "manual_review"


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class RiskStage(StrEnum):
    input = "input"
    script = "script"
    audio = "audio"
    avatar = "avatar"
    compose = "compose"
    pre_publish = "pre_publish"


class RiskType(StrEnum):
    copyright = "copyright"
    portrait = "portrait"
    voice = "voice"
    sensitive_keyword = "sensitive_keyword"
    privacy = "privacy"
    platform_rule = "platform_rule"


class ReviewedBy(StrEnum):
    system = "system"
    user = "user"
    admin = "admin"


class AuthorizationAssetType(StrEnum):
    video = "video"
    script = "script"
    voice = "voice"
    avatar = "avatar"
    image = "image"


class AuthorizationSource(StrEnum):
    user_upload = "user_upload"
    preset = "preset"
    third_party = "third_party"
