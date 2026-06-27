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
  /** 可点击时作为按钮渲染（如失败态查看详情） */
  onClick?: () => void
  title?: string
}

/**
 * 渲染任务状态徽章。
 */
export function StatusBadge({ status, label, onClick, title }: StatusBadgeProps) {
  const className = `status-badge ${statusTone[status]}${onClick ? ' status-badge-clickable' : ''}`

  if (onClick) {
    return (
      <button type="button" className={className} onClick={onClick} title={title}>
        {label}
      </button>
    )
  }

  return <span className={className}>{label}</span>
}
