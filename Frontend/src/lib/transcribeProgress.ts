/**
 * 用途：视频 ASR 文案识别阶段的进度计算与步骤文案。
 */
import { getStatusMessage } from './api-client/mockApi'
import type { TaskStatus } from '../types/domain'

export interface TranscribeProgressStep {
  status: TaskStatus
  label: string
  hint: string
}

/** 识别链路的关键步骤（与后端 TaskStatus 对应）。 */
export const TRANSCRIBE_PROGRESS_STEPS: TranscribeProgressStep[] = [
  { status: 'uploaded', label: '下载参考视频', hint: '从链接拉取原视频，请稍候…' },
  { status: 'audio_extracted', label: '提取音频', hint: '分离音轨，准备送入识别引擎…' },
  { status: 'transcribing', label: '语音识别', hint: 'Whisper 转写口播，首次可能需 2–5 分钟…' },
]

const TRANSCRIBE_STATUS_ORDER: TaskStatus[] = ['uploaded', 'audio_extracted', 'transcribing']
const TRANSCRIBE_PERCENT_STEPS = [12, 42, 78]

export interface TranscribeProgress {
  percent: number
  message: string
  steps: TranscribeProgressStep[]
  currentStepIndex: number
  isIndeterminate: boolean
}

interface TranscribeProgressOptions {
  /** 重新识别刚触发、后端状态尚未切换时使用。 */
  pending?: boolean
}

/** 根据任务状态解析识别进度，供文案页进度条展示。 */
export function getTranscribeProgress(status: TaskStatus, options?: TranscribeProgressOptions): TranscribeProgress {
  const effectiveStatus =
    options?.pending && !TRANSCRIBE_STATUS_ORDER.includes(status) ? ('uploaded' as TaskStatus) : status

  const currentStepIndex = TRANSCRIBE_STATUS_ORDER.indexOf(effectiveStatus)
  const safeIndex = currentStepIndex >= 0 ? currentStepIndex : 0
  const activeStep = TRANSCRIBE_PROGRESS_STEPS[safeIndex]
  const percent = currentStepIndex >= 0 ? TRANSCRIBE_PERCENT_STEPS[currentStepIndex] : 8

  return {
    percent,
    message: TRANSCRIBE_STATUS_ORDER.includes(effectiveStatus)
      ? getStatusMessage(effectiveStatus)
      : activeStep.hint,
    steps: TRANSCRIBE_PROGRESS_STEPS,
    currentStepIndex: safeIndex,
    isIndeterminate: effectiveStatus === 'transcribing' || Boolean(options?.pending),
  }
}
