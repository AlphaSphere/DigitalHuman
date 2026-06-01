import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { SegmentEditor } from '../components/SegmentEditor'
import { StatusBadge } from '../components/StatusBadge'
import { StepNav } from '../components/StepNav'
import { getStatusMessage, mockApi } from '../lib/api-client/mockApi'
import type { ScriptSegment } from '../types/domain'

export function ScriptPage() {
  const { taskId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [draftSegments, setDraftSegments] = useState<ScriptSegment[] | null>(null)

  const taskQuery = useQuery({ queryKey: ['task', taskId], queryFn: () => mockApi.getTask(taskId) })
  const segmentQuery = useQuery({ queryKey: ['segments', taskId], queryFn: () => mockApi.getSegments(taskId) })

  const segments = draftSegments ?? segmentQuery.data ?? []

  const saveMutation = useMutation({
    mutationFn: () => mockApi.updateSegments(taskId, segments),
    onSuccess: (saved) => {
      setDraftSegments(saved)
      queryClient.invalidateQueries({ queryKey: ['segments', taskId] })
    },
  })

  const confirmMutation = useMutation({
    mutationFn: async () => {
      await mockApi.updateSegments(taskId, segments)
      return mockApi.confirmScript(taskId)
    },
    onSuccess: (task) => navigate(`/tasks/${task.id}/risk-review`),
  })

  if (taskQuery.isLoading || segmentQuery.isLoading) {
    return <div className="page">文案正在解析，请稍等。</div>
  }

  if (!taskQuery.data) {
    return <div className="page">任务不存在。</div>
  }

  return (
    <section className="page">
      <StepNav current={1} />
      <div className="page-heading row-heading">
        <div>
          <p className="eyebrow">文案确认</p>
          <h1>检查并确认最终文案</h1>
          <p>后续配音和字幕会优先使用编辑后的文本。</p>
        </div>
        <StatusBadge status={taskQuery.data.status} label={getStatusMessage(taskQuery.data.status)} />
      </div>

      <div className="script-layout">
        <aside className="panel preview-panel">
          <h2>来源预览</h2>
          <div className="video-placeholder">
            {taskQuery.data.script_source === 'video_asr' ? '参考视频预览' : '粘贴文案来源'}
          </div>
          <dl className="meta-list">
            <div>
              <dt>来源</dt>
              <dd>{taskQuery.data.script_source}</dd>
            </div>
            <div>
              <dt>比例</dt>
              <dd>{taskQuery.data.aspect_ratio}</dd>
            </div>
            <div>
              <dt>段落</dt>
              <dd>{segments.length} 段</dd>
            </div>
          </dl>
        </aside>

        <main className="panel">
          <SegmentEditor segments={segments} onChange={setDraftSegments} />
        </main>

        <aside className="panel">
          <h2>检查面板</h2>
          <p className="muted">
            低置信度片段会标记为“需检查”。确认文案后，系统会继续检查敏感词、隐私和 AI 标识风险。
          </p>
          <div className="stat-card">
            <strong>{segments.filter((segment) => segment.confidence && segment.confidence < 0.86).length}</strong>
            <span>个需检查片段</span>
          </div>
          <div className="stat-card">
            <strong>{segments.reduce((count, segment) => count + (segment.edited_text ?? '').length, 0)}</strong>
            <span>确认文本字数</span>
          </div>
        </aside>
      </div>

      <footer className="action-bar">
        <Link className="ghost-button" to="/tasks/new">
          返回创建
        </Link>
        <button className="secondary-button" type="button" onClick={() => saveMutation.mutate()}>
          {saveMutation.isPending ? '保存中...' : '保存草稿'}
        </button>
        <button className="primary-button" type="button" onClick={() => confirmMutation.mutate()}>
          {confirmMutation.isPending ? '确认中...' : '确认文案'}
        </button>
      </footer>
    </section>
  )
}
