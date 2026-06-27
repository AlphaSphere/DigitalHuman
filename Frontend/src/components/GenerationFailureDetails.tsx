/**
 * 用途：展示任务生成/识别失败的摘要、错误码与完整技术详情。
 */
import { useId, type ReactNode } from 'react'
import type { GenerationFailureView } from '../lib/generationFailure'

interface GenerationFailureDetailsProps {
  failure: GenerationFailureView
  /** 配置页等内嵌场景使用紧凑布局 */
  compact?: boolean
  /** 是否默认展开技术详情 */
  defaultDetailsOpen?: boolean
  cosyvoiceHint?: string | null
  note?: string | null
  retryError?: string | null
  actions?: ReactNode
}

export function GenerationFailureDetails({
  failure,
  compact = false,
  defaultDetailsOpen = false,
  cosyvoiceHint = null,
  note = null,
  retryError = null,
  actions = null,
}: GenerationFailureDetailsProps) {
  const detailsId = useId()

  return (
    <div
      id="task-failure-details"
      className={`failure-panel${compact ? ' failure-panel-compact' : ''}`}
      role="alert"
    >
      {!compact ? (
        <header className="failure-panel-header">
          <span className="failure-panel-icon" aria-hidden>
            !
          </span>
          <div>
            <p className="eyebrow">{failure.category === 'transcribe' ? '识别失败' : '生成失败'}</p>
            <h1>{failure.title}</h1>
          </div>
        </header>
      ) : (
        <header className="failure-panel-header failure-panel-header-compact">
          <strong>{failure.title}</strong>
          <code className="failure-panel-code inline">{failure.errorCode}</code>
        </header>
      )}

      <p className="failure-panel-summary">{failure.summary}</p>
      {cosyvoiceHint ? <p className="form-error failure-panel-note">{cosyvoiceHint}</p> : null}
      {note ? <p className="muted failure-panel-note">{note}</p> : null}

      {!compact ? (
        <div className="failure-panel-steps">
          <strong>建议操作</strong>
          <ol>
            {failure.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </div>
      ) : null}

      {!compact ? (
        <div className="failure-panel-meta">
          <span className="failure-panel-code-label">错误码</span>
          <code className="failure-panel-code">{failure.errorCode}</code>
        </div>
      ) : null}

      <details className="failure-panel-details" open={defaultDetailsOpen} id={detailsId}>
        <summary>查看详细错误（含代码级信息）</summary>
        <pre>{failure.technicalDetail}</pre>
      </details>

      {retryError ? <p className="form-error failure-panel-note">{retryError}</p> : null}
      {actions ? <div className="failure-panel-actions">{actions}</div> : null}
    </div>
  )
}
