/**
 * 带行号的文本编辑区，支持合规风险高亮标注与滚动定位。
 */
import { forwardRef, useImperativeHandle, useMemo, useRef } from 'react'
import type { ScriptHighlightSpan } from '../lib/scriptRiskHighlight'

export interface LineNumberTextareaHandle {
  scrollToSpan: (span: Pick<ScriptHighlightSpan, 'start' | 'end' | 'line'>) => void
}

interface LineNumberTextareaProps {
  value: string
  onChange: (value: string) => void
  rows?: number
  maxLength?: number
  placeholder?: string
  highlights?: ScriptHighlightSpan[]
  activeHighlightId?: string | null
  'aria-label'?: string
}

function renderHighlightedText(value: string, highlights: ScriptHighlightSpan[], activeHighlightId?: string | null) {
  if (!highlights.length) return value || '\u00a0'

  const parts: Array<{ text: string; marked?: boolean; id?: string }> = []
  let cursor = 0
  for (const span of highlights) {
    if (span.start > cursor) {
      parts.push({ text: value.slice(cursor, span.start) })
    }
    parts.push({ text: value.slice(span.start, span.end), marked: true, id: span.id })
    cursor = span.end
  }
  if (cursor < value.length) {
    parts.push({ text: value.slice(cursor) })
  }

  return parts.map((part, index) =>
    part.marked ? (
      <mark
        key={`mark_${part.id ?? index}`}
        className={`script-risk-mark${part.id && part.id === activeHighlightId ? ' active' : ''}`}
        title={part.text}
      >
        {part.text}
      </mark>
    ) : (
      <span key={`text_${index}`}>{part.text || '\u00a0'}</span>
    ),
  )
}

export const LineNumberTextarea = forwardRef<LineNumberTextareaHandle, LineNumberTextareaProps>(
  function LineNumberTextarea(
    {
      value,
      onChange,
      rows = 16,
      maxLength,
      placeholder,
      highlights = [],
      activeHighlightId = null,
      'aria-label': ariaLabel,
    },
    ref,
  ) {
    const textareaRef = useRef<HTMLTextAreaElement>(null)
    const gutterRef = useRef<HTMLDivElement>(null)
    const backdropRef = useRef<HTMLDivElement>(null)
    const lineCount = useMemo(() => Math.max(value.split('\n').length, 1), [value])
    const hasHighlights = highlights.length > 0

    const syncScroll = () => {
      const top = textareaRef.current?.scrollTop ?? 0
      if (gutterRef.current) gutterRef.current.scrollTop = top
      if (backdropRef.current) backdropRef.current.scrollTop = top
    }

    useImperativeHandle(ref, () => ({
      scrollToSpan(span) {
        const textarea = textareaRef.current
        if (!textarea) return
        const styles = window.getComputedStyle(textarea)
        const lineHeight = Number.parseFloat(styles.lineHeight) || 24
        const paddingTop = Number.parseFloat(styles.paddingTop) || 16
        const targetTop = Math.max(0, paddingTop + (span.line - 1) * lineHeight - textarea.clientHeight / 3)
        textarea.scrollTop = targetTop
        syncScroll()
        textarea.focus()
      },
    }))

    return (
      <div className={`line-number-editor${hasHighlights ? ' with-risk-highlights' : ''}`}>
        <div ref={gutterRef} className="line-number-gutter" aria-hidden="true">
          {Array.from({ length: lineCount }, (_, index) => {
            const lineNumber = index + 1
            const lineHasRisk = highlights.some((span) => span.line === lineNumber)
            const lineActive = highlights.some((span) => span.line === lineNumber && span.id === activeHighlightId)
            return (
              <span key={lineNumber} className={lineActive ? 'risk-line active' : lineHasRisk ? 'risk-line' : undefined}>
                {lineNumber}
              </span>
            )
          })}
        </div>
        <div className="line-number-input-wrap">
          {hasHighlights ? (
            <div ref={backdropRef} className="line-number-highlight-backdrop" aria-hidden="true">
              {renderHighlightedText(value, highlights, activeHighlightId)}
            </div>
          ) : null}
          <textarea
            ref={textareaRef}
            className={`line-number-textarea${hasHighlights ? ' transparent-text' : ''}`}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onScroll={syncScroll}
            rows={rows}
            maxLength={maxLength}
            placeholder={placeholder}
            aria-label={ariaLabel}
          />
        </div>
      </div>
    )
  },
)
