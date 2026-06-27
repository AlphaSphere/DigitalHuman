/**
 * 旧一键流程链接兼容：按任务状态跳转到分步流程对应页面。
 */
import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { resolveTaskQueryFallback } from '../components/TaskQueryFallback'
import { mockApi } from '../lib/api-client/mockApi'
import { buildTaskStepUrl } from '../lib/taskFlow'

export function TaskFlowRedirect() {
  const { taskId = '' } = useParams()
  const navigate = useNavigate()
  const taskQuery = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => mockApi.getTask(taskId),
    enabled: !!taskId,
  })

  useEffect(() => {
    if (!taskQuery.data) return
    navigate(buildTaskStepUrl(taskId, taskQuery.data.status, taskQuery.data.error_code), { replace: true })
  }, [taskQuery.data, taskId, navigate])

  const queryFallback = resolveTaskQueryFallback({
    query: taskQuery,
    loadingMessage: '正在进入分步流程...',
  })
  if (queryFallback) return queryFallback

  return <div className="page">正在进入分步流程...</div>
}
