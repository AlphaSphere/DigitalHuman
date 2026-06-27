"""
用途：数字人任务流水线中的领域枚举定义，作为状态机、风控阶段与产物类型的唯一字符串来源。
"""

from enum import StrEnum


class ScriptSource(StrEnum):
    """用途：标识任务文案的来源渠道，决定后续 ASR 或粘贴解析分支。"""

    video_asr = "video_asr"
    pasted_subtitle = "pasted_subtitle"
    pasted_script = "pasted_script"


class TaskStatus(StrEnum):
    """用途：任务主状态机节点，贯穿上传、识别、生成、合规与成片全流程。"""

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
    """用途：单条脚本片段的产出方式，用于审计与重跑策略。"""

    whisper = "whisper"
    pasted_subtitle = "pasted_subtitle"
    pasted_script = "pasted_script"
    manual_edit = "manual_edit"


class ScriptGenerationMode(StrEnum):
    """用途：生成阶段按整段脚本还是按时间轴分段驱动 TTS/口播。"""

    full_script = "full_script"
    timed_segments = "timed_segments"


class ArtifactType(StrEnum):
    """用途：任务关联中间产物与成片的类型标签，供存储与下载 API 过滤。"""

    source_video = "source_video"
    audio = "audio"
    transcript = "transcript"
    confirmed_script = "confirmed_script"
    timeline = "timeline"
    tts_audio = "tts_audio"
    avatar_video = "avatar_video"
    subtitle = "subtitle"
    final_video = "final_video"
    final_video_no_subtitle = "final_video_no_subtitle"
    cover = "cover"


class AspectRatio(StrEnum):
    """用途：视频画幅比例，影响数字人模板与合成参数。"""

    portrait = "9:16"
    landscape = "16:9"
    square = "1:1"


class GenerationVoiceMode(StrEnum):
    """用途：配音使用用户上传样本还是系统预设音色。"""

    uploaded_voice = "uploaded_voice"
    preset_voice = "preset_voice"


class GenerationVideoMode(StrEnum):
    """用途：口播视频使用用户上传素材还是预设数字人形象。"""

    uploaded_video = "uploaded_video"
    preset_avatar = "preset_avatar"
    tuilionnx_avatar = "tuilionnx_avatar"


class BackgroundMusicMode(StrEnum):
    """用途：背景音乐选择策略。"""

    none = "none"
    fixed = "fixed"
    random = "random"


class PipelineMode(StrEnum):
    """用途：任务执行模式（分步向导或一键追爆款）。"""

    stepwise = "stepwise"
    one_click = "one_click"


class AvatarEngine(StrEnum):
    """用途：数字人生成引擎。"""

    heygem = "heygem"
    tuilionnx = "tuilionnx"


class GenerationQuality(StrEnum):
    """用途：成片生成质量档位（快速预览 vs 完整成片）。"""

    fast = "fast"
    full = "full"


class RiskStatus(StrEnum):
    """用途：单次风控检查的结论状态，驱动任务是否可继续或需人工确认。"""

    passed = "passed"
    warning = "warning"
    blocked = "blocked"
    manual_review = "manual_review"


class RiskLevel(StrEnum):
    """用途：风险严重度分级，用于前端展示与拦截策略。"""

    low = "low"
    medium = "medium"
    high = "high"


class RiskStage(StrEnum):
    """用途：风控发生的流水线阶段，与 TaskStatus 中检查节点对应。"""

    input = "input"
    script = "script"
    audio = "audio"
    avatar = "avatar"
    compose = "compose"
    pre_publish = "pre_publish"


class RiskType(StrEnum):
    """用途：具体风险类别，便于聚合统计与给出修改建议。"""

    copyright = "copyright"
    portrait = "portrait"
    voice = "voice"
    sensitive_keyword = "sensitive_keyword"
    privacy = "privacy"
    platform_rule = "platform_rule"


class ReviewedBy(StrEnum):
    """用途：风控记录的确认主体（系统自动、用户、管理员或 DeepSeek AI）。"""

    system = "system"
    user = "user"
    admin = "admin"
    deepseek = "deepseek"


class AuthorizationAssetType(StrEnum):
    """用途：用户授权确认所针对的资产类型（视频、文案、声音等）。"""

    video = "video"
    script = "script"
    voice = "voice"
    avatar = "avatar"
    image = "image"


class AuthorizationSource(StrEnum):
    """用途：被授权资产的来源分类，满足合规留痕。"""

    user_upload = "user_upload"
    preset = "preset"
    third_party = "third_party"
