/**
 * 用途：旧版风险页兼容入口，统一重定向到文案与合规页。
 */
import { Navigate, useParams } from 'react-router-dom'

export function RiskReviewPage() {
  const { taskId = '' } = useParams()
  return <Navigate to={`/tasks/${taskId}/script`} replace />
}
