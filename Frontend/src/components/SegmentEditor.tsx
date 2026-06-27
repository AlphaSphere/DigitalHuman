/**
 * 用途：可编辑的文案分段列表，支持逐段修改口播文本（带行号与合规高亮）。
 */
import { useMemo } from 'react'
import type { ScriptHighlightSpan } from '../lib/scriptRiskHighlight'
import { LineNumberTextarea } from './LineNumberTextarea'
import type { ScriptSegment } from '../types/domain'

interface SegmentEditorProps {
  /** 当前段落列表 */
  segments: ScriptSegment[]
  /** 全文维度的高亮区间（会自动映射到各段） */
  scriptHighlights?: ScriptHighlightSpan[]
  activeHighlightId?: string | null
  /** 段落变更回调，传入更新后的完整列表 */
  onChange: (segments: ScriptSegment[]) => void
}

const getSegmentText = (segment: ScriptSegment) =>
  (segment.edited_text && segment.edited_text.trim()) || segment.original_text || ''

/**
 * 分段文案编辑器，展示时间轴、原文与可编辑 textarea。
 */
export function SegmentEditor({
  segments,
  scriptHighlights = [],
  activeHighlightId = null,
  onChange,
}: SegmentEditorProps) {
  const segmentHighlights = useMemo(() => {
    const map = new Map<string, ScriptHighlightSpan[]>()
    let offset = 0

    for (const segment of segments) {
      const text = getSegmentText(segment)
      const local: ScriptHighlightSpan[] = []
      for (const span of scriptHighlights) {
        if (span.end <= offset || span.start >= offset + text.length) continue
        local.push({
          ...span,
          start: Math.max(0, span.start - offset),
          end: Math.min(text.length, span.end - offset),
        })
      }
      map.set(segment.id, local)
      offset += text.length + 1
    }

    return map
  }, [segments, scriptHighlights])

  const updateText = (segmentId: string, editedText: string) => {
    onChange(
      segments.map((segment) =>
        segment.id === segmentId ? { ...segment, edited_text: editedText } : segment,
      ),
    )
  }

  return (
    <div className="segment-list">
      {segments.map((segment) => (
        <article className="segment-card" key={segment.id}>
          <header>
            <strong>#{String(segment.index).padStart(2, '0')}</strong>
            <span>
              {segment.start_time?.toFixed(1) ?? '待估算'}s - {segment.end_time?.toFixed(1) ?? '待估算'}s
            </span>
            {segmentHighlights.get(segment.id)?.length ? <em className="risk-flag">合规风险</em> : null}
            {segment.confidence && segment.confidence < 0.86 ? <em>需检查</em> : null}
          </header>
          <p className="original-text">原文：{segment.original_text}</p>
          <LineNumberTextarea
            value={segment.edited_text?.trim() ? segment.edited_text : segment.original_text}
            onChange={(editedText) => updateText(segment.id, editedText)}
            highlights={segmentHighlights.get(segment.id) ?? []}
            activeHighlightId={activeHighlightId}
            rows={3}
            aria-label={`编辑第 ${segment.index} 段文案`}
          />
        </article>
      ))}
    </div>
  )
}
