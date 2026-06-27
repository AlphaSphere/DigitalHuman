/**
 * 用途：按任务状态与 error_code 解析应进入的分步流程页面路径段。
 */
import type { TaskStatus } from '../types/domain'

const GENERATION_PROGRESS_STATUSES: TaskStatus[] = [
  'dubbing',
  'dubbed',
  'avatar_generating',
  'avatar_generated',
  'subtitle_generating',
  'composing',
  'retrying',
]

const PIPELINE_TERMINAL_STATUSES: TaskStatus[] = ['content_review_required', 'content_rejected']

/** 返回路由 path 段：script | config | progress | result */
export function resolveTaskStepPath(status: TaskStatus, errorCode?: string | null): string {
  if (status === 'failed') {
    if (errorCode === 'TRANSCRIBE_FAILED') return 'script'
    if (errorCode === 'GENERATION_FAILED' || errorCode === 'PIPELINE_FAILED') return 'progress'
    return 'script'
  }

  if (GENERATION_PROGRESS_STATUSES.includes(status)) return 'progress'
  if (PIPELINE_TERMINAL_STATUSES.includes(status)) return 'script'
  if (status === 'content_review_required' || status === 'content_rejected') return 'script'
  if (status === 'script_confirmed') return 'config'
  if (status === 'completed' || status === 'publish_ready' || status === 'publish_blocked') return 'result'
  if (status === 'publish_checking') return 'pre-publish'

  return 'script'
}

export function buildTaskStepUrl(taskId: string, status: TaskStatus, errorCode?: string | null): string {
  return `/tasks/${taskId}/${resolveTaskStepPath(status, errorCode)}`
}

/** 生成失败后仍允许进入配置页核对参数（识别失败除外）。 */
export function canAccessConfigPage(status: TaskStatus, errorCode?: string | null): boolean {
  if (status === 'script_confirmed') return true
  if (status === 'failed' && errorCode !== 'TRANSCRIBE_FAILED') return true
  return resolveTaskStepPath(status, errorCode) === 'config'
}

export function isGenerationInProgress(status?: TaskStatus): boolean {
  return !!status && GENERATION_PROGRESS_STATUSES.includes(status)
}

export function shouldStopProgressPolling(status?: TaskStatus): boolean {
  if (!status) return false
  return status === 'completed' || status === 'failed' || status === 'content_review_required' || status === 'content_rejected'
}

export function shouldStopPipelinePolling(status?: TaskStatus): boolean {
  if (!status) return false
  return (
    status === 'completed' ||
    status === 'failed' ||
    status === 'content_review_required' ||
    status === 'content_rejected' ||
    status === 'script_confirmed'
  )
}
