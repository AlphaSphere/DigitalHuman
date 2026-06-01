import type {
  Artifact,
  AspectRatio,
  AvatarProfile,
  AuthorizationRecord,
  GenerationVoiceMode,
  GenerationVideoMode,
  PrePublishCheckInput,
  RiskCheck,
  RiskFinding,
  RiskStatus,
  RiskType,
  ScriptGenerationMode,
  ScriptSegment,
  ScriptSource,
  SubtitleStyle,
  Task,
  TaskProgress,
  TaskStatus,
  VoiceProfile,
} from '../../types/domain'

const STORAGE_KEY = 'digital-human-web-mock'

interface MockState {
  tasks: Record<string, Task>
  segments: Record<string, ScriptSegment[]>
  artifacts: Record<string, Artifact[]>
  riskChecks: Record<string, RiskCheck[]>
  authorizationRecords: Record<string, AuthorizationRecord[]>
  generationTicks: Record<string, number>
}

interface CreateVideoTaskInput {
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
  custom_voice_file_name?: string
  generation_video_mode: GenerationVideoMode
  custom_video_file_name?: string
  authorization_confirmed: boolean
  aspect_ratio: AspectRatio
  subtitle_style: SubtitleStyle
}

const voiceProfiles: VoiceProfile[] = [
  {
    id: 'voice_default_female',
    name: '默认中文女声',
    provider: 'cozyvoice',
    sample_path: 'storage/voices/default_female.wav',
    config: { speed: 1, volume: 1, description: '清晰、稳定，适合知识口播。' },
  },
  {
    id: 'voice_default_male',
    name: '默认中文男声',
    provider: 'cozyvoice',
    sample_path: 'storage/voices/default_male.wav',
    config: { speed: 0.96, volume: 1, description: '低沉、有信任感，适合讲解类内容。' },
  },
]

const avatarProfiles: AvatarProfile[] = [
  {
    id: 'avatar_studio_a',
    name: '默认数字人 A',
    provider: 'heygem',
    config: {
      resolution: '1080x1920',
      template_path: 'storage/avatars/studio_a',
      description: '竖屏半身口播，适合短视频平台。',
    },
  },
  {
    id: 'avatar_studio_b',
    name: '默认数字人 B',
    provider: 'heygem',
    config: {
      resolution: '1920x1080',
      template_path: 'storage/avatars/studio_b',
      description: '横屏课程讲解，适合知识视频。',
    },
  },
]

const generationStages: TaskStatus[] = [
  'dubbing',
  'dubbed',
  'avatar_generating',
  'avatar_generated',
  'subtitle_generating',
  'composing',
  'completed',
]

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

const wait = (ms = 240) => new Promise((resolve) => window.setTimeout(resolve, ms))

const now = () => new Date().toISOString()

const createId = (prefix: string) => `${prefix}_${crypto.randomUUID().slice(0, 8)}`

const initialState = (): MockState => ({
  tasks: {},
  segments: {},
  artifacts: {},
  riskChecks: {},
  authorizationRecords: {},
  generationTicks: {},
})

const loadState = (): MockState => {
  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) return initialState()

  try {
    const state = JSON.parse(raw) as MockState
    return {
      ...initialState(),
      ...state,
      riskChecks: state.riskChecks ?? {},
      authorizationRecords: state.authorizationRecords ?? {},
    }
  } catch {
    return initialState()
  }
}

const saveState = (state: MockState) => {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

const updateState = <T>(updater: (state: MockState) => T) => {
  const state = loadState()
  const result = updater(state)
  saveState(state)
  return result
}

const ensureTask = (state: MockState, taskId: string) => {
  const task = state.tasks[taskId]
  if (!task) {
    throw new Error('任务不存在')
  }
  return task
}

const buildSegments = (taskId: string, sourceType: ScriptSegment['source_type'], content?: string) => {
  const text =
    content ||
    '大家好，今天介绍一个数字人口播视频生成流程。\n系统会先识别或解析文案，再生成配音和数字人视频。\n最后合成字幕并导出成片。'

  return text
    .split(/\n|。|！|？/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map<ScriptSegment>((item, index) => ({
      id: createId('seg'),
      task_id: taskId,
      index: index + 1,
      source_type: sourceType,
      start_time: index * 4,
      end_time: index * 4 + 3.6,
      original_text: `${item}。`,
      edited_text: `${item}。`,
      confidence: sourceType === 'whisper' ? Math.max(0.78, 0.96 - index * 0.04) : null,
    }))
}

const buildArtifacts = (taskId: string): Artifact[] => [
  {
    id: createId('artifact'),
    task_id: taskId,
    type: 'final_video',
    path: `storage/tasks/${taskId}/output/final_with_subtitle.mp4`,
    meta: { duration: 62.5, format: 'mp4', size_bytes: 10485760, label: '带字幕成片' },
    created_at: now(),
  },
  {
    id: createId('artifact'),
    task_id: taskId,
    type: 'subtitle',
    path: `storage/tasks/${taskId}/intermediate/subtitle.srt`,
    meta: { format: 'srt', size_bytes: 4096, label: '字幕文件' },
    created_at: now(),
  },
]

const createAuthorizationRecords = (taskId: string, assetTypes: AuthorizationRecord['asset_type'][]): AuthorizationRecord[] =>
  assetTypes.map((assetType) => ({
    id: createId('auth'),
    task_id: taskId,
    asset_type: assetType,
    source: 'user_upload',
    authorization_confirmed: true,
    authorization_note: '用户确认拥有素材使用授权，且内容可用于 AI 生成和对外发布。',
    confirmed_at: now(),
  }))

const getEditedScriptText = (segments: ScriptSegment[]) =>
  segments.map((segment) => segment.edited_text ?? segment.original_text).join('\n')

const buildRiskFindings = (taskId: string, scriptText: string): RiskFinding[] => {
  const findings: RiskFinding[] = []
  const keywordRules: Array<{ keyword: string; type: RiskType; suggestion: string }> = [
    { keyword: '收益', type: 'platform_rule', suggestion: '避免承诺固定收益，建议改成更中性的经验分享表述。' },
    { keyword: '最强', type: 'sensitive_keyword', suggestion: '广告法极限词建议替换为“较强”或具体事实描述。' },
    { keyword: '身份证', type: 'privacy', suggestion: '请删除或打码个人身份信息。' },
    { keyword: '手机号', type: 'privacy', suggestion: '请删除手机号或改为非真实示例。' },
  ]

  keywordRules.forEach((rule) => {
    const index = scriptText.indexOf(rule.keyword)
    if (index >= 0) {
      findings.push({
        id: createId('finding'),
        type: rule.type,
        target: 'script',
        text: rule.keyword,
        position: `文案第 ${index + 1} 个字符附近`,
        suggestion: rule.suggestion,
      })
    }
  })

  // MVP 默认提醒用户注意 AI 标识，帮助验证人工确认流程。
  findings.push({
    id: createId('finding'),
    type: 'platform_rule',
    target: 'script',
    text: 'AI 生成标识',
    position: '发布说明',
    suggestion: '建议在标题、简介或画面中标注 AI 数字人 / AI 配音内容。',
  })

  return findings.map((finding) => ({ ...finding, id: `${finding.id}_${taskId.slice(-4)}` }))
}

const deriveRiskStatus = (findings: RiskFinding[]): RiskStatus => {
  if (findings.some((finding) => finding.type === 'privacy')) return 'blocked'
  if (findings.length > 0) return 'manual_review'
  return 'passed'
}

const createScriptRiskCheck = (taskId: string, segments: ScriptSegment[]): RiskCheck => {
  const findings = buildRiskFindings(taskId, getEditedScriptText(segments))
  const riskStatus = deriveRiskStatus(findings)
  const riskTypes = Array.from(new Set(findings.map((finding) => finding.type)))

  return {
    id: createId('risk'),
    task_id: taskId,
    stage: 'script',
    risk_status: riskStatus,
    risk_level: riskStatus === 'blocked' ? 'high' : findings.length > 0 ? 'medium' : 'low',
    risk_types: riskTypes,
    findings,
    reviewed_by: 'system',
    reviewed_at: null,
    created_at: now(),
  }
}

const createPrePublishRiskCheck = (taskId: string, input: PrePublishCheckInput): RiskCheck => {
  const findings: RiskFinding[] = []

  if (!input.ai_label_confirmed) {
    findings.push({
      id: createId('finding'),
      type: 'platform_rule',
      target: 'ai_label',
      text: 'AI 生成标识未确认',
      position: '发布信息',
      suggestion: '建议在标题、简介或视频画面中明确标注 AI 生成内容。',
    })
  }

  if (input.title.includes('最强') || input.description.includes('收益')) {
    findings.push({
      id: createId('finding'),
      type: 'sensitive_keyword',
      target: input.title.includes('最强') ? 'title' : 'description',
      text: input.title.includes('最强') ? '最强' : '收益',
      position: input.title.includes('最强') ? '标题' : '简介',
      suggestion: '发布前建议替换极限词或收益承诺类表述。',
    })
  }

  const riskStatus: RiskStatus = findings.some((finding) => finding.type === 'sensitive_keyword')
    ? 'warning'
    : findings.length > 0
      ? 'manual_review'
      : 'passed'

  return {
    id: createId('risk'),
    task_id: taskId,
    stage: 'pre_publish',
    risk_status: riskStatus,
    risk_level: riskStatus === 'passed' ? 'low' : 'medium',
    risk_types: Array.from(new Set(findings.map((finding) => finding.type))),
    findings,
    reviewed_by: 'system',
    reviewed_at: null,
    created_at: now(),
  }
}

export const getStatusMessage = (status: TaskStatus) => statusMessages[status]

export const getProgress = (task: Task): TaskProgress => {
  const order: TaskStatus[] = [
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
    'publish_ready',
    'completed',
  ]
  const index = Math.max(order.indexOf(task.status), 0)

  return {
    stage: task.status,
    percent: task.status === 'failed' ? 0 : Math.min(100, Math.round((index / (order.length - 1)) * 100)),
    message: getStatusMessage(task.status),
  }
}

export const mockApi = {
  async createVideoTask(input: CreateVideoTaskInput) {
    await wait()
    if (!input.fileName && !input.source_url) throw new Error('请上传参考视频或填写视频链接')

    return updateState((state) => {
      const id = createId('task')
      const task: Task = {
        id,
        script_source: 'video_asr',
        status: 'transcribed',
        source_video_path: input.source_url ?? `storage/tasks/${id}/input/${input.fileName}`,
        duration: 62.5,
        aspect_ratio: input.aspect_ratio,
        error_code: null,
        error_message: null,
        created_at: now(),
        updated_at: now(),
      }
      state.tasks[id] = task
      state.segments[id] = buildSegments(id, 'whisper')
      state.authorizationRecords[id] = []
      return task
    })
  },

  async createScriptTask(input: CreateScriptTaskInput) {
    await wait()
    if (!input.content.trim()) throw new Error('请先粘贴字幕或口播文案')

    return updateState((state) => {
      const id = createId('task')
      const task: Task = {
        id,
        script_source: input.content_type,
        status: 'script_parsed',
        duration: null,
        aspect_ratio: input.aspect_ratio,
        error_code: null,
        error_message: null,
        created_at: now(),
        updated_at: now(),
      }
      state.tasks[id] = task
      state.segments[id] = buildSegments(id, input.content_type, input.content)
      state.authorizationRecords[id] = []
      return task
    })
  },

  async getTask(taskId: string) {
    await wait(120)
    return updateState((state) => {
      const task = ensureTask(state, taskId)

      if (generationStages.includes(task.status) && task.status !== 'completed') {
        const ticks = (state.generationTicks[taskId] ?? 0) + 1
        state.generationTicks[taskId] = ticks

        if (ticks % 2 === 0) {
          const currentIndex = generationStages.indexOf(task.status)
          const nextStatus = generationStages[Math.min(currentIndex + 1, generationStages.length - 1)]
          task.status = nextStatus
          task.updated_at = now()

          if (nextStatus === 'completed') {
            state.artifacts[taskId] = buildArtifacts(taskId)
          }
        }
      }

      return task
    })
  },

  async getSegments(taskId: string) {
    await wait(120)
    const state = loadState()
    ensureTask(state, taskId)
    return state.segments[taskId] ?? []
  },

  async updateSegments(taskId: string, segments: ScriptSegment[], scriptGenerationMode?: ScriptGenerationMode) {
    await wait()
    return updateState((state) => {
      const task = ensureTask(state, taskId)
      task.script_generation_mode = scriptGenerationMode ?? task.script_generation_mode ?? 'full_script'
      task.updated_at = now()
      state.segments[taskId] = segments.map((segment, index) => ({
        ...segment,
        index: index + 1,
        source_type: 'manual_edit',
      }))
      return state.segments[taskId]
    })
  },

  async confirmScript(taskId: string) {
    await wait()
    return updateState((state) => {
      const task = ensureTask(state, taskId)
      const riskCheck = createScriptRiskCheck(taskId, state.segments[taskId] ?? [])
      state.riskChecks[taskId] = [
        ...(state.riskChecks[taskId] ?? []).filter((check) => check.stage !== 'script'),
        riskCheck,
      ]
      task.status =
        riskCheck.risk_status === 'blocked'
          ? 'content_rejected'
          : riskCheck.risk_status === 'passed'
            ? 'script_confirmed'
            : 'content_review_required'
      task.updated_at = now()
      return task
    })
  },

  async getRiskChecks(taskId: string, stage?: RiskCheck['stage']) {
    await wait(120)
    const state = loadState()
    ensureTask(state, taskId)
    const checks = state.riskChecks[taskId] ?? []
    return stage ? checks.filter((check) => check.stage === stage) : checks
  },

  async confirmRiskCheck(taskId: string, riskCheckId: string, confirmationNote: string) {
    await wait()
    return updateState((state) => {
      const task = ensureTask(state, taskId)
      const checks = state.riskChecks[taskId] ?? []
      const riskCheck = checks.find((check) => check.id === riskCheckId)
      if (!riskCheck) throw new Error('风险审核记录不存在')
      if (riskCheck.risk_status === 'blocked') throw new Error('高风险内容不能人工放行，请先修改内容')
      if (!confirmationNote.trim()) throw new Error('请填写确认说明')

      riskCheck.risk_status = 'passed'
      riskCheck.reviewed_by = 'user'
      riskCheck.reviewed_at = now()
      task.status = riskCheck.stage === 'pre_publish' ? 'publish_ready' : 'script_confirmed'
      task.updated_at = now()
      return { task, riskCheck }
    })
  },

  async getVoiceProfiles() {
    await wait(120)
    return voiceProfiles
  },

  async getAvatarProfiles() {
    await wait(120)
    return avatarProfiles
  },

  async saveGenerationConfig(taskId: string, input: SaveGenerationConfigInput) {
    await wait()
    return updateState((state) => {
      const task = ensureTask(state, taskId)
      if (input.generation_voice_mode === 'uploaded_voice' && !input.custom_voice_file_name) {
        throw new Error('请先上传自己的音色样本')
      }
      if (input.generation_video_mode === 'uploaded_video' && !input.custom_video_file_name) {
        throw new Error('请先上传自己拍摄的视频素材')
      }
      if (
        (input.generation_voice_mode === 'uploaded_voice' || input.generation_video_mode === 'uploaded_video') &&
        !input.authorization_confirmed
      ) {
        throw new Error('请先确认上传素材授权')
      }

      task.voice_profile_id = input.voice_profile_id
      task.avatar_profile_id = input.avatar_profile_id
      task.generation_voice_mode = input.generation_voice_mode
      task.custom_voice_path =
        input.generation_voice_mode === 'uploaded_voice'
          ? `storage/tasks/${taskId}/input/${input.custom_voice_file_name}`
          : null
      task.generation_video_mode = input.generation_video_mode
      task.custom_video_path =
        input.generation_video_mode === 'uploaded_video'
          ? `storage/tasks/${taskId}/input/${input.custom_video_file_name}`
          : null
      task.aspect_ratio = input.aspect_ratio
      task.subtitle_style = input.subtitle_style
      task.updated_at = now()

      // 只有用户上传自己的声音或自拍视频时，才记录这一步的素材授权确认。
      const uploadedAssetTypes: AuthorizationRecord['asset_type'][] = []
      if (input.generation_voice_mode === 'uploaded_voice') uploadedAssetTypes.push('voice')
      if (input.generation_video_mode === 'uploaded_video') uploadedAssetTypes.push('video')
      state.authorizationRecords[taskId] = uploadedAssetTypes.length
        ? createAuthorizationRecords(taskId, uploadedAssetTypes)
        : []
      return task
    })
  },

  async startGenerate(taskId: string) {
    await wait()
    return updateState((state) => {
      const task = ensureTask(state, taskId)
      if (task.status === 'content_review_required' || task.status === 'content_rejected') {
        throw new Error('请先处理内容风险后再开始生成')
      }
      task.status = 'dubbing'
      task.updated_at = now()
      state.generationTicks[taskId] = 0
      return task
    })
  },

  async retryTask(taskId: string) {
    await wait()
    return updateState((state) => {
      const task = ensureTask(state, taskId)
      task.status = 'retrying'
      task.error_code = null
      task.error_message = null
      task.updated_at = now()
      state.generationTicks[taskId] = 0
      return task
    })
  },

  async getArtifacts(taskId: string) {
    await wait(120)
    return updateState((state) => {
      ensureTask(state, taskId)
      if (!state.artifacts[taskId]) {
        state.artifacts[taskId] = buildArtifacts(taskId)
      }
      return state.artifacts[taskId]
    })
  },

  async runPrePublishCheck(taskId: string, input: PrePublishCheckInput) {
    await wait()
    return updateState((state) => {
      const task = ensureTask(state, taskId)
      if (task.status !== 'completed' && task.status !== 'publish_ready' && task.status !== 'publish_blocked') {
        throw new Error('成片生成完成后才能进行发布前合规检查')
      }

      const riskCheck = createPrePublishRiskCheck(taskId, input)
      state.riskChecks[taskId] = [
        ...(state.riskChecks[taskId] ?? []).filter((check) => check.stage !== 'pre_publish'),
        riskCheck,
      ]
      task.status = riskCheck.risk_status === 'blocked' ? 'publish_blocked' : riskCheck.risk_status === 'passed' ? 'publish_ready' : 'publish_checking'
      task.updated_at = now()
      return riskCheck
    })
  },
}
