import type {
  Artifact,
  AspectRatio,
  AvatarProfile,
  GenerationVoiceMode,
  GenerationVideoMode,
  DistributionRecord,
  MusicTrack,
  PrePublishCheckInput,
  RiskCheck,
  RiskStage,
  ScriptGenerationMode,
  ScriptSegment,
  ScriptSource,
  SubtitleStyle,
  Task,
  TaskProgress,
  TaskStatus,
  VoiceProfile,
} from '../../types/domain'

interface ApiEnvelope<T> {
  success: boolean
  data?: T
  error?: {
    code: string
    message: string
    detail?: Record<string, unknown>
  }
}

interface CreateVideoTaskInput {
  file?: File | null
  fileName?: string
  source_url?: string
  aspect_ratio: AspectRatio
}

interface CreateScriptTaskInput {
  content: string
  content_type: Exclude<ScriptSource, 'video_asr'>
  aspect_ratio: AspectRatio
}

interface SaveGenerationConfigInput {
  voice_profile_id: string
  avatar_profile_id: string
  generation_voice_mode: GenerationVoiceMode
  custom_voice_file?: File | null
  custom_voice_file_name?: string
  generation_video_mode: GenerationVideoMode
  custom_video_file?: File | null
  custom_video_file_name?: string
  authorization_confirmed: boolean
  aspect_ratio: AspectRatio
  subtitle_style: SubtitleStyle
  background_music_path?: string | null
  background_music_volume?: number
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'

const statusMessages: Record<TaskStatus, string> = {
  uploaded: '视频已上传，等待识别',
  audio_extracted: '音频提取完成',
  transcribing: '正在识别文案',
  transcribed: '文案识别完成，请确认',
  script_pasted: '文案已提交，等待解析',
  script_parsing: '正在解析文案',
  script_parsed: '文案解析完成，请确认',
  script_confirmed: '文案已确认，可以配置生成参数',
  content_checking: '正在检查内容风险',
  content_review_required: '内容需要人工确认',
  content_rejected: '内容风险较高，请修改',
  dubbing: '正在生成配音',
  dubbed: '配音生成完成',
  avatar_generating: '正在生成数字人口播视频',
  avatar_generated: '数字人视频生成完成',
  subtitle_generating: '正在生成字幕',
  composing: '正在合成最终视频',
  publish_checking: '正在进行发布前合规检查',
  publish_blocked: '发布前检查未通过',
  publish_ready: '已通过发布前检查',
  completed: '成片已生成',
  failed: '生成失败，可查看原因并重试',
  retrying: '正在从失败节点重试',
}

const progressOrder: TaskStatus[] = [
  'uploaded',
  'transcribing',
  'transcribed',
  'script_confirmed',
  'content_checking',
  'content_review_required',
  'dubbing',
  'dubbed',
  'avatar_generating',
  'avatar_generated',
  'subtitle_generating',
  'composing',
  'completed',
]

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { 'Content-Type': 'application/json', ...init?.headers },
  })
  const envelope = (await response.json()) as ApiEnvelope<T>
  if (!response.ok || !envelope.success) {
    throw new Error(envelope.error?.message ?? '请求失败')
  }
  return envelope.data as T
}

export const getStatusMessage = (status: TaskStatus) => statusMessages[status]

export const getProgress = (task: Task): TaskProgress => {
  if (task.status === 'failed') {
    return { stage: task.status, percent: 0, message: getStatusMessage(task.status) }
  }
  const index = progressOrder.includes(task.status) ? progressOrder.indexOf(task.status) : 0
  return {
    stage: task.status,
    percent: Math.min(100, Math.round((index / (progressOrder.length - 1)) * 100)),
    message: getStatusMessage(task.status),
  }
}

export const mockApi = {
  async createVideoTask(input: CreateVideoTaskInput): Promise<Task> {
    const formData = new FormData()
    formData.append('aspect_ratio', input.aspect_ratio)
    if (input.file) {
      formData.append('file', input.file, input.file.name)
    }
    if (input.source_url) {
      formData.append('source_url', input.source_url)
    }
    return request<Task>('/tasks/video', { method: 'POST', body: formData })
  },

  async createScriptTask(input: CreateScriptTaskInput): Promise<Task> {
    return request<Task>('/tasks/script', { method: 'POST', body: JSON.stringify(input) })
  },

  async getTask(taskId: string): Promise<Task> {
    return request<Task>(`/tasks/${taskId}`)
  },

  async getSegments(taskId: string): Promise<ScriptSegment[]> {
    return request<ScriptSegment[]>(`/tasks/${taskId}/segments`)
  },

  async updateSegments(
    taskId: string,
    segments: ScriptSegment[],
    script_generation_mode: ScriptGenerationMode = 'full_script',
  ): Promise<ScriptSegment[]> {
    return request<ScriptSegment[]>(`/tasks/${taskId}/segments`, {
      method: 'PUT',
      body: JSON.stringify({
        script_generation_mode,
        segments: segments.map((segment) => ({
          id: segment.id,
          index: segment.index,
          start_time: segment.start_time,
          end_time: segment.end_time,
          original_text: segment.original_text,
          edited_text: segment.edited_text ?? segment.original_text,
        })),
      }),
    })
  },

  async confirmScript(taskId: string): Promise<Task> {
    return request<Task>(`/tasks/${taskId}/confirm-script`, { method: 'POST', body: JSON.stringify({}) })
  },

  async getVoiceProfiles(): Promise<VoiceProfile[]> {
    return request<VoiceProfile[]>('/voice-profiles')
  },

  async getAvatarProfiles(): Promise<AvatarProfile[]> {
    return request<AvatarProfile[]>('/avatar-profiles')
  },

  async saveGenerationConfig(taskId: string, input: SaveGenerationConfigInput): Promise<Task> {
    const formData = new FormData()
    formData.append(
      'config',
      JSON.stringify({
        voice_profile_id: input.voice_profile_id,
        avatar_profile_id: input.avatar_profile_id,
        generation_voice_mode: input.generation_voice_mode,
        custom_voice_file_name: input.custom_voice_file?.name ?? input.custom_voice_file_name,
        generation_video_mode: input.generation_video_mode,
        custom_video_file_name: input.custom_video_file?.name ?? input.custom_video_file_name,
        authorization_confirmed: input.authorization_confirmed,
        aspect_ratio: input.aspect_ratio,
        subtitle_style: input.subtitle_style,
        background_music_path: input.background_music_path,
        background_music_volume: input.background_music_volume,
      }),
    )
    if (input.custom_voice_file) formData.append('custom_voice_file', input.custom_voice_file, input.custom_voice_file.name)
    if (input.custom_video_file) formData.append('custom_video_file', input.custom_video_file, input.custom_video_file.name)
    return request<Task>(`/tasks/${taskId}/generation-config`, { method: 'POST', body: formData })
  },

  async startGenerate(taskId: string): Promise<Task> {
    return request<Task>(`/tasks/${taskId}/generate`, { method: 'POST', body: JSON.stringify({}) })
  },

  async retryTask(taskId: string): Promise<Task> {
    return request<Task>(`/tasks/${taskId}/retry`, { method: 'POST', body: JSON.stringify({}) })
  },

  async getRiskChecks(taskId: string, stage?: RiskStage): Promise<RiskCheck[]> {
    const suffix = stage ? `?stage=${stage}` : ''
    return request<RiskCheck[]>(`/tasks/${taskId}/risk-checks${suffix}`)
  },

  async confirmRiskCheck(taskId: string, riskCheckId: string, confirmation_note: string) {
    return request<{ task: string; riskCheck: RiskCheck }>(`/tasks/${taskId}/risk-checks/${riskCheckId}/confirm`, {
      method: 'POST',
      body: JSON.stringify({ confirmed: true, confirmation_note }),
    })
  },

  async getArtifacts(taskId: string): Promise<Artifact[]> {
    return request<Artifact[]>(`/tasks/${taskId}/artifacts`)
  },

  getArtifactDownloadUrl(artifactId: string): string {
    return `${API_BASE_URL}/artifacts/${artifactId}/download`
  },

  async runPrePublishCheck(taskId: string, input: PrePublishCheckInput): Promise<RiskCheck> {
    return request<RiskCheck>(`/tasks/${taskId}/pre-publish-check`, { method: 'POST', body: JSON.stringify(input) })
  },

  async getMusicTracks(): Promise<MusicTrack[]> {
    return request<MusicTrack[]>('/music-tracks')
  },

  async getDistributions(taskId: string): Promise<DistributionRecord[]> {
    return request<DistributionRecord[]>(`/tasks/${taskId}/distributions`)
  },

  async createDistribution(
    taskId: string,
    input: Pick<DistributionRecord, 'platform' | 'title' | 'description' | 'tags'>,
  ): Promise<DistributionRecord> {
    return request<DistributionRecord>(`/tasks/${taskId}/distributions`, {
      method: 'POST',
      body: JSON.stringify(input),
    })
  },

  async retryDistribution(distributionId: string): Promise<DistributionRecord> {
    return request<DistributionRecord>(`/distributions/${distributionId}/retry`, {
      method: 'POST',
      body: JSON.stringify({}),
    })
  },
}
