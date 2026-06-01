import type { ScriptSegment } from '../types/domain'

interface SegmentEditorProps {
  segments: ScriptSegment[]
  onChange: (segments: ScriptSegment[]) => void
}

export function SegmentEditor({ segments, onChange }: SegmentEditorProps) {
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
            {segment.confidence && segment.confidence < 0.86 ? <em>需检查</em> : null}
          </header>
          <p className="original-text">原文：{segment.original_text}</p>
          <textarea
            value={segment.edited_text ?? segment.original_text}
            onChange={(event) => updateText(segment.id, event.target.value)}
            rows={3}
            aria-label={`编辑第 ${segment.index} 段文案`}
          />
        </article>
      ))}
    </div>
  )
}
