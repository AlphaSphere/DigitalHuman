/**
 * 文案页内嵌 DeepSeek 合规检查：仿写完成后展示，并标注问题位置。
 */
import { RiskCard } from './RiskCard'
import { RiskSummary } from './RiskSummary'
import type { RiskCheck, RiskFinding } from '../types/domain'

interface ScriptRiskPanelProps {
  riskCheck?: RiskCheck
  riskStale?: boolean
  checking?: boolean
  disabled?: boolean
  deepSeekReady?: boolean
  riskCheckMode?: 'ai' | 'rules'
  activeFindingId?: string | null
  confirmationNote: string
  onConfirmationNoteChange: (value: string) => void
  onRunCheck: () => void
  onJumpToFinding?: (finding: RiskFinding) => void
}

export function ScriptRiskPanel({
  riskCheck,
  riskStale = false,
  checking = false,
  disabled = false,
  deepSeekReady = false,
  riskCheckMode = 'ai',
  activeFindingId = null,
  confirmationNote,
  onConfirmationNoteChange,
  onRunCheck,
  onJumpToFinding,
}: ScriptRiskPanelProps) {
  const needsManualConfirm =
    riskCheck?.risk_status === 'warning' || riskCheck?.risk_status === 'manual_review'
  const isBlocked = riskCheck?.risk_status === 'blocked'
  const scriptFindings = riskCheck?.findings.filter((item) => item.target === 'script') ?? []
  const metaFindings = riskCheck?.findings.filter((item) => item.target !== 'script') ?? []
  const canRunCheck = riskCheckMode === 'rules' || deepSeekReady
  const checkButtonLabel = checking
    ? riskCheckMode === 'ai'
      ? 'DeepSeek 分析中…'
      : '规则检查中…'
    : riskCheck
      ? riskCheckMode === 'ai'
        ? '重新 AI 检查'
        : '重新规则检查'
      : riskCheckMode === 'ai'
        ? '运行 AI 合规检查'
        : '运行规则检查'

  return (
    <section id="script-compliance" className="script-risk-section" aria-label="文案合规检查">
      <div className="script-risk-header">
        <div>
          <h3>{riskCheckMode === 'ai' ? 'DeepSeek AI 合规检查' : '关键词规则合规检查'}</h3>
          <p className="muted">
            {riskCheckMode === 'ai'
              ? '由 DeepSeek 扫描正文合规问题；红色高亮为正文命中，点击风险卡片可跳转到对应位置。'
              : '使用内置关键词规则扫描（仅供参考）；配置 DeepSeek 后可切换为 AI 合规。'}
          </p>
        </div>
        <div className="script-risk-actions">
          <span className={`rewrite-status compact ${deepSeekReady || riskCheckMode === 'rules' ? 'ready' : 'pending'}`}>
            {riskCheckMode === 'ai' ? (deepSeekReady ? 'DeepSeek 已连接' : 'DeepSeek 未就绪') : '规则模式'}
          </span>
          <button
            type="button"
            className="secondary-button"
            disabled={disabled || checking || !canRunCheck}
            onClick={onRunCheck}
          >
            {checkButtonLabel}
          </button>
        </div>
      </div>

      {checking && !riskCheck ? (
        <p className="script-risk-stale info">DeepSeek 正在分析文案合规性，请稍候…</p>
      ) : null}

      {riskStale ? (
        <p className="script-risk-stale">
          文案已修改，请重新运行{riskCheckMode === 'ai' ? ' AI ' : ' '}合规检查后再继续。
        </p>
      ) : null}

      <RiskSummary riskCheck={checking && !riskCheck ? undefined : riskCheck} />

      {needsManualConfirm ? (
        <label className="field-stack script-risk-confirm">
          人工确认说明（可选，不填则使用默认说明）
          <textarea
            rows={3}
            value={confirmationNote}
            onChange={(event) => onConfirmationNoteChange(event.target.value)}
            placeholder="已阅读风险提示，确认可以继续生成。"
          />
        </label>
      ) : null}

      {isBlocked ? (
        <p className="form-error script-risk-blocked">内容被阻断，请修改文案中标注的问题后重新检查。</p>
      ) : null}

      {scriptFindings.length ? (
        <>
          <p className="script-risk-section-label">正文问题（可点击定位）</p>
          <div className="risk-list compact">
            {scriptFindings.map((finding) => (
              <RiskCard
                key={finding.id}
                finding={finding}
                active={finding.id === activeFindingId}
                onJump={onJumpToFinding}
              />
            ))}
          </div>
        </>
      ) : null}

      {metaFindings.length ? (
        <>
          <p className="script-risk-section-label">发布环节提示（非正文词句）</p>
          <div className="risk-list compact">
            {metaFindings.map((finding) => (
              <RiskCard key={finding.id} finding={finding} />
            ))}
          </div>
        </>
      ) : null}

      {riskCheck && !riskCheck.findings.length ? (
        <div className="empty-card">DeepSeek 未发现具体风险命中项。</div>
      ) : null}

      {!riskCheck && !checking ? (
        <div className="empty-card muted">仿写完成后将自动运行 DeepSeek 合规检查。</div>
      ) : null}
    </section>
  )
}
