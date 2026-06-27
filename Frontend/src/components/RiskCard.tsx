/**
 * 用途：展示单条内容风险命中详情卡片，支持点击跳转到正文位置。
 */
import { canJumpToFinding, formatFindingPosition } from '../lib/scriptRiskHighlight'
import type { RiskFinding } from '../types/domain'

const riskTypeLabels: Record<RiskFinding['type'], string> = {
  copyright: '版权风险',
  portrait: '肖像风险',
  voice: '声音风险',
  sensitive_keyword: '敏感词风险',
  privacy: '隐私泄露风险',
  platform_rule: '平台规则风险',
}

interface RiskCardProps {
  finding: RiskFinding
  active?: boolean
  onJump?: (finding: RiskFinding) => void
}

export function RiskCard({ finding, active = false, onJump }: RiskCardProps) {
  const jumpable = canJumpToFinding(finding)

  return (
    <article
      className={`risk-card${active ? ' active' : ''}${jumpable ? ' jumpable' : ''}`}
      role={jumpable ? 'button' : undefined}
      tabIndex={jumpable ? 0 : undefined}
      onClick={() => jumpable && onJump?.(finding)}
      onKeyDown={(event) => {
        if (!jumpable) return
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onJump?.(finding)
        }
      }}
    >
      <header>
        <span>{riskTypeLabels[finding.type]}</span>
        <strong>{finding.target === 'script' ? '正文' : finding.target}</strong>
        {jumpable ? <em className="risk-jump-hint">点击定位</em> : null}
      </header>
      <dl>
        <div>
          <dt>命中内容</dt>
          <dd>{finding.text ?? '未返回具体文本'}</dd>
        </div>
        <div>
          <dt>命中位置</dt>
          <dd>{formatFindingPosition(finding)}</dd>
        </div>
        <div>
          <dt>处理建议</dt>
          <dd>{finding.suggestion ?? '建议人工复核后再继续。'}</dd>
        </div>
      </dl>
    </article>
  )
}
