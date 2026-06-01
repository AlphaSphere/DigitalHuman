import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { StatusBadge } from '../components/StatusBadge'
import { StepNav } from '../components/StepNav'
import { getStatusMessage, mockApi } from '../lib/api-client/mockApi'

export function ResultPage() {
  const { taskId = '' } = useParams()
  const taskQuery = useQuery({ queryKey: ['task', taskId], queryFn: () => mockApi.getTask(taskId) })
  const artifactQuery = useQuery({ queryKey: ['artifacts', taskId], queryFn: () => mockApi.getArtifacts(taskId) })

  if (taskQuery.isLoading || artifactQuery.isLoading) {
    return <div className="page">正在加载成片结果...</div>
  }

  if (!taskQuery.data) return <div className="page">任务不存在。</div>

  return (
    <section className="page">
      <StepNav current={5} />
      <div className="page-heading row-heading">
        <div>
          <p className="eyebrow">成片结果</p>
          <h1>成片已生成，可以预览和下载</h1>
          <p>当前为 mock 产物，发布前建议先完成标题、简介、标签和 AI 标识检查。</p>
        </div>
        <StatusBadge status={taskQuery.data.status} label={getStatusMessage(taskQuery.data.status)} />
      </div>

      <div className="two-column result-grid">
        <main className="panel">
          <div className="final-video">
            <span>最终视频预览</span>
            <strong>{taskQuery.data.aspect_ratio}</strong>
          </div>
        </main>

        <aside className="panel">
          <h2>产物列表</h2>
          <div className="artifact-list">
            {artifactQuery.data?.map((artifact) => (
              <article key={artifact.id} className="artifact-card">
                <div>
                  <strong>{artifact.meta.label ?? artifact.type}</strong>
                  <span>{artifact.meta.format?.toUpperCase()} · {formatSize(artifact.meta.size_bytes)}</span>
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
              <dd>{taskQuery.data.script_source}</dd>
            </div>
            <div>
              <dt>音色</dt>
              <dd>{taskQuery.data.voice_profile_id}</dd>
            </div>
            <div>
              <dt>数字人</dt>
              <dd>{taskQuery.data.avatar_profile_id}</dd>
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

function formatSize(size?: number) {
  if (!size) return '未知大小'
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}
