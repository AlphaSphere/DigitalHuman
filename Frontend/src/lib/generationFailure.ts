/**
 * 用途：将任务失败时的 error_code / error_message 解析为进度页可读的展示结构。
 */

export type FailureCategory = 'transcribe' | 'pipeline' | 'dubbing' | 'avatar' | 'subtitle' | 'compose' | 'generic'

export type FailureRecoveryAction = 'retry_generation' | 'go_script' | 'retranscribe'

export interface GenerationFailureView {
  category: FailureCategory
  title: string
  summary: string
  steps: string[]
  errorCode: string
  /** 完整技术详情，含错误码与原始 error_message */
  technicalDetail: string
  rawErrorMessage: string
  recoveryAction: FailureRecoveryAction
  recoveryLabel: string
}

const CATEGORY_TITLE: Record<FailureCategory, string> = {
  transcribe: '视频文案识别失败',
  pipeline: '一键流水线失败',
  dubbing: '配音生成失败',
  avatar: '数字人生成失败',
  subtitle: '字幕生成失败',
  compose: '视频合成失败',
  generic: '生成任务失败',
}

const CATEGORY_STEPS: Record<FailureCategory, string[]> = {
  transcribe: [
    '返回「文案与合规」页，检查参考视频链接是否可公开访问。',
    '确认已安装 yt-dlp、ffmpeg、Whisper（或关闭 Stub 模式）。',
    '点击「重新识别文案」或手动粘贴口播稿后继续。',
  ],
  pipeline: [
    '若提示需人工确认合规，请返回文案页完成确认后再试。',
    '检查模型服务（8002/8003/8004）是否就绪。',
    '修复问题后点击「重新生成」或从配置页重新发起。',
  ],
  dubbing: [
    '关闭应用后，使用「一键启动数字人追爆」重新启动（会自动拉起 8002 配音服务）。',
    '若暂未部署真实 CosyVoice，在 `.env` 设置 `ALLOW_MODEL_SERVICE_STUB_OUTPUT=true` 后重启，8002 会输出占位 WAV 便于联调。',
    '若需真实 AI 配音，配置 `COSYVOICE_UPSTREAM_URL` 指向 CosyVoice 官方 FastAPI（常见端口 50000）。',
    '确认 8002 健康检查 mode 为 stub 或 upstream 后，再点击「重新生成」。',
  ],
  avatar: [
    '重启一键启动脚本，确认 8003（HeyGem）或 8004（TuiliONNX）服务已就绪。',
    '在配置页检查数字人引擎、自拍素材与输出比例是否匹配。',
    '确认无误后点击「重新生成」，系统会保留已生成的文案与配音。',
  ],
  subtitle: [
    '检查文案与时间轴是否完整，必要时返回「文案与合规」页修正。',
    '确认本地 ffmpeg 可用后，点击「重新生成」。',
  ],
  compose: [
    '确认中间产物（配音、数字人视频、字幕）未被手动删除或移动。',
    '返回配置页核对输出比例与素材路径，再点击「重新生成」。',
  ],
  generic: [
    '系统已保留文案与中间产物，可先返回配置页核对参数。',
    '排除环境问题后，点击「重新生成」重试完整流程。',
  ],
}

function normalizeMessage(message: string): string {
  return message.replace(/[:：]\s*$/, '').trim()
}

function detectCategory(message: string, errorCode: string): FailureCategory {
  if (errorCode === 'TRANSCRIBE_FAILED') return 'transcribe'
  if (errorCode === 'PIPELINE_FAILED') return 'pipeline'

  const text = `${message} ${errorCode}`.toLowerCase()
  if (/whisper|yt-dlp|识别|transcrib/.test(text)) return 'transcribe'
  if (/ffmpeg|合成|compose|final_with_subtitle|subtitles=/.test(text)) return 'compose'
  if (/cosyvoice|配音|dubbing|tts/.test(text)) return 'dubbing'
  if (/heygem|tuilionnx|数字人|avatar/.test(text)) return 'avatar'
  if (/字幕|subtitle/.test(text)) return 'subtitle'
  return 'generic'
}

function buildSummary(category: FailureCategory, message: string): string {
  const cleaned = normalizeMessage(message)

  if (category === 'transcribe') {
    return cleaned || '未能从参考视频中识别出口播文案，请检查链接或依赖环境。'
  }
  if (category === 'pipeline') {
    return cleaned || '一键流水线未能完成，请查看下方建议操作。'
  }
  if (category === 'dubbing') {
    if (/ffmpeg|Command \['/i.test(message)) {
      return '生成流程中 ffmpeg 执行失败，请点击状态徽章查看完整命令与报错。'
    }
    if (/未配置.*COSYVOICE|COSYVOICE_COMMAND_TEMPLATE|COSYVOICE_UPSTREAM_URL/i.test(message)) {
      return 'CosyVoice 配音服务尚未就绪：8002 端口在运行，但未配置真实上游，也未开启占位输出。'
    }
    if (!cleaned || /^cosyvoice 服务调用失败$/i.test(cleaned)) {
      return '配音服务（CosyVoice）未正常响应，未能生成配音文件。'
    }
    if (/cosyvoice 服务不可达/i.test(cleaned)) return cleaned
    if (/cosyvoice/i.test(cleaned)) {
      return (
        cleaned.replace(/^cosyvoice 服务调用失败[:：]?\s*/i, '').trim() ||
        '配音服务调用异常，请检查 8002 端口与 CosyVoice 配置。'
      )
    }
  }
  if (category === 'avatar' && (!cleaned || /heygem|tuilionnx/i.test(cleaned))) {
    if (!cleaned) return '数字人包装服务未就绪，未能生成口播视频。'
  }
  if (category === 'compose') {
    if (/ffmpeg|Command \['/i.test(message)) {
      return '视频合成失败（ffmpeg 执行出错），请点击状态徽章查看完整命令与报错。'
    }
  }
  if (cleaned && cleaned.length > 160) {
    return `${cleaned.slice(0, 160)}…（完整信息请点击状态徽章查看）`
  }
  if (cleaned) return cleaned
  return '任务在处理过程中遇到错误，未能完成生成。'
}

function buildTechnicalDetail(errorCode: string, rawMessage: string): string {
  const lines = [`错误码: ${errorCode}`]
  if (rawMessage.trim()) {
    lines.push('', '原始错误信息:', rawMessage.trim())
  } else {
    lines.push('', '原始错误信息: （后端未返回 error_message）')
  }
  return lines.join('\n')
}

function resolveRecovery(category: FailureCategory): Pick<GenerationFailureView, 'recoveryAction' | 'recoveryLabel'> {
  if (category === 'transcribe') {
    return { recoveryAction: 'go_script', recoveryLabel: '去文案与合规' }
  }
  return { recoveryAction: 'retry_generation', recoveryLabel: '重新生成' }
}

/** 根据后端返回的错误字段，生成进度页失败态展示数据。 */
export function parseGenerationFailure(
  errorCode: string | null | undefined,
  errorMessage: string | null | undefined,
): GenerationFailureView {
  const rawMessage = (errorMessage ?? '').trim()
  const code = (errorCode ?? 'UNKNOWN_ERROR').trim() || 'UNKNOWN_ERROR'
  const category = detectCategory(rawMessage, code)
  const summary = buildSummary(category, rawMessage)
  const recovery = resolveRecovery(category)

  return {
    category,
    title: CATEGORY_TITLE[category],
    summary,
    steps: CATEGORY_STEPS[category],
    errorCode: code,
    rawErrorMessage: rawMessage,
    technicalDetail: buildTechnicalDetail(code, rawMessage),
    ...recovery,
  }
}
