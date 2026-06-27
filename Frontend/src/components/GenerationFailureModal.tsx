/**
 * 用途：生成失败详情弹窗，仅在用户点击状态徽章等入口时展示。
 */
import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import type { GenerationFailureView } from '../lib/generationFailure'

interface GenerationFailureModalProps {
  failure: GenerationFailureView
  open: boolean
  onClose: () => void
  cosyvoiceHint?: string | null
  note?: string | null
  actions?: ReactNode
}

export function GenerationFailureModal({
  failure,
  open,
  onClose,
  cosyvoiceHint = null,
  note = null,
  actions = null,
}: GenerationFailureModalProps) {
  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div className="app-modal-overlay" onClick={onClose}>
      <div
        className="app-modal failure-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="failure-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="app-modal-header">
          <div>
            <p className="eyebrow">{failure.category === 'transcribe' ? '识别失败' : '生成失败'}</p>
            <h2 id="failure-modal-title">{failure.title}</h2>
          </div>
          <button type="button" className="app-modal-close" aria-label="关闭" onClick={onClose}>
            ×
          </button>
        </header>

        <div className="app-modal-body failure-modal-body">
          <p className="failure-panel-summary">{failure.summary}</p>
          {cosyvoiceHint ? <p className="form-error failure-panel-note">{cosyvoiceHint}</p> : null}
          {note ? <p className="muted failure-panel-note">{note}</p> : null}

          <div className="failure-panel-meta">
            <span className="failure-panel-code-label">错误码</span>
            <code className="failure-panel-code">{failure.errorCode}</code>
          </div>

          <div className="failure-panel-steps">
            <strong>建议操作</strong>
            <ol>
              {failure.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </div>

          <div className="failure-panel-details failure-panel-details-open">
            <strong className="failure-panel-details-title">详细错误（含代码级信息）</strong>
            <pre>{failure.technicalDetail}</pre>
          </div>
        </div>

        {actions ? <footer className="app-modal-footer failure-panel-actions">{actions}</footer> : null}
      </div>
    </div>,
    document.body,
  )
}
