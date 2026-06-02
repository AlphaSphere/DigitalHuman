"""
用途：API 层 Pydantic 模型（请求/响应 DTO），在路由与领域/ORM 之间做校验与序列化边界。
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


AspectRatio = Literal["9:16", "16:9", "1:1"]
ScriptGenerationMode = Literal["full_script", "timed_segments"]
RiskStage = Literal["input", "script", "audio", "avatar", "compose", "pre_publish"]


class SubtitleStyle(BaseModel):
    """用途：成片字幕样式配置，随生成参数保存并在合成阶段应用。"""

    enabled: bool
    font_size: int
    position: Literal["bottom", "middle", "top"] = "bottom"
    color: str
    stroke: bool = True


class TaskOut(BaseModel):
    """用途：任务详情 API 响应体，聚合状态、生成配置与错误信息。"""

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
    """用途：单条脚本片段的对外表示，含 ASR 原文与用户编辑稿。"""

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
    """用途：批量更新片段请求中的单条项，edited_text 为必填提交内容。"""

    id: str | None = None
    index: int
    start_time: float | None = None
    end_time: float | None = None
    original_text: str | None = None
    edited_text: str


class UpdateSegmentsRequest(BaseModel):
    """用途：用户确认/编辑脚本后提交的整体请求，含生成模式与片段列表。"""

    script_generation_mode: ScriptGenerationMode = "full_script"
    segments: list[SegmentUpdate]


class CreateScriptTaskRequest(BaseModel):
    """用途：从粘贴文案创建任务的入参，跳过视频 ASR 路径。"""

    content: str = Field(min_length=1, max_length=5000)
    content_type: Literal["pasted_subtitle", "pasted_script"] = "pasted_script"
    aspect_ratio: AspectRatio = "9:16"


class SaveGenerationConfigRequest(BaseModel):
    """用途：文案确认后保存 TTS/数字人/字幕/背景音乐等生成配置。"""

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
    """用途：风控命中明细的 API 输出。"""

    id: str
    type: str
    target: str
    text: str | None = None
    position: str | None = None
    suggestion: str | None = None


class RiskCheckOut(BaseModel):
    """用途：某阶段一次完整风控检查的结果，含 findings 列表。"""

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
    """用途：用户在人工复核节点确认继续或附注的请求体。"""

    confirmed: bool = True
    confirmation_note: str


class ArtifactOut(BaseModel):
    """用途：任务关联产物（文件）的元信息与存储路径。"""

    id: str
    task_id: str
    type: str
    path: str | None = None
    meta: dict[str, Any]
    created_at: datetime


class VoiceProfileOut(BaseModel):
    """用途：可选音色预设的对外结构。"""

    id: str
    name: str
    provider: Literal["cozyvoice"]
    sample_path: str | None = None
    config: dict[str, Any]


class AvatarProfileOut(BaseModel):
    """用途：可选数字人形象的对外结构。"""

    id: str
    name: str
    provider: Literal["heygem"]
    config: dict[str, Any]


class PrePublishCheckInput(BaseModel):
    """用途：发布前合规检查所需的标题、标签与平台信息。"""

    platform: Literal["douyin", "xiaohongshu", "bilibili", "wechat_channels", "kuaishou", "tiktok", "youtube"]
    title: str
    description: str
    tags: list[str]
    ai_label_confirmed: bool
    cover_artifact_id: str | None = None


class MusicTrackOut(BaseModel):
    """用途：背景音乐库中单曲的展示与路径信息。"""

    id: str
    name: str
    path: str
    source: str = "CC0-1.0 Music"
    duration: float | None = None


class CreateDistributionRequest(BaseModel):
    """用途：创建向指定平台分发成片的请求参数。"""

    platform: Literal["douyin", "xiaohongshu", "bilibili", "wechat_channels", "kuaishou", "tiktok", "youtube"]
    title: str = Field(min_length=1, max_length=100)
    description: str = ""
    tags: list[str] = []


class DistributionRecordOut(BaseModel):
    """用途：分发任务的状态与平台链接查询响应。"""

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
