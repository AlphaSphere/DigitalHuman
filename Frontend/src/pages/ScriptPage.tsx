/**
 * 用途：文案确认页，支持整段或分段时间轴两种编辑模式，保存并确认后进入风险检查。
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { SegmentEditor } from '../components/SegmentEditor'
import { StatusBadge } from '../components/StatusBadge'
import { StepNav } from '../components/StepNav'
import { getStatusMessage, mockApi } from '../lib/api-client/mockApi'
import type { ScriptGenerationMode, ScriptSegment } from '../types/domain'

/** 完整文案模式下的最大字符数限制。 */
const FULL_SCRIPT_MAX_LENGTH = 5000

/**
 * 取段落当前生效文本（编辑态优先于原文）。
 *
 * @param segment - ScriptSegment
 * @returns edited_text 或 original_text
 */
const getSegmentText = (segment: ScriptSegment) => segment.edited_text ?? segment.original_text

/**
 * 将多段文案合并为整段字符串（段间换行）。
 *
 * @param segments - 段落列表
 * @returns 合并后的完整文案
 */
const buildFullScript = (segments: ScriptSegment[]) => segments.map(getSegmentText).join('\n')

/**
 * 将整段文案包装为单条 ScriptSegment 供 API 提交。
 *
 * @param taskId - 任务 ID
 * @param text - 完整文案内容
 * @param segments - 原段落列表（用于复用 id 与时间范围）
 * @returns 长度为 1 的 ScriptSegment 数组
 */
const buildFullScriptSegment = (taskId: string, text: string, segments: ScriptSegment[]): ScriptSegment[] => [
  {
    id: segments[0]?.id ?? `seg_full_${taskId}`,
    task_id: taskId,
    index: 1,
    source_type: 'manual_edit',
    start_time: segments[0]?.start_time ?? null,
    end_time: segments.at(-1)?.end_time ?? null,
    original_text: text,
    edited_text: text,
    confidence: null,
  },
]

/**
 * 文案确认与编辑页面。
 *
 * @returns 含模式切换、编辑器与保存/确认操作的页面
 *
 * 逻辑：
 * - draftSegments 覆盖服务端数据实现本地草稿；
 * - full_script 模式提交单段，timed_segments 保留多段；
 * - confirmMutation 先 save 再 confirmScript，成功后跳转风险页。
 */
export function ScriptPage() {
  const { taskId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [draftSegments, setDraftSegments] = useState<ScriptSegment[] | null>(null)
  const [scriptModeOverride, setScriptModeOverride] = useState<ScriptGenerationMode | null>(null)
  const [fullScriptDraftOverride, setFullScriptDraftOverride] = useState<string | null>(null)

  const taskQuery = useQuery({ queryKey: ['task', taskId], queryFn: () => mockApi.getTask(taskId) })
  const segmentQuery = useQuery({ queryKey: ['segments', taskId], queryFn: () => mockApi.getSegments(taskId) })

  const segments = draftSegments ?? segmentQuery.data ?? []
  const scriptMode = scriptModeOverride ?? taskQuery.data?.script_generation_mode ?? 'full_script'
  const fullScriptDraft = fullScriptDraftOverride ?? buildFullScript(segments)
  const activeSegments =
    scriptMode === 'full_script' ? buildFullScriptSegment(taskId, fullScriptDraft, segments) : segments

  const saveMutation = useMutation({
    mutationFn: () => mockApi.updateSegments(taskId, activeSegments, scriptMode),
    onSuccess: (saved) => {
      setDraftSegments(saved)
      setFullScriptDraftOverride(buildFullScript(saved))
      queryClient.invalidateQueries({ queryKey: ['segments', taskId] })
    },
  })

  const confirmMutation = useMutation({
    mutationFn: async () => {
      await mockApi.updateSegments(taskId, activeSegments, scriptMode)
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
              <dd>{scriptMode === 'full_script' ? '完整文案' : `${segments.length} 段`}</dd>
            </div>
          </dl>
        </aside>

        <main className="panel">
          <div className="script-mode-switch">
            <button
              type="button"
              className={`select-card ${scriptMode === 'full_script' ? 'active' : ''}`}
              onClick={() => {
                setFullScriptDraftOverride(buildFullScript(segments))
                setScriptModeOverride('full_script')
              }}
            >
              <strong>完整文案生成</strong>
              <p>合并展示原视频完整文案，不按时间点拆分，适合只需要整段口播配音的自动生成。</p>
            </button>
            <button
              type="button"
              className={`select-card ${scriptMode === 'timed_segments' ? 'active' : ''}`}
              onClick={() => setScriptModeOverride('timed_segments')}
            >
              <strong>分段时间轴生成</strong>
              <p>保留每个时间点和对应文案，适合要按原视频节奏拼接、字幕对齐的自动生成。</p>
            </button>
          </div>

          {scriptMode === 'full_script' ? (
            <label className="full-script-editor">
              <span className="editor-label-row">
                完整原视频文案
                <small>{fullScriptDraft.length} / {FULL_SCRIPT_MAX_LENGTH}</small>
              </span>
              <textarea
                value={fullScriptDraft}
                onChange={(event) => setFullScriptDraftOverride(event.target.value)}
                maxLength={FULL_SCRIPT_MAX_LENGTH}
                rows={16}
                placeholder="这里展示完整原视频文案，可直接整体修改..."
              />
            </label>
          ) : (
            <SegmentEditor segments={segments} onChange={setDraftSegments} />
          )}
        </main>

        <aside className="panel">
          <h2>检查面板</h2>
          <p className="muted">
            低置信度片段会标记为“需检查”。确认文案后，系统会继续检查敏感词、隐私和 AI 标识风险。
          </p>
          <div className="stat-card">
            <strong>{scriptMode === 'full_script' ? 1 : segments.filter((segment) => segment.confidence && segment.confidence < 0.86).length}</strong>
            <span>{scriptMode === 'full_script' ? '段完整文案' : '个需检查片段'}</span>
          </div>
          <div className="stat-card">
            <strong>{activeSegments.reduce((count, segment) => count + getSegmentText(segment).length, 0)}</strong>
            <span>确认文本字数</span>
          </div>
          <div className="stat-card">
            <strong>{scriptMode === 'full_script' ? '整段' : '时间轴'}</strong>
            <span>自动化生成方式</span>
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
