/** 任务列表页 */
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { resolveTaskQueryFallback } from '../components/TaskQueryFallback'
import { mockApi } from '../lib/api-client/mockApi'
import { buildTaskStepUrl } from '../lib/taskFlow'

export function TaskListPage() {
  const tasksQuery = useQuery({ queryKey: ['tasks'], queryFn: () => mockApi.getTasks() })

  const queryFallback = resolveTaskQueryFallback({
    query: tasksQuery,
    loadingMessage: '正在加载任务列表...',
    notFoundMessage: '暂无任务。',
  })
  if (queryFallback) return queryFallback

  return (
    <div className="page">
      <h1>任务列表</h1>
      <ul>
        {(tasksQuery.data ?? []).map((task) => (
          <li key={task.id}>
            <Link to={buildTaskStepUrl(task.id, task.status, task.error_code)}>{task.id}</Link> — {task.status}
          </li>
        ))}
      </ul>
    </div>
  )
}
