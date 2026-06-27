/**
 * 用途：成片结果页，展示最终视频预览、产物下载与任务摘要，入口至发布前检查。
 */
import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { StatusBadge } from '../components/StatusBadge'
import { StepNav } from '../components/StepNav'
import { resolveTaskQueryFallback } from '../components/TaskQueryFallback'
import { getStatusMessage, mockApi } from '../lib/api-client/mockApi'
import { buildTaskStepUrl } from '../lib/taskFlow'

function formatSize(size?: number) {
  if (!size) return '未知大小'
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

const RESULT_READY_STATUSES = new Set(['completed', 'publish_ready', 'publish_blocked', 'publish_checking'])

export function ResultPage() {
  const { taskId = '' } = useParams()
  const navigate = useNavigate()
  const taskQuery = useQuery({ queryKey: ['task', taskId], queryFn: () => mockApi.getTask(taskId) })
  const runtimeQuery = useQuery({ queryKey: ['runtime-info'], queryFn: () => mockApi.getRuntimeInfo(), staleTime: 60_000 })
  const artifactQuery = useQuery({
    queryKey: ['artifacts', taskId],
    queryFn: () => mockApi.getArtifacts(taskId),
    enabled: !!taskId,
  })

  const task = taskQuery.data
  const finalVideo = artifactQuery.data?.find((item) => item.type === 'final_video')

  useEffect(() => {
    if (!task) return
    if (!RESULT_READY_STATUSES.has(task.status)) {
      navigate(buildTaskStepUrl(task.id, task.status, task.error_code), { replace: true })
    }
  }, [navigate, task])

  const taskFallback = resolveTaskQueryFallback({
    query: taskQuery,
    loadingMessage: '正在加载成片结果...',
  })
  if (taskFallback) return taskFallback

  if (artifactQuery.isLoading) {
    return <div className="page">正在加载成片产物...</div>
  }

  if (!task || !RESULT_READY_STATUSES.has(task.status)) {
    return <div className="page">成片尚未就绪，正在跳转...</div>
  }

  const runtime = runtimeQuery.data
  const isDemoOutput =
    runtime?.use_stub_model_adapters ||
    runtime?.cosyvoice_mode === 'stub' ||
    runtime?.heygem_mode === 'stub' ||
    runtime?.tuilionnx_mode === 'stub'

  return (
    <section className="page">
      <StepNav current={4} />
      <div className="page-heading row-heading">
        <div>
          <p className="eyebrow">成片结果</p>
          <h1>成片已生成，可以预览和下载</h1>
          <p>
            {isDemoOutput
              ? '当前为占位配音/数字人 + FFmpeg 合成的演示成片；接入真实模型后可获得 AI 口播效果。'
              : '发布前建议先完成标题、简介、标签和 AI 标识检查。'}
          </p>
        </div>
        <StatusBadge status={task.status} label={getStatusMessage(task.status)} />
      </div>

      <div className="two-column result-grid">
        <main className="panel">
          {finalVideo ? (
            <video
              className="final-video-player"
              controls
              preload="metadata"
              src={mockApi.getArtifactDownloadUrl(finalVideo.id)}
            />
          ) : (
            <div className="final-video">
              <span>最终视频预览</span>
              <strong>{task.aspect_ratio}</strong>
              <p className="muted">未找到成片文件，请返回进度页重试生成。</p>
            </div>
          )}
        </main>

        <aside className="panel">
          <h2>产物列表</h2>
          <div className="artifact-list">
            {artifactQuery.data?.map((artifact) => (
              <article key={artifact.id} className="artifact-card">
                <div>
                  <strong>{artifact.meta.label ?? artifact.type}</strong>
                  <span>
                    {artifact.meta.format?.toUpperCase()} · {formatSize(artifact.meta.size_bytes)}
                  </span>
                </div>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => window.open(mockApi.getArtifactDownloadUrl(artifact.id), '_blank')}
                >
                  下载
                </button>
              </article>
            ))}
          </div>
          <h2>任务摘要</h2>
          <dl className="meta-list">
            <div>
              <dt>文案来源</dt>
              <dd>{task.script_source}</dd>
            </div>
            <div>
              <dt>音色</dt>
              <dd>{task.voice_profile_id}</dd>
            </div>
            <div>
              <dt>数字人</dt>
              <dd>{task.avatar_profile_id}</dd>
            </div>
            <div>
              <dt>合规提示</dt>
              <dd>发布前需确认 AI 生成标识</dd>
            </div>
          </dl>
        </aside>
      </div>

      <footer className="action-bar">
        <Link className="ghost-button" to="/tasks/new">
          创建新任务
        </Link>
        <Link className="primary-button" to={`/tasks/${taskId}/pre-publish`}>
          发布前合规检查
        </Link>
      </footer>
    </section>
  )
}
