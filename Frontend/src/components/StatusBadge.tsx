import type { TaskStatus } from '../types/domain'

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
  status: TaskStatus
  label: string
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  return <span className={`status-badge ${statusTone[status]}`}>{label}</span>
}
