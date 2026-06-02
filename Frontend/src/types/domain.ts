/**
 * 用途：定义数字人口播工作台前端与后端共享的领域类型与接口形状。
 */

/** 文案来源：视频 ASR、粘贴字幕或粘贴口播稿。 */
export type ScriptSource = 'video_asr' | 'pasted_subtitle' | 'pasted_script'

/** 任务生命周期状态，覆盖上传、识别、生成、发布与失败重试全链路。 */
export type TaskStatus =
  | 'uploaded'
  | 'audio_extracted'
  | 'transcribing'
  | 'transcribed'
  | 'script_pasted'
  | 'script_parsing'
  | 'script_parsed'
  | 'script_confirmed'
  | 'content_checking'
  | 'content_review_required'
  | 'content_rejected'
  | 'dubbing'
  | 'dubbed'
  | 'avatar_generating'
  | 'avatar_generated'
  | 'subtitle_generating'
  | 'composing'
  | 'publish_checking'
  | 'publish_blocked'
  | 'publish_ready'
  | 'completed'
  | 'failed'
  | 'retrying'

/** 文案段落来源：Whisper、粘贴或人工编辑。 */
export type SegmentSource = 'whisper' | 'pasted_subtitle' | 'pasted_script' | 'manual_edit'

/** 文案生成模式：整段口播或按时间轴分段。 */
export type ScriptGenerationMode = 'full_script' | 'timed_segments'

/** 任务产物类型：源视频、音频、字幕、成片等。 */
export type ArtifactType =
  | 'source_video'
  | 'audio'
  | 'transcript'
  | 'confirmed_script'
  | 'timeline'
  | 'tts_audio'
  | 'avatar_video'
  | 'subtitle'
  | 'final_video'

/** 输出视频宽高比。 */
export type AspectRatio = '9:16' | '16:9' | '1:1'

/** 配音素材模式：上传音色或预设音色。 */
export type GenerationVoiceMode = 'uploaded_voice' | 'preset_voice'

/** 成片素材模式：上传自拍视频或预设数字人。 */
export type GenerationVideoMode = 'uploaded_video' | 'preset_avatar'

/**
 * 字幕样式配置。
 */
export interface SubtitleStyle {
  enabled: boolean
  font_size: number
  position: 'bottom' | 'middle' | 'top'
  color: string
  stroke: boolean
}

/**
 * 数字人视频生成任务实体。
 */
export interface Task {
  id: string
  script_source: ScriptSource
  script_generation_mode?: ScriptGenerationMode | null
  status: TaskStatus
  source_video_path?: string | null
  duration?: number | null
  aspect_ratio?: AspectRatio
  generation_voice_mode?: GenerationVoiceMode | null
  custom_voice_path?: string | null
  generation_video_mode?: GenerationVideoMode | null
  custom_video_path?: string | null
  voice_profile_id?: string | null
  avatar_profile_id?: string | null
  subtitle_style?: SubtitleStyle | null
  background_music_path?: string | null
  background_music_volume?: number | null
  error_code?: string | null
  error_message?: string | null
  created_at: string
  updated_at: string
}

/**
 * 单段口播/字幕文案，含时间轴与编辑态文本。
 */
export interface ScriptSegment {
  id: string
  task_id: string
  index: number
  source_type: SegmentSource
  start_time?: number | null
  end_time?: number | null
  original_text: string
  edited_text?: string | null
  confidence?: number | null
}

/**
 * 预设音色配置（CosyVoice 提供方）。
 */
export interface VoiceProfile {
  id: string
  name: string
  provider: 'cozyvoice'
  sample_path?: string
  config: {
    speed: number
    volume: number
    description?: string
  }
}

/**
 * 预设数字人形象配置（HeyGem 提供方）。
 */
export interface AvatarProfile {
  id: string
  name: string
  provider: 'heygem'
  config: {
    resolution: string
    template_path: string
    description?: string
  }
}

/**
 * 任务中间或最终产物元数据。
 */
export interface Artifact {
  id: string
  task_id: string
  type: ArtifactType
  path?: string
  meta: {
    duration?: number
    format?: string
    size_bytes?: number
    label?: string
  }
  created_at: string
}

/**
 * 任务进度展示结构，供进度页 UI 使用。
 */
export interface TaskProgress {
  stage: TaskStatus
  percent: number
  message: string
}

/** 风险检查结论：通过、警告、阻断或需人工复核。 */
export type RiskStatus = 'passed' | 'warning' | 'blocked' | 'manual_review'

/** 风险严重等级。 */
export type RiskLevel = 'low' | 'medium' | 'high'

/** 风险检查所处流水线阶段。 */
export type RiskStage = 'input' | 'script' | 'audio' | 'avatar' | 'compose' | 'pre_publish'

/** 风险类型分类。 */
export type RiskType = 'copyright' | 'portrait' | 'voice' | 'sensitive_keyword' | 'privacy' | 'platform_rule'

/**
 * 单条风险命中详情。
 */
export interface RiskFinding {
  id: string
  type: RiskType
  target: string
  text?: string
  position?: string
  suggestion?: string
}

/**
 * 一次完整的风险检查结果。
 */
export interface RiskCheck {
  id: string
  task_id: string
  stage: RiskStage
  risk_status: RiskStatus
  risk_level: RiskLevel
  risk_types: RiskType[]
  findings: RiskFinding[]
  reviewed_by: 'system' | 'user' | 'admin'
  reviewed_at?: string | null
  created_at: string
}

/**
 * 用户素材授权确认记录。
 */
export interface AuthorizationRecord {
  id: string
  task_id: string
  asset_type: 'video' | 'script' | 'voice' | 'avatar' | 'image'
  source: 'user_upload' | 'preset' | 'third_party'
  authorization_confirmed: boolean
  authorization_note?: string
  confirmed_at: string
}

/**
 * 发布前合规检查表单输入。
 */
export interface PrePublishCheckInput {
  platform: 'douyin' | 'xiaohongshu' | 'bilibili' | 'wechat_channels' | 'kuaishou' | 'tiktok' | 'youtube'
  title: string
  description: string
  tags: string[]
  ai_label_confirmed: boolean
  cover_artifact_id?: string
}

/**
 * 可选背景音乐曲目。
 */
export interface MusicTrack {
  id: string
  name: string
  path: string
  source: string
  duration?: number | null
}

/**
 * 平台分发任务记录。
 */
export interface DistributionRecord {
  id: string
  task_id: string
  platform: PrePublishCheckInput['platform']
  title: string
  description?: string | null
  tags: string[]
  status: 'pending' | 'running' | 'success' | 'failed'
  external_url?: string | null
  error_message?: string | null
  created_at: string
  updated_at: string
}
