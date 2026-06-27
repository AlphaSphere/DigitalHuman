/**
 * AI 文案仿写工具条（DeepSeek）：紧凑横排，嵌入文案编辑区顶部。
 */
import { useMutation } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { mockApi, type RuntimeInfo } from '../lib/api-client/mockApi'
import type { ScriptRewriteMode, ScriptRewriteStyle, ScriptSegment } from '../types/domain'

const STYLE_OPTIONS: Array<{ value: ScriptRewriteStyle; label: string }> = [
  { value: 'viral_spoken', label: '爆款口播' },
  { value: 'formal', label: '正式专业' },
  { value: 'humorous', label: '幽默轻松' },
]

interface Props {
  taskId: string
  disabled?: boolean
  scriptCharCount?: number
  runtimeInfo?: RuntimeInfo
  onRewritten: (segments: ScriptSegment[]) => void
  /** 仿写成功后触发，用于展开 AI 合规检查区 */
  onRewriteComplete?: () => void
}

export function ScriptRewritePanel({
  taskId,
  disabled = false,
  scriptCharCount = 0,
  runtimeInfo,
  onRewritten,
  onRewriteComplete,
}: Props) {
  const [mode, setMode] = useState<ScriptRewriteMode>('auto')
  const [style, setStyle] = useState<ScriptRewriteStyle>('viral_spoken')
  const [instruction, setInstruction] = useState('')
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const isDeepSeekReady = (runtimeInfo?.enable_llm_rewrite ?? true) && (runtimeInfo?.has_deepseek_api_key ?? false)

  const statusLabel = useMemo(() => {
    if (runtimeInfo && !runtimeInfo.enable_llm_rewrite) return '未启用'
    if (isDeepSeekReady) return '已连接'
    if (!runtimeInfo) return '…'
    return '未就绪'
  }, [runtimeInfo, isDeepSeekReady])

  const mutation = useMutation({
    mutationFn: () =>
      mockApi.rewriteScript(taskId, {
        mode,
        style: mode === 'auto' ? style : undefined,
        instruction: mode === 'instruction' ? instruction.trim() : undefined,
      }),
    onSuccess: (result) => {
      setMessage({ type: 'success', text: result.rewrite_summary ?? '仿写完成' })
      onRewritten(result.segments)
      onRewriteComplete?.()
    },
    onError: (err) => setMessage({ type: 'error', text: err instanceof Error ? err.message : '仿写失败' }),
  })

  const canRun =
    !disabled &&
    isDeepSeekReady &&
    scriptCharCount > 0 &&
    !mutation.isPending &&
    (mode !== 'instruction' || instruction.trim().length > 0)

  return (
    <div className="rewrite-toolbar">
      <div className="rewrite-toolbar-row">
        <div className="rewrite-toolbar-label">
          <strong>DeepSeek 仿写</strong>
          <span className={`rewrite-status compact ${isDeepSeekReady ? 'ready' : 'pending'}`}>{statusLabel}</span>
        </div>

        <div className="rewrite-mode-tabs" role="tablist" aria-label="仿写模式">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'auto'}
            className={mode === 'auto' ? 'active' : ''}
            onClick={() => setMode('auto')}
            disabled={disabled}
          >
            智能仿写
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'instruction'}
            className={mode === 'instruction' ? 'active' : ''}
            onClick={() => setMode('instruction')}
            disabled={disabled}
          >
            按指令
          </button>
        </div>

        {mode === 'auto' ? (
          <div className="rewrite-style-tabs">
            {STYLE_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={style === option.value ? 'active' : ''}
                onClick={() => setStyle(option.value)}
                disabled={disabled}
              >
                {option.label}
              </button>
            ))}
          </div>
        ) : (
          <input
            className="rewrite-instruction-input"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="输入改写要求，例如：更口语化、保留卖点"
            disabled={disabled}
          />
        )}

        <button type="button" className="secondary-button rewrite-run-btn" disabled={!canRun} onClick={() => mutation.mutate()}>
          {mutation.isPending ? '仿写中…' : '执行仿写'}
        </button>
      </div>

      {message ? (
        <p className={message.type === 'error' ? 'form-error rewrite-toolbar-message' : 'rewrite-toolbar-message success'}>
          {message.text}
        </p>
      ) : null}
    </div>
  )
}
