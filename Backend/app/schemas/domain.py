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
    # 字幕字体系列，默认 SimHei（黑体），支持系统已安装的中文字体
    font_family: str = "SimHei"


class TaskOut(BaseModel):
    """用途：任务详情 API 响应体，聚合状态、生成配置与错误信息。"""

    id: str
    script_source: str
    script_generation_mode: str | None = None
    status: str
    source_video_path: str | None = None
    source_url: str | None = None
    duration: float | None = None
    aspect_ratio: str | None = None
    pipeline_mode: str | None = None
    pipeline_stage: dict[str, Any] | None = None
    generation_voice_mode: str | None = None
    custom_voice_path: str | None = None
    custom_voice_prompt_text: str | None = None
    generation_video_mode: str | None = None
    custom_video_path: str | None = None
    voice_profile_id: str | None = None
    avatar_profile_id: str | None = None
    subtitle_style: SubtitleStyle | None = None
    voice_speed: float | None = None
    background_music_path: str | None = None
    background_music_mode: str | None = None
    background_music_volume: float | None = None
    ai_watermark_enabled: bool | None = None
    export_without_subtitle: bool | None = None
    avatar_engine: str | None = None
    generation_quality: Literal["fast", "full"] | None = None
    tuilionnx_sync_offset: int | None = None
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
    custom_voice_prompt_text: str | None = Field(default=None, max_length=500)
    generation_video_mode: Literal["uploaded_video", "preset_avatar", "tuilionnx_avatar"]
    custom_video_file_name: str | None = None
    authorization_confirmed: bool = False
    aspect_ratio: AspectRatio = "9:16"
    subtitle_style: SubtitleStyle
    background_music_path: str | None = None
    background_music_mode: Literal["none", "fixed", "random"] = "fixed"
    background_music_volume: float = Field(default=0.18, ge=0, le=1)
    voice_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    ai_watermark_enabled: bool = False
    export_without_subtitle: bool = False
    avatar_engine: Literal["heygem", "tuilionnx"] = "heygem"
    generation_quality: Literal["fast", "full"] = "full"
    tuilionnx_sync_offset: int = Field(default=0, ge=-10, le=10)


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


class ConfirmScriptRequest(BaseModel):
    """用途：确认文案并进入配置页；warning/manual_review 时可附带确认说明。"""

    confirmation_note: str | None = None


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
    cover_artifact_id: str | None = None


class BatchDistributionRequest(BaseModel):
    """批量多平台分发。"""

    platforms: list[
        Literal["douyin", "xiaohongshu", "bilibili", "wechat_channels", "kuaishou", "tiktok", "youtube"]
    ]
    title: str = Field(min_length=1, max_length=100)
    description: str = ""
    tags: list[str] = []
    cover_artifact_id: str | None = None


class RewriteScriptRequest(BaseModel):
    mode: Literal["auto", "instruction"] = "auto"
    instruction: str | None = None
    style: Literal["viral_spoken", "formal", "humorous", "custom"] | None = "viral_spoken"


class GeneratePublishMetadataRequest(BaseModel):
    platform: str | None = None
    tone: Literal["viral", "professional", "casual"] = "viral"


class GenerateCoverRequest(BaseModel):
    cover_text: str = ""
    highlight_words: list[str] = []
    frame_path: str | None = None
    font_size: int = 60
    font_color: str = "#FFFFFF"
    highlight_color: str = "#FFD600"
    position: Literal["top", "center", "bottom"] = "bottom"
    use_ai_copy: bool = False
    script: str | None = None


class OneClickPipelineRequest(BaseModel):
    source_url: str | None = None
    aspect_ratio: AspectRatio = "9:16"
    rewrite_enabled: bool = True
    rewrite_mode: Literal["auto", "instruction"] = "auto"
    rewrite_instruction: str | None = None
    rewrite_style: Literal["viral_spoken", "formal", "humorous", "custom"] | None = "viral_spoken"
    generation_preset: SaveGenerationConfigRequest | None = None
    publish_platforms: list[str] = []
    auto_generate_metadata: bool = True
    auto_generate_cover: bool = False
    auto_confirm_risk: bool = False
    voice_speed: float = 1.0
    background_music_mode: Literal["none", "fixed", "random"] = "random"
    ai_watermark_enabled: bool = True
    export_without_subtitle: bool = False
    avatar_engine: Literal["heygem", "tuilionnx"] = "heygem"
    generation_quality: Literal["fast", "full"] = "fast"
    generation_voice_mode: Literal["uploaded_voice", "preset_voice"] | None = None
    require_config_before_generate: bool = True
    cover_artifact_id: str | None = None


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
