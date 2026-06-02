/**
 * 用途：展示单条内容风险命中详情卡片。
 */
import type { RiskFinding } from '../types/domain'

/** 风险类型到中文标签的映射。 */
const riskTypeLabels: Record<RiskFinding['type'], string> = {
  copyright: '版权风险',
  portrait: '肖像风险',
  voice: '声音风险',
  sensitive_keyword: '敏感词风险',
  privacy: '隐私泄露风险',
  platform_rule: '平台规则风险',
}

interface RiskCardProps {
  /** 单条风险发现记录 */
  finding: RiskFinding
}

/**
 * 渲染风险命中卡片：类型、目标、内容与处理建议。
 *
 * @param props.finding - RiskFinding 对象
 * @returns article.risk-card 元素
 *
 * 逻辑：缺失 text/position/suggestion 时使用友好占位文案。
 */
export function RiskCard({ finding }: RiskCardProps) {
  return (
    <article className="risk-card">
      <header>
        <span>{riskTypeLabels[finding.type]}</span>
        <strong>{finding.target}</strong>
      </header>
      <dl>
        <div>
          <dt>命中内容</dt>
          <dd>{finding.text ?? '未返回具体文本'}</dd>
        </div>
        <div>
          <dt>命中位置</dt>
          <dd>{finding.position ?? '待系统定位'}</dd>
        </div>
        <div>
          <dt>处理建议</dt>
          <dd>{finding.suggestion ?? '建议人工复核后再继续。'}</dd>
        </div>
      </dl>
    </article>
  )
}
