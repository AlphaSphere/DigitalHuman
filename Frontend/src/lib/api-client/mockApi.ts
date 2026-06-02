/**
 * 用途：封装后端 REST API 调用，提供任务、文案、风险、产物与分发相关方法。
 */
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

/** 后端统一响应信封结构。 */
interface ApiEnvelope<T> {
  success: boolean
  data?: T
  error?: {
    code: string
    message: string
    detail?: Record<string, unknown>
  }
}

/** 创建视频任务（上传或 URL）的输入参数。 */
interface CreateVideoTaskInput {
  file?: File | null
  fileName?: string
  source_url?: string
  aspect_ratio: AspectRatio
}

/** 创建纯文案任务的输入参数。 */
interface CreateScriptTaskInput {
  content: string
  content_type: Exclude<ScriptSource, 'video_asr'>
  aspect_ratio: AspectRatio
}

/** 保存生成配置（音色、数字人、字幕等）的输入参数。 */
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

/** API 根地址，可通过 VITE_API_BASE_URL 环境变量覆盖。 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'

/** 各 TaskStatus 对应的中文进度/状态说明。 */
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

/** 进度条计算所用的关键状态顺序（不含失败态）。 */
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

/**
 * 通用 fetch 封装，解析后端 ApiEnvelope 并在失败时抛 Error。
 *
 * @param path - 相对 API 路径（不含 base URL）
 * @param init - 可选 RequestInit
 * @returns 信封中的 data 字段
 *
 * 逻辑：
 * - FormData 请求不强制 Content-Type，由浏览器设置 boundary；
 * - response.ok 或 envelope.success 为 false 时抛出后端 error.message。
 */
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

/**
 * 获取任务状态的中文说明文案。
 *
 * @param status - TaskStatus 枚举值
 * @returns 对应中文描述
 */
export const getStatusMessage = (status: TaskStatus) => statusMessages[status]

/**
 * 根据任务当前状态计算进度百分比与展示信息。
 *
 * @param task - 含 status 字段的任务对象
 * @returns TaskProgress（stage、percent、message）
 *
 * 逻辑：
 * - failed 态固定 percent=0；
 * - 其余按 progressOrder 索引线性映射到 0-100%。
 */
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

/**
 * 后端 API 客户端集合，供各页面 useQuery/useMutation 调用。
 */
export const mockApi = {
  /**
   * 创建基于参考视频的任务（上传文件或提供 URL）。
   *
   * @param input - 视频文件/链接与画幅比例
   * @returns 新建 Task
   *
   * 逻辑：以 multipart/form-data 提交 file 或 source_url。
   */
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

  /**
   * 创建基于粘贴文案的任务。
   *
   * @param input - 文案内容与类型、画幅比例
   * @returns 新建 Task
   */
  async createScriptTask(input: CreateScriptTaskInput): Promise<Task> {
    return request<Task>('/tasks/script', { method: 'POST', body: JSON.stringify(input) })
  },

  /**
   * 按 ID 获取任务详情。
   *
   * @param taskId - 任务 UUID
   * @returns Task 实体
   */
  async getTask(taskId: string): Promise<Task> {
    return request<Task>(`/tasks/${taskId}`)
  },

  /**
   * 获取任务下的文案段落列表。
   *
   * @param taskId - 任务 UUID
   * @returns ScriptSegment 数组
   */
  async getSegments(taskId: string): Promise<ScriptSegment[]> {
    return request<ScriptSegment[]>(`/tasks/${taskId}/segments`)
  },

  /**
   * 批量更新文案段落与生成模式。
   *
   * @param taskId - 任务 UUID
   * @param segments - 待保存的段落列表
   * @param script_generation_mode - 整段或分段时间轴模式，默认 full_script
   * @returns 服务端持久化后的段落列表
   *
   * 逻辑：edited_text 缺省时回退为 original_text。
   */
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

  /**
   * 确认文案并触发后续风险检查流程。
   *
   * @param taskId - 任务 UUID
   * @returns 更新后的 Task
   */
  async confirmScript(taskId: string): Promise<Task> {
    return request<Task>(`/tasks/${taskId}/confirm-script`, { method: 'POST', body: JSON.stringify({}) })
  },

  /**
   * 获取可选预设音色列表。
   *
   * @returns VoiceProfile 数组
   */
  async getVoiceProfiles(): Promise<VoiceProfile[]> {
    return request<VoiceProfile[]>('/voice-profiles')
  },

  /**
   * 获取可选预设数字人列表。
   *
   * @returns AvatarProfile 数组
   */
  async getAvatarProfiles(): Promise<AvatarProfile[]> {
    return request<AvatarProfile[]>('/avatar-profiles')
  },

  /**
   * 保存任务的生成配置（音色、数字人、字幕、背景音乐等）。
   *
   * @param taskId - 任务 UUID
   * @param input - SaveGenerationConfigInput
   * @returns 更新后的 Task
   *
   * 逻辑：config 字段 JSON 字符串 + 可选 custom_voice/custom_video 文件 multipart 上传。
   */
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

  /**
   * 启动视频生成流水线。
   *
   * @param taskId - 任务 UUID
   * @returns 进入生成中状态的 Task
   */
  async startGenerate(taskId: string): Promise<Task> {
    return request<Task>(`/tasks/${taskId}/generate`, { method: 'POST', body: JSON.stringify({}) })
  },

  /**
   * 从失败节点重试任务。
   *
   * @param taskId - 任务 UUID
   * @returns 进入 retrying 状态的 Task
   */
  async retryTask(taskId: string): Promise<Task> {
    return request<Task>(`/tasks/${taskId}/retry`, { method: 'POST', body: JSON.stringify({}) })
  },

  /**
   * 获取任务的风险检查记录，可按阶段过滤。
   *
   * @param taskId - 任务 UUID
   * @param stage - 可选 RiskStage 过滤条件
   * @returns RiskCheck 数组
   */
  async getRiskChecks(taskId: string, stage?: RiskStage): Promise<RiskCheck[]> {
    const suffix = stage ? `?stage=${stage}` : ''
    return request<RiskCheck[]>(`/tasks/${taskId}/risk-checks${suffix}`)
  },

  /**
   * 人工确认风险检查并记录说明。
   *
   * @param taskId - 任务 UUID
   * @param riskCheckId - 风险记录 ID
   * @param confirmation_note - 用户填写的确认说明
   * @returns 含 task 与 riskCheck 的确认结果
   */
  async confirmRiskCheck(taskId: string, riskCheckId: string, confirmation_note: string) {
    return request<{ task: string; riskCheck: RiskCheck }>(`/tasks/${taskId}/risk-checks/${riskCheckId}/confirm`, {
      method: 'POST',
      body: JSON.stringify({ confirmed: true, confirmation_note }),
    })
  },

  /**
   * 获取任务关联的产物列表。
   *
   * @param taskId - 任务 UUID
   * @returns Artifact 数组
   */
  async getArtifacts(taskId: string): Promise<Artifact[]> {
    return request<Artifact[]>(`/tasks/${taskId}/artifacts`)
  },

  /**
   * 构造产物下载 URL（供 window.open 或 a 标签使用）。
   *
   * @param artifactId - 产物 UUID
   * @returns 完整下载地址字符串
   */
  getArtifactDownloadUrl(artifactId: string): string {
    return `${API_BASE_URL}/artifacts/${artifactId}/download`
  },

  /**
   * 执行发布前合规检查（标题、简介、标签、AI 标识等）。
   *
   * @param taskId - 任务 UUID
   * @param input - PrePublishCheckInput
   * @returns 本次检查的 RiskCheck 结果
   */
  async runPrePublishCheck(taskId: string, input: PrePublishCheckInput): Promise<RiskCheck> {
    return request<RiskCheck>(`/tasks/${taskId}/pre-publish-check`, { method: 'POST', body: JSON.stringify(input) })
  },

  /**
   * 获取可选 CC0 背景音乐列表。
   *
   * @returns MusicTrack 数组
   */
  async getMusicTracks(): Promise<MusicTrack[]> {
    return request<MusicTrack[]>('/music-tracks')
  },

  /**
   * 获取任务的平台分发记录。
   *
   * @param taskId - 任务 UUID
   * @returns DistributionRecord 数组
   */
  async getDistributions(taskId: string): Promise<DistributionRecord[]> {
    return request<DistributionRecord[]>(`/tasks/${taskId}/distributions`)
  },

  /**
   * 创建平台分发任务。
   *
   * @param taskId - 任务 UUID
   * @param input - 平台、标题、简介与标签
   * @returns 新建 DistributionRecord
   */
  async createDistribution(
    taskId: string,
    input: Pick<DistributionRecord, 'platform' | 'title' | 'description' | 'tags'>,
  ): Promise<DistributionRecord> {
    return request<DistributionRecord>(`/tasks/${taskId}/distributions`, {
      method: 'POST',
      body: JSON.stringify(input),
    })
  },

  /**
   * 重试失败的分发任务。
   *
   * @param distributionId - 分发记录 UUID
   * @returns 更新后的 DistributionRecord
   */
  async retryDistribution(distributionId: string): Promise<DistributionRecord> {
    return request<DistributionRecord>(`/distributions/${distributionId}/retry`, {
      method: 'POST',
      body: JSON.stringify({}),
    })
  },
}
