/**
 * 用途：配置页文案门禁引导按钮，使用 programmatic 导航避免 WebView 内 <a> 跳转失效。
 */
import { useNavigate } from 'react-router-dom'
import type { ScriptGateAction } from '../lib/scriptGate'

interface ScriptGateLinkProps {
  taskId: string
  action: ScriptGateAction
  className?: string
}

export function ScriptGateLink({ taskId, action, className }: ScriptGateLinkProps) {
  const navigate = useNavigate()

  const handleClick = () => {
    if (action.target === 'script') {
      navigate(`/tasks/${taskId}/script`, { state: { focusCompliance: true } })
      return
    }
    navigate(`/tasks/${taskId}/progress`)
  }

  return (
    <button type="button" className={className} onClick={handleClick}>
      {action.label}
    </button>
  )
}
