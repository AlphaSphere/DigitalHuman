/**
 * 从合规命中项解析文案中的高亮区间，用于编辑器标注与跳转。
 */
import type { RiskFinding } from '../types/domain'

export interface ScriptHighlightSpan {
  id: string
  start: number
  end: number
  line: number
  label: string
}

const SPAN_PATTERN = /char:(\d+)-(\d+)\|line:(\d+)/
const META_PATTERN = /^meta:/

/** 解析 position 字段中的 char/line 信息。 */
export function parseFindingSpan(position?: string): Pick<ScriptHighlightSpan, 'start' | 'end' | 'line'> | null {
  if (!position || META_PATTERN.test(position)) return null
  const match = position.match(SPAN_PATTERN)
  if (!match) return null
  return {
    start: Number(match[1]),
    end: Number(match[2]),
    line: Number(match[3]),
  }
}

/** 是否为可在正文中定位的命中项。 */
export function canJumpToFinding(finding: RiskFinding): boolean {
  return parseFindingSpan(finding.position) !== null
}

/** 格式化命中位置供 UI 展示。 */
export function formatFindingPosition(finding: RiskFinding): string {
  const position = finding.position?.trim()
  if (!position) return '待定位'
  if (META_PATTERN.test(position)) {
    const parts = position.split('|')
    return parts[2] || parts[1] || '发布环节要求'
  }
  const parts = position.split('|')
  if (parts.length >= 3) return parts.slice(2).join(' · ')
  return position
}

/** 将风险命中项转为全文高亮区间（仅正文内可定位项）。 */
export function buildHighlightSpans(script: string, findings: RiskFinding[]): ScriptHighlightSpan[] {
  const spans: ScriptHighlightSpan[] = []

  for (const finding of findings) {
    const parsed = parseFindingSpan(finding.position)
    if (parsed) {
      const snippet = script.slice(parsed.start, parsed.end)
      if (!snippet.trim()) continue
      spans.push({
        id: finding.id,
        start: parsed.start,
        end: parsed.end,
        line: parsed.line,
        label: finding.text ?? snippet,
      })
      continue
    }

    if (finding.position && META_PATTERN.test(finding.position)) continue

    const text = finding.text?.trim()
    if (!text || !script.includes(text)) continue
    let fromIndex = 0
    while (fromIndex < script.length) {
      const index = script.indexOf(text, fromIndex)
      if (index < 0) break
      spans.push({
        id: `${finding.id}_${index}`,
        start: index,
        end: index + text.length,
        line: script.slice(0, index).split('\n').length,
        label: text,
      })
      fromIndex = index + text.length
    }
  }

  return spans
    .filter((span) => span.start >= 0 && span.end > span.start && span.end <= script.length)
    .sort((a, b) => a.start - b.start || a.end - b.end)
    .filter((span, index, list) => {
      if (index === 0) return true
      const prev = list[index - 1]
      return span.start !== prev.start || span.end !== prev.end
    })
}

export function getFindingSpan(finding: RiskFinding, script: string): ScriptHighlightSpan | null {
  return buildHighlightSpans(script, [finding])[0] ?? null
}
