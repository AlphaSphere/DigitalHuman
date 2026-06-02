export type ScriptSource = 'video_asr' | 'pasted_subtitle' | 'pasted_script'

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

export type SegmentSource = 'whisper' | 'pasted_subtitle' | 'pasted_script' | 'manual_edit'

export type ScriptGenerationMode = 'full_script' | 'timed_segments'

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

export type AspectRatio = '9:16' | '16:9' | '1:1'

export type GenerationVoiceMode = 'uploaded_voice' | 'preset_voice'

export type GenerationVideoMode = 'uploaded_video' | 'preset_avatar'

export interface SubtitleStyle {
  enabled: boolean
  font_size: number
  position: 'bottom' | 'middle' | 'top'
  color: string
  stroke: boolean
}

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

export interface TaskProgress {
  stage: TaskStatus
  percent: number
  message: string
}

export type RiskStatus = 'passed' | 'warning' | 'blocked' | 'manual_review'

export type RiskLevel = 'low' | 'medium' | 'high'

export type RiskStage = 'input' | 'script' | 'audio' | 'avatar' | 'compose' | 'pre_publish'

export type RiskType = 'copyright' | 'portrait' | 'voice' | 'sensitive_keyword' | 'privacy' | 'platform_rule'

export interface RiskFinding {
  id: string
  type: RiskType
  target: string
  text?: string
  position?: string
  suggestion?: string
}

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

export interface AuthorizationRecord {
  id: string
  task_id: string
  asset_type: 'video' | 'script' | 'voice' | 'avatar' | 'image'
  source: 'user_upload' | 'preset' | 'third_party'
  authorization_confirmed: boolean
  authorization_note?: string
  confirmed_at: string
}

export interface PrePublishCheckInput {
  platform: 'douyin' | 'xiaohongshu' | 'bilibili' | 'wechat_channels' | 'kuaishou' | 'tiktok' | 'youtube'
  title: string
  description: string
  tags: string[]
  ai_label_confirmed: boolean
  cover_artifact_id?: string
}

export interface MusicTrack {
  id: string
  name: string
  path: string
  source: string
  duration?: number | null
}

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
