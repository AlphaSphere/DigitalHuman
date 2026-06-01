import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { RiskCard } from '../components/RiskCard'
import { RiskSummary } from '../components/RiskSummary'
import { StatusBadge } from '../components/StatusBadge'
import { StepNav } from '../components/StepNav'
import { getStatusMessage, mockApi } from '../lib/api-client/mockApi'

export function RiskReviewPage() {
  const { taskId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [confirmationNote, setConfirmationNote] = useState('已确认素材授权和内容风险，继续生成。')
  const [error, setError] = useState<string | null>(null)

  const taskQuery = useQuery({ queryKey: ['task', taskId], queryFn: () => mockApi.getTask(taskId) })
  const riskQuery = useQuery({
    queryKey: ['riskChecks', taskId, 'script'],
    queryFn: () => mockApi.getRiskChecks(taskId, 'script'),
  })

  const riskCheck = useMemo(() => riskQuery.data?.[0], [riskQuery.data])

  const confirmMutation = useMutation({
    mutationFn: async () => {
      if (!riskCheck) throw new Error('风险审核记录不存在')
      return mockApi.confirmRiskCheck(taskId, riskCheck.id, confirmationNote)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task', taskId] })
      queryClient.invalidateQueries({ queryKey: ['riskChecks', taskId] })
      navigate(`/tasks/${taskId}/config`)
    },
    onError: (err) => setError(err instanceof Error ? err.message : '风险确认失败'),
  })

  if (taskQuery.isLoading || riskQuery.isLoading) {
    return <div className="page">正在读取内容风险结果...</div>
  }

  const task = taskQuery.data
  if (!task) return <div className="page">任务不存在。</div>

  const canContinueDirectly = riskCheck?.risk_status === 'passed'
  const canConfirm = riskCheck?.risk_status === 'warning' || riskCheck?.risk_status === 'manual_review'
  const isBlocked = riskCheck?.risk_status === 'blocked'

  return (
    <section className="page">
      <StepNav current={2} />
      <div className="page-heading row-heading">
        <div>
          <p className="eyebrow">内容风险提示</p>
          <h1>生成前先确认内容安全与授权风险</h1>
          <p>系统会提示敏感词、隐私、授权和 AI 标识风险，避免高风险内容直接进入生成。</p>
        </div>
        <StatusBadge status={task.status} label={getStatusMessage(task.status)} />
      </div>

      <div className="two-column risk-layout">
        <main className="panel">
          <RiskSummary riskCheck={riskCheck} />
          <div className="risk-list">
            {riskCheck?.findings.length ? (
              riskCheck.findings.map((finding) => <RiskCard key={finding.id} finding={finding} />)
            ) : (
              <div className="empty-card">未发现具体风险命中项。</div>
            )}
          </div>
        </main>

        <aside className="panel">
          <h2>处理建议</h2>
          <p className="muted">
            如果风险来自具体文案，请返回文案页修改；如果是 AI 标识或授权提示，可以阅读后人工确认。
          </p>
          {canConfirm ? (
            <label className="field-stack">
              人工确认说明
              <textarea
                rows={5}
                value={confirmationNote}
                onChange={(event) => setConfirmationNote(event.target.value)}
              />
            </label>
          ) : null}
          {isBlocked ? <p className="form-error">当前内容被阻断，必须返回修改后重新确认文案。</p> : null}
          {error ? <p className="form-error">{error}</p> : null}
        </aside>
      </div>

      <footer className="action-bar">
        <Link className="ghost-button" to={`/tasks/${taskId}/script`}>
          返回修改文案
        </Link>
        {canContinueDirectly ? (
          <Link className="primary-button" to={`/tasks/${taskId}/config`}>
            继续配置生成
          </Link>
        ) : (
          <button
            type="button"
            className="primary-button"
            disabled={!canConfirm || confirmMutation.isPending}
            onClick={() => confirmMutation.mutate()}
          >
            {confirmMutation.isPending ? '确认中...' : '我已了解风险并继续'}
          </button>
        )}
      </footer>
    </section>
  )
}
