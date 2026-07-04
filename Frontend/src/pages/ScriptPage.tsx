/**
 * 用途：文案与合规页——识别/编辑文案、AI 仿写、AI 合规检查在同一页完成。
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { LineNumberTextarea, type LineNumberTextareaHandle } from '../components/LineNumberTextarea'
import { ScriptRewritePanel } from '../components/ScriptRewritePanel'
import { ScriptRiskPanel } from '../components/ScriptRiskPanel'
import { SegmentEditor } from '../components/SegmentEditor'
import { SourceVideoPreview } from '../components/SourceVideoPreview'
import { StatusBadge } from '../components/StatusBadge'
import { StepNav } from '../components/StepNav'
import { TranscribeProgressPanel } from '../components/TranscribeProgressPanel'
import { getStatusMessage, mockApi } from '../lib/api-client/mockApi'
import { buildHighlightSpans, getFindingSpan } from '../lib/scriptRiskHighlight'
import { isTranscribeFailure } from '../lib/scriptGate'
import type { RiskCheck, RiskFinding, ScriptGenerationMode, ScriptSegment } from '../types/domain'

const FULL_SCRIPT_MAX_LENGTH = 5000
const TRANSCRIBING_STATUSES = ['uploaded', 'transcribing', 'audio_extracted'] as const

const clampScript = (text: string) => text.slice(0, FULL_SCRIPT_MAX_LENGTH)

const getSegmentText = (segment: ScriptSegment) =>
  (segment.edited_text && segment.edited_text.trim()) || segment.original_text || ''

const buildFullScript = (segments: ScriptSegment[]) => segments.map(getSegmentText).join('\n')

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

export function ScriptPage() {
  const { taskId = '' } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const [draftSegments, setDraftSegments] = useState<ScriptSegment[] | null>(null)
  const [scriptModeOverride, setScriptModeOverride] = useState<ScriptGenerationMode | null>(null)
  const [fullScriptDraftOverride, setFullScriptDraftOverride] = useState<string | null>(null)
  const [confirmationNote, setConfirmationNote] = useState('已阅读风险提示，确认可以继续生成。')
  const [riskStale, setRiskStale] = useState(false)
  const [proceedError, setProceedError] = useState<string | null>(null)
  const [activeFindingId, setActiveFindingId] = useState<string | null>(null)
  const [pendingJumpFindingId, setPendingJumpFindingId] = useState<string | null>(null)
  const fullScriptEditorRef = useRef<LineNumberTextareaHandle>(null)
  const autoAiCheckOnceRef = useRef(false)

  const taskQuery = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => mockApi.getTask(taskId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && TRANSCRIBING_STATUSES.includes(status as (typeof TRANSCRIBING_STATUSES)[number]) ? 2000 : false
    },
  })

  const runtimeQuery = useQuery({
    queryKey: ['runtime-info'],
    queryFn: () => mockApi.getRuntimeInfo(),
    staleTime: 60_000,
  })

  const segmentQuery = useQuery({
    queryKey: ['segments', taskId],
    queryFn: () => mockApi.getSegments(taskId),
    enabled: !!taskId,
    staleTime: 0,
    refetchInterval: () => {
      const status = taskQuery.data?.status
      return status && TRANSCRIBING_STATUSES.includes(status as (typeof TRANSCRIBING_STATUSES)[number]) ? 2000 : false
    },
  })

  const segments = draftSegments ?? segmentQuery.data ?? []
  const scriptMode = scriptModeOverride ?? taskQuery.data?.script_generation_mode ?? 'full_script'
  const fullScriptDraft = clampScript(fullScriptDraftOverride ?? buildFullScript(segments))
  const isTranscribing = taskQuery.data?.status
    ? TRANSCRIBING_STATUSES.includes(taskQuery.data.status as (typeof TRANSCRIBING_STATUSES)[number])
    : false
  const hasScriptText = fullScriptDraft.trim().length > 0
  const transcribeFailed = isTranscribeFailure(taskQuery.data?.status, taskQuery.data?.error_code, hasScriptText)

  const riskQuery = useQuery({
    queryKey: ['riskChecks', taskId, 'script'],
    queryFn: () => mockApi.getRiskChecks(taskId, 'script'),
    enabled: !!taskId && hasScriptText && !isTranscribing,
  })

  const markRiskStale = () => setRiskStale(true)

  const retranscribeMutation = useMutation({
    mutationFn: () => mockApi.retranscribeVideo(taskId),
    onSuccess: () => {
      setDraftSegments(null)
      setFullScriptDraftOverride(null)
      setRiskStale(true)
      queryClient.invalidateQueries({ queryKey: ['segments', taskId] })
      queryClient.invalidateQueries({ queryKey: ['task', taskId] })
      queryClient.invalidateQueries({ queryKey: ['riskChecks', taskId] })
    },
  })

  const isFetchingScript = isTranscribing || retranscribeMutation.isPending

  const activeSegments =
    scriptMode === 'full_script' ? buildFullScriptSegment(taskId, fullScriptDraft, segments) : segments
  const scriptCharCount = activeSegments.reduce((count, segment) => count + getSegmentText(segment).length, 0)
  const reviewCount =
    scriptMode === 'full_script'
      ? 0
      : segments.filter((segment) => segment.confidence && segment.confidence < 0.86).length
  const riskCheck = useMemo<RiskCheck | undefined>(() => riskQuery.data?.[0], [riskQuery.data])
  const runtimeInfo = runtimeQuery.data
  const riskCheckMode = runtimeInfo?.risk_check_mode ?? (runtimeInfo?.has_deepseek_api_key ? 'ai' : 'rules')
  const isDeepSeekReady = Boolean(runtimeInfo?.has_deepseek_api_key)
  const isLegacyRiskCheck = riskCheck?.reviewed_by === 'system' && riskCheckMode === 'ai'
  const displayRiskCheck = isLegacyRiskCheck ? undefined : riskCheck
  const canUseCompliance = hasScriptText && !isTranscribing && !transcribeFailed
  const isStubMode = runtimeInfo?.use_stub_model_adapters ?? true
  const canRealTranscribe =
    runtimeInfo &&
    !runtimeInfo.use_stub_model_adapters &&
    runtimeInfo.has_yt_dlp &&
    runtimeInfo.has_ffmpeg &&
    (runtimeInfo.has_whisper_cli || Boolean(runtimeInfo.whisper_base_url))

  const modeHint = useMemo(
    () =>
      scriptMode === 'full_script'
        ? '整段口播，适合直接配音生成'
        : '按时间轴分段，适合字幕对齐与节奏拼接',
    [scriptMode],
  )

  const scriptHighlights = useMemo(() => {
    if (!canUseCompliance || riskStale || !displayRiskCheck?.findings.length) return []
    return buildHighlightSpans(fullScriptDraft, displayRiskCheck.findings)
  }, [fullScriptDraft, displayRiskCheck, canUseCompliance, riskStale])

  const handleJumpToFinding = (finding: RiskFinding) => {
    const span = getFindingSpan(finding, fullScriptDraft)
    if (!span) return
    setActiveFindingId(finding.id)
    if (scriptMode !== 'full_script') {
      setFullScriptDraftOverride(clampScript(buildFullScript(segments)))
      setScriptModeOverride('full_script')
      setPendingJumpFindingId(finding.id)
      return
    }
    requestAnimationFrame(() => {
      fullScriptEditorRef.current?.scrollToSpan(span)
      document.querySelector('.script-editor-body')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    })
  }

  useEffect(() => {
    if (!pendingJumpFindingId || scriptMode !== 'full_script') return
    const finding = displayRiskCheck?.findings.find((item) => item.id === pendingJumpFindingId)
    if (!finding) return
    const span = getFindingSpan(finding, fullScriptDraft)
    if (!span) return
    requestAnimationFrame(() => {
      fullScriptEditorRef.current?.scrollToSpan(span)
      document.querySelector('.script-editor-body')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      setPendingJumpFindingId(null)
    })
  }, [pendingJumpFindingId, scriptMode, fullScriptDraft, displayRiskCheck?.findings])

  useEffect(() => {
    // 任务状态从服务端变为 transcribed / 重新识别失败时，清空本地草稿并让 segments 重新拉取，
    // 属于「外部状态变化后重置本地编辑缓冲区」，不是内部状态间的级联同步。
    /* eslint-disable react-hooks/set-state-in-effect */
    const status = taskQuery.data?.status
    const errorCode = taskQuery.data?.error_code
    if (status === 'transcribed') {
      setDraftSegments(null)
      setFullScriptDraftOverride(null)
      queryClient.invalidateQueries({ queryKey: ['segments', taskId] })
      return
    }
    if (status === 'failed' && errorCode === 'TRANSCRIBE_FAILED') {
      setDraftSegments(null)
      setFullScriptDraftOverride(null)
      queryClient.invalidateQueries({ queryKey: ['segments', taskId] })
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [taskQuery.data?.status, taskQuery.data?.error_code, taskId, queryClient])

  const saveMutation = useMutation({
    mutationFn: () => mockApi.updateSegments(taskId, activeSegments, scriptMode),
    onSuccess: (saved) => {
      setDraftSegments(saved)
      setFullScriptDraftOverride(clampScript(buildFullScript(saved)))
      queryClient.invalidateQueries({ queryKey: ['segments', taskId] })
    },
  })

  const riskCheckMutation = useMutation({
    mutationFn: async () => {
      await mockApi.updateSegments(taskId, activeSegments, scriptMode)
      return mockApi.checkScriptRisk(taskId)
    },
    onSuccess: (result) => {
      setRiskStale(false)
      setProceedError(null)
      setActiveFindingId(null)
      queryClient.setQueryData(['riskChecks', taskId, 'script'], [result.riskCheck])
      queryClient.invalidateQueries({ queryKey: ['task', taskId] })
      queryClient.invalidateQueries({ queryKey: ['riskChecks', taskId] })
    },
    onError: (err) => setProceedError(err instanceof Error ? err.message : '合规检查失败'),
  })

  const { mutate: runRiskCheck, isPending: isRiskCheckPending } = riskCheckMutation

  const handleRewriteComplete = () => {
    autoAiCheckOnceRef.current = false
    setRiskStale(false)
    setProceedError(null)
    runRiskCheck()
  }

  const needsRiskRefresh =
    canUseCompliance &&
    !riskStale &&
    !isTranscribing &&
    (isLegacyRiskCheck || (riskQuery.isFetched && !riskCheck))

  const isComplianceChecking = isRiskCheckPending || (needsRiskRefresh && !displayRiskCheck)

  useEffect(() => {
    autoAiCheckOnceRef.current = false
  }, [taskId])

  useEffect(() => {
    const focusCompliance = (location.state as { focusCompliance?: boolean } | null)?.focusCompliance
    if (!focusCompliance) return
    const timer = window.setTimeout(() => {
      document.getElementById('script-compliance')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 120)
    return () => window.clearTimeout(timer)
  }, [location.state, taskId, displayRiskCheck?.id])

  useEffect(() => {
    if (!needsRiskRefresh) return
    if (riskQuery.isLoading || isRiskCheckPending) return
    if (autoAiCheckOnceRef.current) return
    autoAiCheckOnceRef.current = true
    runRiskCheck()
  }, [needsRiskRefresh, riskQuery.isLoading, isRiskCheckPending, runRiskCheck])

  const proceedMutation = useMutation({
    mutationFn: async () => {
      // 已确认且文案未改：直接进配置，切勿先 save（save 会把 script_confirmed 打回 transcribed）
      if (taskQuery.data?.status === 'script_confirmed' && !riskStale) {
        return taskQuery.data
      }

      await mockApi.updateSegments(taskId, activeSegments, scriptMode)

      const shouldRefreshCheck =
        riskStale || isLegacyRiskCheck || !displayRiskCheck || !riskQuery.isFetched
      if (shouldRefreshCheck) {
        const checked = await mockApi.checkScriptRisk(taskId)
        setRiskStale(false)
        setActiveFindingId(null)
        queryClient.setQueryData(['riskChecks', taskId, 'script'], [checked.riskCheck])
        queryClient.invalidateQueries({ queryKey: ['task', taskId] })
        if (checked.riskCheck.risk_status === 'blocked') {
          throw new Error('内容存在高风险，请修改文案标注的问题后重新检查')
        }
      } else if (displayRiskCheck?.risk_status === 'blocked') {
        throw new Error('内容存在高风险，请修改文案标注的问题后重新检查')
      }

      const note = confirmationNote.trim() || '已阅读风险提示，确认可以继续生成。'
      const resultTask = await mockApi.confirmScript(taskId, note)
      if (resultTask.status !== 'script_confirmed') {
        throw new Error('未能进入配置步骤，请稍后重试')
      }
      return resultTask
    },
    onSuccess: (resultTask) => {
      setProceedError(null)
      setRiskStale(false)
      queryClient.setQueryData(['task', taskId], resultTask)
      queryClient.invalidateQueries({ queryKey: ['task', taskId] })
      queryClient.invalidateQueries({ queryKey: ['riskChecks', taskId] })
      navigate(`/tasks/${taskId}/config`, { state: { skipConfigGuard: true } })
    },
    onError: (err) => {
      const message = err instanceof Error ? err.message : '无法进入下一步'
      setProceedError(message)
      requestAnimationFrame(() => {
        document.querySelector('.script-proceed-error')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      })
    },
  })

  const isRiskBlocked = displayRiskCheck?.risk_status === 'blocked' && !riskStale
  const hasScriptContent = scriptMode === 'full_script' ? !!fullScriptDraft.trim() : segments.length > 0
  const canProceed =
    canUseCompliance && hasScriptContent && !isTranscribing && !proceedMutation.isPending && !isRiskBlocked

  if (taskQuery.isLoading) {
    return (
      <section className="page script-page">
        <StepNav current={1} />
        <TranscribeProgressPanel status="uploaded" pending title="正在加载任务" />
      </section>
    )
  }

  if (!taskQuery.data) {
    return <div className="page">任务不存在。</div>
  }

  return (
    <section className="page script-page">
      <StepNav current={1} />
      <div className="page-heading row-heading">
        <div>
          <p className="eyebrow">文案与合规</p>
          <h1>编辑文案并完成 AI 合规检查</h1>
          <p>在同一页完成文案确认、DeepSeek 仿写与内容风险扫描，通过后再进入生成配置。</p>
        </div>
        <StatusBadge status={taskQuery.data.status} label={getStatusMessage(taskQuery.data.status)} />
      </div>

      {isStubMode && taskQuery.data.script_source === 'video_asr' ? (
        <div className="panel transcribe-hint stub-mode-banner">
          <strong>当前为演示模式（Stub）</strong>
          <p>
            链接识别不会调用真实 Whisper，只会填入约 60 字的示例文案。要识别原视频口播，请在 `.env` 中设置
            `USE_STUB_MODEL_ADAPTERS=false`，并安装 yt-dlp、ffmpeg、openai-whisper 后重启应用。
          </p>
          {runtimeInfo && !canRealTranscribe ? (
            <p className="muted">
              依赖检测：yt-dlp {runtimeInfo.has_yt_dlp ? '✓' : '✗'} · ffmpeg {runtimeInfo.has_ffmpeg ? '✓' : '✗'} ·
              whisper {runtimeInfo.has_whisper_cli || runtimeInfo.whisper_base_url ? '✓' : '✗'}
            </p>
          ) : null}
        </div>
      ) : null}

      {isFetchingScript && taskQuery.data.script_source === 'video_asr' ? (
        <TranscribeProgressPanel
          status={taskQuery.data.status}
          pending={retranscribeMutation.isPending && !isTranscribing}
        />
      ) : null}

      {transcribeFailed ? (
        <div className="panel form-error transcribe-hint">
          <strong>视频文案识别失败</strong>
          <p>{taskQuery.data.error_message ?? '请检查链接是否公开可访问，或安装 yt-dlp / whisper 后重试。'}</p>
          <button
            type="button"
            className="secondary-button"
            disabled={retranscribeMutation.isPending}
            onClick={() => retranscribeMutation.mutate()}
          >
            {retranscribeMutation.isPending ? '重新识别中...' : '重新识别文案'}
          </button>
        </div>
      ) : null}

      {!isTranscribing && !transcribeFailed && !hasScriptText ? (
        <div className="panel muted transcribe-hint">
          未获取到文案。若当前为演示模式（Stub），只会显示示例文本；真实识别需关闭 Stub 并安装 yt-dlp、Whisper。
          <button
            type="button"
            className="secondary-button"
            disabled={retranscribeMutation.isPending}
            onClick={() => retranscribeMutation.mutate()}
          >
            重新识别
          </button>
        </div>
      ) : null}

      <div className="script-layout">
        <aside className="panel preview-panel">
          <h2>参考视频</h2>
          <SourceVideoPreview task={taskQuery.data} hasScriptText={hasScriptText} />
          <dl className="meta-list compact">
            <div>
              <dt>来源</dt>
              <dd>{taskQuery.data.script_source}</dd>
            </div>
            <div>
              <dt>画幅</dt>
              <dd>{taskQuery.data.aspect_ratio}</dd>
            </div>
          </dl>
        </aside>

        <section className="panel script-workspace">
          <header className="script-workspace-header">
            <div className="script-workspace-intro">
              <h2>文案工作区</h2>
              <p className="muted">{modeHint}</p>
            </div>
            <div className="script-workspace-tools">
              <div className="script-mode-tabs" role="tablist" aria-label="文案生成模式">
                <button
                  type="button"
                  role="tab"
                  aria-selected={scriptMode === 'full_script'}
                  className={scriptMode === 'full_script' ? 'active' : ''}
                  onClick={() => {
                    setFullScriptDraftOverride(clampScript(buildFullScript(segments)))
                    setScriptModeOverride('full_script')
                    markRiskStale()
                  }}
                >
                  完整文案
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={scriptMode === 'timed_segments'}
                  className={scriptMode === 'timed_segments' ? 'active' : ''}
                  onClick={() => {
                    setScriptModeOverride('timed_segments')
                    markRiskStale()
                  }}
                >
                  分段时间轴
                </button>
              </div>
              <div className="script-meta-chips" aria-label="文案统计">
                <span>{scriptCharCount} 字</span>
                <span>{scriptMode === 'full_script' ? '整段生成' : `${segments.length} 段`}</span>
                {reviewCount > 0 ? <span className="warn">{reviewCount} 处需检查</span> : null}
              </div>
            </div>
          </header>

          <ScriptRewritePanel
            taskId={taskId}
            disabled={isTranscribing || !hasScriptText}
            scriptCharCount={scriptCharCount}
            runtimeInfo={runtimeInfo}
            onRewritten={(nextSegments) => {
              setDraftSegments(nextSegments)
              setFullScriptDraftOverride(clampScript(buildFullScript(nextSegments)))
              queryClient.invalidateQueries({ queryKey: ['segments', taskId] })
              queryClient.invalidateQueries({ queryKey: ['task', taskId] })
            }}
            onRewriteComplete={handleRewriteComplete}
          />

          <div className="script-editor-body">
            {isFetchingScript && taskQuery.data.script_source === 'video_asr' ? (
              <p className="muted">文案识别完成后将自动填入此处，请稍候。</p>
            ) : scriptMode === 'full_script' ? (
              <label className="full-script-editor">
                <span className="editor-label-row">
                  完整原视频文案
                  <small>
                    {fullScriptDraft.length} / {FULL_SCRIPT_MAX_LENGTH}
                  </small>
                </span>
                <LineNumberTextarea
                  ref={fullScriptEditorRef}
                  value={fullScriptDraft}
                  onChange={(value) => {
                    setFullScriptDraftOverride(clampScript(value))
                    markRiskStale()
                    setActiveFindingId(null)
                  }}
                  highlights={scriptHighlights}
                  activeHighlightId={activeFindingId}
                  maxLength={FULL_SCRIPT_MAX_LENGTH}
                  rows={16}
                  placeholder="这里展示完整原视频文案，可直接整体修改..."
                  aria-label="完整原视频文案"
                />
              </label>
            ) : segments.length > 0 ? (
              <SegmentEditor
                segments={segments}
                scriptHighlights={scriptHighlights}
                activeHighlightId={activeFindingId}
                onChange={(nextSegments) => {
                  setDraftSegments(nextSegments)
                  markRiskStale()
                  setActiveFindingId(null)
                }}
              />
            ) : (
              <p className="muted">暂无文案段落，请等待识别完成或返回重新创建任务。</p>
            )}
          </div>

          {canUseCompliance && riskCheckMode === 'rules' ? (
            <p className="script-risk-hint muted">
              当前未配置 DeepSeek，合规检查使用内置关键词规则（仅供参考）。建议在 `.env` 配置 `DEEPSEEK_API_KEY` 以启用 AI 合规。
            </p>
          ) : null}

          {canUseCompliance ? (
            <ScriptRiskPanel
              riskCheck={displayRiskCheck}
              riskStale={riskStale}
              checking={isComplianceChecking}
              disabled={isTranscribing || !hasScriptText}
              deepSeekReady={isDeepSeekReady}
              riskCheckMode={riskCheckMode}
              activeFindingId={activeFindingId}
              confirmationNote={confirmationNote}
              onConfirmationNoteChange={setConfirmationNote}
              onRunCheck={() => {
                autoAiCheckOnceRef.current = false
                runRiskCheck()
              }}
              onJumpToFinding={handleJumpToFinding}
            />
          ) : null}

          {proceedError ? <p className="form-error script-proceed-error">{proceedError}</p> : null}

          <footer className="action-bar script-action-bar">
            <Link className="ghost-button" to="/tasks/new">
              返回创建
            </Link>
            <button className="secondary-button" type="button" onClick={() => saveMutation.mutate()} disabled={isTranscribing}>
              {saveMutation.isPending ? '保存中...' : '保存草稿'}
            </button>
            {isComplianceChecking ? (
              <p className="muted script-proceed-hint">合规检查进行中，也可直接点击继续（将自动完成确认）。</p>
            ) : riskStale ? (
              <p className="muted script-proceed-hint">文案已修改，点击后将自动重新检查并进入配置。</p>
            ) : isRiskBlocked ? (
              <p className="form-error script-proceed-hint">内容被阻断，请修改标注问题后再继续。</p>
            ) : displayRiskCheck &&
                (displayRiskCheck.risk_status === 'warning' || displayRiskCheck.risk_status === 'manual_review') ? (
              <p className="muted script-proceed-hint">有提示项也可直接继续，无需修改文案。</p>
            ) : null}
            <button
              className="primary-button"
              type="button"
              onClick={() => proceedMutation.mutate()}
              disabled={isTranscribing || proceedMutation.isPending || !canProceed}
              title={!canProceed && isRiskBlocked ? '请先修改文案中的高风险内容' : undefined}
            >
              {proceedMutation.isPending ? '检查并进入配置...' : '继续配置生成'}
            </button>
          </footer>
        </section>
      </div>
    </section>
  )
}
