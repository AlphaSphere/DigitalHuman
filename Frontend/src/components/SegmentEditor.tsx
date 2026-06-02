/**
 * 用途：可编辑的文案分段列表，支持逐段修改口播文本。
 */
import type { ScriptSegment } from '../types/domain'

interface SegmentEditorProps {
  /** 当前段落列表 */
  segments: ScriptSegment[]
  /** 段落变更回调，传入更新后的完整列表 */
  onChange: (segments: ScriptSegment[]) => void
}

/**
 * 分段文案编辑器，展示时间轴、原文与可编辑 textarea。
 *
 * @param props.segments - 待编辑的 ScriptSegment 数组
 * @param props.onChange - 任一字段变更时回传新列表
 * @returns 分段卡片列表 DOM
 *
 * 逻辑：
 * - updateText 按 segmentId 更新 edited_text；
 * - confidence < 0.86 时显示「需检查」标记；
 * - textarea 默认值为 edited_text ?? original_text。
 */
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
