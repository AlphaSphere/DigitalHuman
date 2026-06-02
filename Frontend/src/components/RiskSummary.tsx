/**
 * 用途：汇总展示一次风险检查的整体结论与统计指标。
 */
import type { RiskCheck, RiskStatus } from '../types/domain'

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
    description: '系统无法自动判断是否可放行，请确认授权、语义和平台规则后继续。',
  },
}

interface RiskSummaryProps {
  /** 可选的风险检查记录，缺省时展示等待态 */
  riskCheck?: RiskCheck
}

/**
 * 风险检查摘要面板。
 *
 * @param props.riskCheck - 后端返回的 RiskCheck，undefined 时显示等待提示
 * @returns section.risk-summary 元素
 *
 * 逻辑：
 * - 无 riskCheck 时渲染 info 态占位；
 * - 有数据时按 risk_status 选择 copy 与 CSS 类，并展示命中数/等级/审核来源。
 */
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
