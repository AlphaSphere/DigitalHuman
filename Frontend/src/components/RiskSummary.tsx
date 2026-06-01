import type { RiskCheck, RiskStatus } from '../types/domain'

const summaryCopy: Record<RiskStatus, { title: string; description: string }> = {
  passed: {
    title: '未发现明显风险',
    description: '当前内容可以继续进入下一步，后续发布前仍建议再做一次合规检查。',
  },
  warning: {
    title: '存在提示性风险',
    description: '请阅读命中位置和处理建议，确认已了解风险后再继续。',
  },
  blocked: {
    title: '内容风险已阻断',
    description: '当前内容不能直接继续，请返回修改文案、素材或发布信息后重新检查。',
  },
  manual_review: {
    title: '需要人工确认',
    description: '系统无法自动判断是否可放行，请确认授权、语义和平台规则后继续。',
  },
}

interface RiskSummaryProps {
  riskCheck?: RiskCheck
}

export function RiskSummary({ riskCheck }: RiskSummaryProps) {
  if (!riskCheck) {
    return (
      <section className="risk-summary info">
        <p className="eyebrow">Risk Review</p>
        <h2>等待风险结果</h2>
        <p>系统还没有返回风险审核记录，请先确认文案或重新检查。</p>
      </section>
    )
  }

  const copy = summaryCopy[riskCheck.risk_status]

  return (
    <section className={`risk-summary ${riskCheck.risk_status}`}>
      <p className="eyebrow">Risk Review</p>
      <h2>{copy.title}</h2>
      <p>{copy.description}</p>
      <div className="risk-summary-grid">
        <span>
          <strong>{riskCheck.findings.length}</strong>
          命中项
        </span>
        <span>
          <strong>{riskCheck.risk_level}</strong>
          风险等级
        </span>
        <span>
          <strong>{riskCheck.reviewed_by}</strong>
          审核来源
        </span>
      </div>
    </section>
  )
}
