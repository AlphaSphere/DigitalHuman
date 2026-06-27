/**
 * 一键流水线进度页。
 */
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { StepNav } from '../components/StepNav'
import { resolveTaskQueryFallback } from '../components/TaskQueryFallback'
import { mockApi } from '../lib/api-client/mockApi'
import { shouldStopPipelinePolling } from '../lib/taskFlow'

export function PipelineProgressPage() {
  const { taskId = '' } = useParams()
  const statusQuery = useQuery({
    queryKey: ['pipeline-status', taskId],
    queryFn: () => mockApi.getPipelineStatus(taskId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (!status || shouldStopPipelinePolling(status)) return false
      return 2000
    },
  })

  const data = statusQuery.data

  const queryFallback = resolveTaskQueryFallback({
    query: statusQuery,
    loadingMessage: '正在读取流水线进度...',
  })
  if (queryFallback) return queryFallback

  if (!data) return <div className="page">正在读取流水线进度...</div>

  const needsManualReview = data.status === 'content_review_required' || data.status === 'content_rejected'
  const stalledConfirmed = data.status === 'script_confirmed'

  return (
    <section className="page">
      <StepNav current={3} />
      <div className="page-heading row-heading">
        <div>
          <p className="eyebrow">一键流水线</p>
          <h1>{data.message || '处理中'}</h1>
          <p>阶段：{data.stage}</p>
        </div>
      </div>
      <div className="panel">
        <div className="progress-ring">
          <strong>{data.percent}%</strong>
          <span>流水线进度</span>
        </div>

        {needsManualReview ? (
          <div className="config-inline-alert" style={{ marginTop: 16 }}>
            <strong>需要人工确认合规</strong>
            <p>一键流程已暂停，请前往文案与合规页填写确认说明后继续。</p>
            <Link className="primary-button" to={`/tasks/${taskId}/script`}>
              去文案与合规
            </Link>
          </div>
        ) : null}

        {stalledConfirmed || data.stage === 'await_config' ? (
          <div className="config-inline-alert" style={{ marginTop: 16 }}>
            <strong>流水线已暂停</strong>
            <p>{data.message || '请先上传音色样本并保存生成配置，再继续一键生成。'}</p>
            <Link className="primary-button" to={`/tasks/${taskId}/config`}>
              去配置生成
            </Link>
          </div>
        ) : null}

        {data.stage_timings && Object.keys(data.stage_timings).length > 0 ? (
          <ul className="timeline" style={{ marginTop: 16 }}>
            {Object.entries(data.stage_timings).map(([stage, timing]) => (
              <li key={stage}>
                {stage} · {timing.duration_ms ? `${Math.round(timing.duration_ms / 1000)}秒` : '--'}
              </li>
            ))}
          </ul>
        ) : null}

        {data.status === 'completed' ? (
          <Link className="primary-button" to={`/tasks/${taskId}/result`}>
            查看成片
          </Link>
        ) : null}

        {data.status === 'failed' ? (
          <div className="config-inline-alert" style={{ marginTop: 16 }}>
            <strong>流水线失败</strong>
            <p>{data.message || '请检查模型服务或返回文案页处理。'}</p>
            <Link className="secondary-button" to={`/tasks/${taskId}/progress`}>
              查看生成进度
            </Link>
            <Link className="ghost-button" to={`/tasks/${taskId}/script`}>
              返回文案处理
            </Link>
          </div>
        ) : null}
      </div>
    </section>
  )
}
