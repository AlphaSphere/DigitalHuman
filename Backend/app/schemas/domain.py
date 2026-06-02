from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


AspectRatio = Literal["9:16", "16:9", "1:1"]
ScriptGenerationMode = Literal["full_script", "timed_segments"]
RiskStage = Literal["input", "script", "audio", "avatar", "compose", "pre_publish"]


class SubtitleStyle(BaseModel):
    enabled: bool
    font_size: int
    position: Literal["bottom", "middle", "top"] = "bottom"
    color: str
    stroke: bool = True


class TaskOut(BaseModel):
    id: str
    script_source: str
    script_generation_mode: str | None = None
    status: str
    source_video_path: str | None = None
    duration: float | None = None
    aspect_ratio: str | None = None
    generation_voice_mode: str | None = None
    custom_voice_path: str | None = None
    generation_video_mode: str | None = None
    custom_video_path: str | None = None
    voice_profile_id: str | None = None
    avatar_profile_id: str | None = None
    subtitle_style: SubtitleStyle | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ScriptSegmentOut(BaseModel):
    id: str
    task_id: str
    index: int
    source_type: str
    start_time: float | None = None
    end_time: float | None = None
    original_text: str
    edited_text: str | None = None
    confidence: float | None = None


class SegmentUpdate(BaseModel):
    id: str | None = None
    index: int
    start_time: float | None = None
    end_time: float | None = None
    original_text: str | None = None
    edited_text: str


class UpdateSegmentsRequest(BaseModel):
    script_generation_mode: ScriptGenerationMode = "full_script"
    segments: list[SegmentUpdate]


class CreateScriptTaskRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    content_type: Literal["pasted_subtitle", "pasted_script"] = "pasted_script"
    aspect_ratio: AspectRatio = "9:16"


class SaveGenerationConfigRequest(BaseModel):
    voice_profile_id: str
    avatar_profile_id: str
    generation_voice_mode: Literal["uploaded_voice", "preset_voice"]
    custom_voice_file_name: str | None = None
    generation_video_mode: Literal["uploaded_video", "preset_avatar"]
    custom_video_file_name: str | None = None
    authorization_confirmed: bool = False
    aspect_ratio: AspectRatio = "9:16"
    subtitle_style: SubtitleStyle
    background_music_path: str | None = None
    background_music_volume: float = Field(default=0.18, ge=0, le=1)


class RiskFindingOut(BaseModel):
    id: str
    type: str
    target: str
    text: str | None = None
    position: str | None = None
    suggestion: str | None = None


class RiskCheckOut(BaseModel):
    id: str
    task_id: str
    stage: str
    risk_status: str
    risk_level: str
    risk_types: list[str]
    findings: list[RiskFindingOut]
    reviewed_by: str
    reviewed_at: datetime | None = None
    created_at: datetime


class ConfirmRiskRequest(BaseModel):
    confirmed: bool = True
    confirmation_note: str


class ArtifactOut(BaseModel):
    id: str
    task_id: str
    type: str
    path: str | None = None
    meta: dict[str, Any]
    created_at: datetime


class VoiceProfileOut(BaseModel):
    id: str
    name: str
    provider: Literal["cozyvoice"]
    sample_path: str | None = None
    config: dict[str, Any]


class AvatarProfileOut(BaseModel):
    id: str
    name: str
    provider: Literal["heygem"]
    config: dict[str, Any]


class PrePublishCheckInput(BaseModel):
    platform: Literal["douyin", "xiaohongshu", "bilibili", "wechat_channels", "kuaishou", "tiktok", "youtube"]
    title: str
    description: str
    tags: list[str]
    ai_label_confirmed: bool
    cover_artifact_id: str | None = None


class MusicTrackOut(BaseModel):
    id: str
    name: str
    path: str
    source: str = "CC0-1.0 Music"
    duration: float | None = None


class CreateDistributionRequest(BaseModel):
    platform: Literal["douyin", "xiaohongshu", "bilibili", "wechat_channels", "kuaishou", "tiktok", "youtube"]
    title: str = Field(min_length=1, max_length=100)
    description: str = ""
    tags: list[str] = []


class DistributionRecordOut(BaseModel):
    id: str
    task_id: str
    platform: str
    title: str
    description: str | None = None
    tags: list[str]
    status: str
    external_url: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
