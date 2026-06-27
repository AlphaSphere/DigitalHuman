/**
 * 用途：生成进度页，轮询任务状态、展示时间轴，失败时可重试，完成后自动跳转结果页。
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { GenerationFailureDetails } from '../components/GenerationFailureDetails'
import { StatusBadge } from '../components/StatusBadge'
import { StepNav } from '../components/StepNav'
import { resolveTaskQueryFallback } from '../components/TaskQueryFallback'
import { getProgress, getStatusMessage, mockApi } from '../lib/api-client/mockApi'
import { parseGenerationFailure } from '../lib/generationFailure'
import { buildTaskStepUrl, resolveTaskStepPath, shouldStopProgressPolling } from '../lib/taskFlow'
import type { TaskStatus } from '../types/domain'

const timeline: TaskStatus[] = [
  'uploaded',
  'transcribing',
  'transcribed',
  'script_confirmed',
  'content_review_required',
  'retrying',
  'dubbing',
  'dubbed',
  'avatar_generating',
  'avatar_generated',
  'subtitle_generating',
  'composing',
  'completed',
]

function resolveTimelineIndex(status: TaskStatus): number {
  if (status === 'failed') return timeline.indexOf('dubbing')
  const index = timeline.indexOf(status)
  return index >= 0 ? index : 0
}

function formatDurationMs(durationMs?: number): string {
  if (!durationMs || durationMs <= 0) return '--'
  const totalSeconds = Math.round(durationMs / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  if (minutes <= 0) return `${seconds}秒`
  return `${minutes}分${seconds.toString().padStart(2, '0')}秒`
}

const stageTimingLabels: Record<string, string> = {
  dubbing: '配音',
  avatar_generating: '口型/数字人',
  subtitle_generating: '字幕',
  composing: '合成',
}

export function ProgressPage() {
  const { taskId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [retryError, setRetryError] = useState<string | null>(null)
  const taskQuery = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => mockApi.getTask(taskId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (!status || shouldStopProgressPolling(status)) return false
      return 1800
    },
  })

  const retryMutation = useMutation({
    mutationFn: () => mockApi.retryTask(taskId),
    onSuccess: () => {
      setRetryError(null)
      queryClient.invalidateQueries({ queryKey: ['task', taskId] })
    },
    onError: (err) => setRetryError(err instanceof Error ? err.message : '重新生成失败，请稍后重试'),
  })

  const runtimeQuery = useQuery({
    queryKey: ['runtime-info'],
    queryFn: () => mockApi.getRuntimeInfo(),
    staleTime: 60_000,
  })

  const task = taskQuery.data
  const progress = task ? getProgress(task) : null

  useEffect(() => {
    if (!task) return
    if (task.status === 'completed') {
      const timer = window.setTimeout(() => navigate(`/tasks/${task.id}/result`), 800)
      return () => window.clearTimeout(timer)
    }
    if (task.status === 'failed') return
    const step = resolveTaskStepPath(task.status, task.error_code)
    if (step !== 'progress') {
      navigate(buildTaskStepUrl(task.id, task.status, task.error_code), { replace: true })
    }
  }, [navigate, task])

  const queryFallback = resolveTaskQueryFallback({
    query: taskQuery,
    loadingMessage: '正在读取任务进度...',
  })
  if (queryFallback) return queryFallback

  if (!task || !progress) return <div className="page">正在读取任务进度...</div>

  if (task.status === 'failed') {
    const failure = parseGenerationFailure(task.error_code, task.error_message)
    const runtimeInfo = runtimeQuery.data
    const cosyvoiceHint =
      failure.category === 'dubbing' && runtimeInfo?.cosyvoice_mode === 'unconfigured'
        ? '检测到 8002 配音服务处于未配置状态。请在 `.env` 添加 `ALLOW_MODEL_SERVICE_STUB_OUTPUT=true` 并重启一键启动脚本，或配置 `COSYVOICE_UPSTREAM_URL`。'
        : null

    return (
      <section className="page">
        <StepNav current={3} />
        <GenerationFailureDetails
          failure={failure}
          defaultDetailsOpen
          cosyvoiceHint={cosyvoiceHint}
          note={
            failure.category === 'transcribe'
              ? '请返回文案页重新识别或粘贴文案后继续。'
              : '系统已保留文案和中间产物，修复问题后可重新发起完整生成。'
          }
          retryError={retryError}
          actions={
            <>
              {failure.recoveryAction === 'go_script' ? (
                <button className="ghost-button" type="button" onClick={() => navigate(`/tasks/${taskId}/script`)}>
                  去文案与合规
                </button>
              ) : (
                <button className="ghost-button" type="button" onClick={() => navigate(`/tasks/${taskId}/config`)}>
                  返回检查配置
                </button>
              )}
              {failure.recoveryAction === 'retry_generation' ? (
                <button
                  className="primary-button"
                  type="button"
                  disabled={retryMutation.isPending}
                  onClick={() => retryMutation.mutate()}
                >
                  {retryMutation.isPending ? '重新生成中...' : failure.recoveryLabel}
                </button>
              ) : (
                <button className="primary-button" type="button" onClick={() => navigate(`/tasks/${taskId}/script`)}>
                  去文案与合规
                </button>
              )}
            </>
          }
        />
      </section>
    )
  }

  const currentIndex = resolveTimelineIndex(task.status)
  const stageTimings = task.pipeline_stage?.stage_timings ?? {}

  return (
    <section className="page">
      <StepNav current={3} />
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
            <span>整体进度</span>
          </div>
          <ul className="timeline">
            {timeline.map((step, index) => (
              <li key={step} className={index < currentIndex ? 'done' : index === currentIndex ? 'current' : ''}>
                {getStatusMessage(step)}
              </li>
            ))}
          </ul>
        </main>

        <aside className="panel">
          <h2>当前阶段</h2>
          <p>{progress.message}</p>
          {Object.keys(stageTimings).length > 0 ? (
            <ul className="timeline" style={{ marginTop: 12 }}>
              {Object.entries(stageTimings).map(([stage, timing]) => (
                <li key={stage}>
                  {stageTimingLabels[stage] ?? stage} · {formatDurationMs(timing.duration_ms)}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">各阶段耗时会在生成完成后显示，便于对比优化效果。</p>
          )}
          <Link className="ghost-button" to={`/tasks/${taskId}/config`}>
            返回配置
          </Link>
        </aside>
      </div>
    </section>
  )
}
