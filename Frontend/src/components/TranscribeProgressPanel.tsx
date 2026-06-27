/**
 * 用途：文案识别阶段的进度条与步骤说明。
 */
import { getTranscribeProgress } from '../lib/transcribeProgress'
import type { TaskStatus } from '../types/domain'

interface TranscribeProgressPanelProps {
  status: TaskStatus
  pending?: boolean
  compact?: boolean
  title?: string
}

export function TranscribeProgressPanel({
  status,
  pending = false,
  compact = false,
  title = '正在获取文案',
}: TranscribeProgressPanelProps) {
  const progress = getTranscribeProgress(status, { pending })
  const activeStep = progress.steps[progress.currentStepIndex]

  return (
    <div className={`panel transcribe-progress-panel${compact ? ' transcribe-progress-panel-compact' : ''}`}>
      <div className="transcribe-progress-header">
        <div>
          <strong>{title}</strong>
          {!compact ? <p className="muted">{activeStep?.hint ?? progress.message}</p> : null}
        </div>
        <span className="transcribe-progress-percent">{progress.percent}%</span>
      </div>

      <div
        className={`progress-track${progress.isIndeterminate ? ' progress-track-indeterminate' : ''}`}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress.percent}
        aria-label={title}
      >
        <div className="progress-fill" style={{ width: `${progress.percent}%` }} />
      </div>

      <ul className="transcribe-step-list" aria-label="识别步骤">
        {progress.steps.map((step, index) => {
          const state =
            index < progress.currentStepIndex ? 'done' : index === progress.currentStepIndex ? 'current' : 'pending'
          return (
            <li key={step.status} className={state}>
              <span className="transcribe-step-marker" aria-hidden="true" />
              <div>
                <strong>{step.label}</strong>
                {state === 'current' ? <span className="muted">{step.hint}</span> : null}
              </div>
            </li>
          )
        })}
      </ul>

      {!compact ? (
        <p className="muted transcribe-progress-footnote">识别完成后文案会自动填入下方工作区，请保持页面打开。</p>
      ) : null}
    </div>
  )
}
