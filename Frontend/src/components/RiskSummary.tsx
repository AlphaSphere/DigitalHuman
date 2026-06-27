/**
 * 用途：汇总展示一次风险检查的整体结论与统计指标。
 */
import type { RiskCheck, RiskStatus } from '../types/domain'

const reviewedByLabels: Record<RiskCheck['reviewed_by'], string> = {
  system: '系统规则',
  user: '人工确认',
  admin: '管理员',
  deepseek: 'DeepSeek AI',
}

/** 各风险状态对应的标题与说明文案。 */
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
    description: 'DeepSeek 提示需人工确认，请阅读标注位置和处理建议后继续。',
  },
}

interface RiskSummaryProps {
  riskCheck?: RiskCheck
}

export function RiskSummary({ riskCheck }: RiskSummaryProps) {
  if (!riskCheck) {
    return (
      <section className="risk-summary info">
        <p className="eyebrow">DeepSeek 合规检查</p>
        <h2>等待 AI 分析结果</h2>
        <p>请先完成 DeepSeek 仿写，系统将自动运行 AI 合规检查。</p>
      </section>
    )
  }

  const copy = summaryCopy[riskCheck.risk_status]

  return (
    <section className={`risk-summary ${riskCheck.risk_status}`}>
      <p className="eyebrow">DeepSeek 合规检查</p>
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
          <strong>{reviewedByLabels[riskCheck.reviewed_by] ?? riskCheck.reviewed_by}</strong>
          审核来源
        </span>
      </div>
    </section>
  )
}
