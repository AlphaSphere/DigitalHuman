/**
 * 用途：根据任务状态展示带语义色调的状态徽章。
 */
import type { TaskStatus } from '../types/domain'

/** 任务状态到视觉色调（success/warning/danger/info）的映射。 */
const statusTone: Record<TaskStatus, 'success' | 'warning' | 'danger' | 'info'> = {
  uploaded: 'info',
  audio_extracted: 'success',
  transcribing: 'info',
  transcribed: 'success',
  script_pasted: 'info',
  script_parsing: 'info',
  script_parsed: 'success',
  script_confirmed: 'success',
  content_checking: 'info',
  content_review_required: 'warning',
  content_rejected: 'danger',
  dubbing: 'info',
  dubbed: 'success',
  avatar_generating: 'info',
  avatar_generated: 'success',
  subtitle_generating: 'info',
  composing: 'info',
  publish_checking: 'warning',
  publish_blocked: 'danger',
  publish_ready: 'success',
  completed: 'success',
  failed: 'danger',
  retrying: 'warning',
}

interface StatusBadgeProps {
  /** 后端任务状态枚举值 */
  status: TaskStatus
  /** 展示给用户的中文状态文案 */
  label: string
}

/**
 * 渲染任务状态徽章。
 *
 * @param props.status - 决定 CSS 色调类名
 * @param props.label - 徽章内显示文本
 * @returns span.status-badge 元素
 *
 * 逻辑：通过 statusTone 查表附加 success/warning/danger/info 类。
 */
export function StatusBadge({ status, label }: StatusBadgeProps) {
  return <span className={`status-badge ${statusTone[status]}`}>{label}</span>
}
