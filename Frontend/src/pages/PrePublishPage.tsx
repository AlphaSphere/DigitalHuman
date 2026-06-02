/**
 * 用途：发布前合规检查页，填写平台发布信息、执行风险检查并创建分发任务。
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { RiskCard } from '../components/RiskCard'
import { RiskSummary } from '../components/RiskSummary'
import { StatusBadge } from '../components/StatusBadge'
import { getStatusMessage, mockApi } from '../lib/api-client/mockApi'
import type { PrePublishCheckInput, RiskCheck } from '../types/domain'

/** 支持的发布平台选项。 */
const platforms: Array<{ value: PrePublishCheckInput['platform']; label: string }> = [
  { value: 'douyin', label: '抖音' },
  { value: 'xiaohongshu', label: '小红书' },
  { value: 'bilibili', label: 'B 站' },
  { value: 'wechat_channels', label: '视频号' },
  { value: 'kuaishou', label: '快手' },
  { value: 'tiktok', label: 'TikTok' },
  { value: 'youtube', label: 'YouTube' },
]

/**
 * 发布前合规检查与平台分发页面。
 *
 * @returns 发布信息表单、风险结果侧栏与分发记录列表
 *
 * 逻辑：
 * - checkMutation 调用 runPrePublishCheck 并更新 activeRiskCheck；
 * - passed 可直接 createDistribution；warning/manual_review 需 confirmRiskCheck；
 * - blocked 禁止发布，需修改信息后重新检查。
 */
export function PrePublishPage() {
  const { taskId = '' } = useParams()
  const queryClient = useQueryClient()
  const [platform, setPlatform] = useState<PrePublishCheckInput['platform']>('douyin')
  const [title, setTitle] = useState('AI 数字人口播视频')
  const [description, setDescription] = useState('本视频使用 AI 数字人和 AI 配音生成，用于内容演示。')
  const [tags, setTags] = useState('AI数字人,口播,内容创作')
  const [aiLabelConfirmed, setAiLabelConfirmed] = useState(false)
  const [confirmationNote, setConfirmationNote] = useState('我会在发布时补充 AI 生成标识。')
  const [activeRiskCheck, setActiveRiskCheck] = useState<RiskCheck | null>(null)
  const [error, setError] = useState<string | null>(null)

  const taskQuery = useQuery({ queryKey: ['task', taskId], queryFn: () => mockApi.getTask(taskId) })
  const riskQuery = useQuery({
    queryKey: ['riskChecks', taskId, 'pre_publish'],
    queryFn: () => mockApi.getRiskChecks(taskId, 'pre_publish'),
  })
  const distributionQuery = useQuery({
    queryKey: ['distributions', taskId],
    queryFn: () => mockApi.getDistributions(taskId),
  })

  const latestRiskCheck = activeRiskCheck ?? riskQuery.data?.[0] ?? null

  const checkMutation = useMutation({
    mutationFn: () =>
      mockApi.runPrePublishCheck(taskId, {
        platform,
        title,
        description,
        tags: tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
        ai_label_confirmed: aiLabelConfirmed,
      }),
    onSuccess: (riskCheck) => {
      setError(null)
      setActiveRiskCheck(riskCheck)
      queryClient.invalidateQueries({ queryKey: ['task', taskId] })
      queryClient.invalidateQueries({ queryKey: ['riskChecks', taskId] })
    },
    onError: (err) => setError(err instanceof Error ? err.message : '发布前检查失败'),
  })

  const confirmMutation = useMutation({
    mutationFn: async () => {
      if (!latestRiskCheck) throw new Error('请先执行发布前合规检查')
      return mockApi.confirmRiskCheck(taskId, latestRiskCheck.id, confirmationNote)
    },
    onSuccess: ({ riskCheck }) => {
      setError(null)
      setActiveRiskCheck(riskCheck)
      queryClient.invalidateQueries({ queryKey: ['task', taskId] })
      queryClient.invalidateQueries({ queryKey: ['riskChecks', taskId] })
    },
    onError: (err) => setError(err instanceof Error ? err.message : '确认失败'),
  })

  const distributeMutation = useMutation({
    mutationFn: () =>
      mockApi.createDistribution(taskId, {
        platform,
        title,
        description,
        tags: tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
      }),
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['distributions', taskId] })
    },
    onError: (err) => setError(err instanceof Error ? err.message : '分发任务创建失败'),
  })

  const retryDistributionMutation = useMutation({
    mutationFn: (distributionId: string) => mockApi.retryDistribution(distributionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['distributions', taskId] }),
    onError: (err) => setError(err instanceof Error ? err.message : '分发重试失败'),
  })

  if (taskQuery.isLoading || riskQuery.isLoading) {
    return <div className="page">正在加载发布前检查...</div>
  }

  const task = taskQuery.data
  if (!task) return <div className="page">任务不存在。</div>

  const canConfirm =
    latestRiskCheck?.risk_status === 'warning' || latestRiskCheck?.risk_status === 'manual_review'
  const canPublish = latestRiskCheck?.risk_status === 'passed'
  const isBlocked = latestRiskCheck?.risk_status === 'blocked'

  return (
    <section className="page">
      <div className="page-heading row-heading">
        <div>
          <p className="eyebrow">发布前合规检查</p>
          <h1>检查标题、简介、标签和 AI 标识</h1>
          <p>不同平台规则不同，发布前先确认是否存在敏感词、极限词或 AI 标识遗漏。</p>
        </div>
        <StatusBadge status={task.status} label={getStatusMessage(task.status)} />
      </div>

      <div className="two-column prepublish-layout">
        <main className="panel">
          <h2>发布信息</h2>
          <label className="field-stack">
            发布平台
            <select value={platform} onChange={(event) => setPlatform(event.target.value as PrePublishCheckInput['platform'])}>
              {platforms.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-stack">
            标题
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label className="field-stack">
            简介
            <textarea rows={6} value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <label className="field-stack">
            标签
            <input value={tags} onChange={(event) => setTags(event.target.value)} />
            <span className="muted">多个标签用英文逗号分隔。</span>
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={aiLabelConfirmed}
              onChange={(event) => setAiLabelConfirmed(event.target.checked)}
            />
            我会在标题、简介或画面中添加 AI 生成标识。
          </label>
        </main>

        <aside className="panel">
          <RiskSummary riskCheck={latestRiskCheck ?? undefined} />
          <div className="risk-list compact">
            {latestRiskCheck?.findings.length ? (
              latestRiskCheck.findings.map((finding) => <RiskCard key={finding.id} finding={finding} />)
            ) : (
              <div className="empty-card">执行检查后会展示平台规则和发布风险。</div>
            )}
          </div>
          {canConfirm ? (
            <label className="field-stack">
              人工确认说明
              <textarea
                rows={4}
                value={confirmationNote}
                onChange={(event) => setConfirmationNote(event.target.value)}
              />
            </label>
          ) : null}
          {isBlocked ? <p className="form-error">当前平台禁止直接发布，请修改发布信息后重新检查。</p> : null}
          {error ? <p className="form-error">{error}</p> : null}
          <h2>分发记录</h2>
          <div className="artifact-list">
            {distributionQuery.data?.length ? (
              distributionQuery.data.map((record) => (
                <article key={record.id} className="artifact-card">
                  <div>
                    <strong>{record.platform} · {record.status}</strong>
                    <span>{record.external_url ?? record.error_message ?? record.title}</span>
                  </div>
                  {record.status === 'failed' ? (
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => retryDistributionMutation.mutate(record.id)}
                    >
                      重试
                    </button>
                  ) : null}
                </article>
              ))
            ) : (
              <div className="empty-card">通过发布前检查后，可以创建平台分发任务。</div>
            )}
          </div>
        </aside>
      </div>

      <footer className="action-bar">
        <Link className="ghost-button" to={`/tasks/${taskId}/result`}>
          返回结果页
        </Link>
        <button className="secondary-button" type="button" onClick={() => checkMutation.mutate()}>
          {checkMutation.isPending ? '检查中...' : '重新检查'}
        </button>
        {canConfirm ? (
          <button className="primary-button" type="button" onClick={() => confirmMutation.mutate()}>
            {confirmMutation.isPending ? '确认中...' : '确认并继续发布'}
          </button>
        ) : (
          <button
            className="primary-button"
            type="button"
            disabled={!canPublish || distributeMutation.isPending}
            onClick={() => distributeMutation.mutate()}
          >
            {distributeMutation.isPending ? '创建分发中...' : canPublish ? '发布到平台' : '等待检查通过'}
          </button>
        )}
      </footer>
    </section>
  )
}
