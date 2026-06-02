/**
 * 用途：生成进度页，轮询任务状态、展示时间轴，失败时可重试，完成后自动跳转结果页。
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { StatusBadge } from '../components/StatusBadge'
import { StepNav } from '../components/StepNav'
import { getProgress, getStatusMessage, mockApi } from '../lib/api-client/mockApi'
import type { TaskStatus } from '../types/domain'

/** 进度时间轴展示用的关键状态序列（与 UI 步骤一一对应）。 */
const timeline: TaskStatus[] = [
  'uploaded',
  'transcribed',
  'script_confirmed',
  'content_checking',
  'content_review_required',
  'dubbing',
  'dubbed',
  'avatar_generating',
  'avatar_generated',
  'subtitle_generating',
  'composing',
  'completed',
]

/**
 * 视频生成进度监控页面。
 *
 * @returns 进度环、时间轴与失败重试 UI
 *
 * 逻辑：
 * - refetchInterval 1.8s 轮询直至 completed；
 * - failed 态展示错误码与 retryTask；
 * - completed 后 800ms 自动 navigate 至结果页。
 */
export function ProgressPage() {
  const { taskId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const taskQuery = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => mockApi.getTask(taskId),
    refetchInterval: (query) => (query.state.data?.status === 'completed' ? false : 1800),
  })

  const retryMutation = useMutation({
    mutationFn: () => mockApi.retryTask(taskId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['task', taskId] }),
  })

  const task = taskQuery.data
  const progress = task ? getProgress(task) : null

  useEffect(() => {
    if (task?.status === 'completed') {
      const timer = window.setTimeout(() => navigate(`/tasks/${task.id}/result`), 800)
      return () => window.clearTimeout(timer)
    }
  }, [navigate, task?.id, task?.status])

  if (taskQuery.isLoading || !task || !progress) {
    return <div className="page">正在读取任务进度...</div>
  }

  if (task.status === 'failed') {
    return (
      <section className="page">
        <StepNav current={4} />
        <div className="failure-panel">
          <h1>生成失败：{task.error_message ?? '任务处理失败'}</h1>
          <p>系统已保留文案和中间产物，可从失败节点重试。</p>
          <code>{task.error_code ?? 'UNKNOWN_ERROR'}</code>
          <button className="primary-button" type="button" onClick={() => retryMutation.mutate()}>
            从失败节点重试
          </button>
        </div>
      </section>
    )
  }

  const currentIndex = timeline.indexOf(task.status)

  return (
    <section className="page">
      <StepNav current={4} />
      <div className="page-heading row-heading">
        <div>
          <p className="eyebrow">生成进度</p>
          <h1>{progress.message}</h1>
          <p>长耗时阶段会持续更新状态，完成后自动进入结果页。</p>
        </div>
        <StatusBadge status={task.status} label={getStatusMessage(task.status)} />
      </div>

      <div className="two-column">
        <main className="panel">
          <div className="progress-ring">
            <strong>{progress.percent}%</strong>
            <span>{progress.stage}</span>
          </div>
          <ol className="timeline">
            {timeline.map((status, index) => (
              <li key={status} className={index < currentIndex ? 'done' : index === currentIndex ? 'current' : ''}>
                <span>{index < currentIndex ? '✓' : index === currentIndex ? '●' : '○'}</span>
                {getStatusMessage(status)}
              </li>
            ))}
          </ol>
        </main>

        <aside className="panel">
          <h2>当前阶段详情</h2>
          <p className="muted">{progress.message}</p>
          <div className="artifact-preview-list">
            <span>confirmed_script.json</span>
            <span>tts_audio.wav {currentIndex >= 4 ? '已生成' : '等待中'}</span>
            <span>avatar_video.mp4 {currentIndex >= 6 ? '已生成' : '生成中'}</span>
            <span>final_with_subtitle.mp4 {task.status === 'completed' ? '已生成' : '等待中'}</span>
          </div>
        </aside>
      </div>

      <footer className="action-bar">
        <Link className="ghost-button" to={`/tasks/${taskId}/config`}>
          返回配置
        </Link>
        <button className="secondary-button" type="button" onClick={() => taskQuery.refetch()}>
          手动刷新
        </button>
      </footer>
    </section>
  )
}
