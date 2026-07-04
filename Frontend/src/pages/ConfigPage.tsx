/**
 * 用途：生成配置页，选择音色、数字人/自拍视频、字幕样式与背景音乐，保存并启动生成。
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { BackgroundMusicPicker } from '../components/BackgroundMusicPicker'
import { GenerationFailureModal } from '../components/GenerationFailureModal'
import { ScriptGateLink } from '../components/ScriptGateLink'
import { FileDrop } from '../components/FileDrop'
import { SubtitleStyleControls } from '../components/SubtitleStyleControls'
import { TtsSpeedControl } from '../components/TtsSpeedControl'
import { StatusBadge } from '../components/StatusBadge'
import { StepNav } from '../components/StepNav'
import { resolveTaskQueryFallback } from '../components/TaskQueryFallback'
import { getStatusMessage, mockApi } from '../lib/api-client/mockApi'
import { parseGenerationFailure } from '../lib/generationFailure'
import { resolveScriptGate } from '../lib/scriptGate'
import { formatModelServiceLabel, hasStubModelMode, probeModelServices } from '../lib/modelServiceStatus'
import { buildTaskStepUrl, canAccessConfigPage, isGenerationInProgress } from '../lib/taskFlow'
import type { BackgroundMusicMode, GenerationVideoMode, GenerationVoiceMode, GenerationQuality, SubtitleStyle } from '../types/domain'

const DEFAULT_SUBTITLE_STYLE: SubtitleStyle = {
  enabled: true,
  font_size: 20,
  position: 'bottom',
  color: '#FFFFFF',
  stroke: true,
  font_family: 'SimHei',
}

/** 将任务画幅映射为预览框样式类名。 */
function getPreviewRatioClass(aspectRatio?: string | null) {
  if (aspectRatio === '16:9') return 'ratio-16-9'
  if (aspectRatio === '1:1') return 'ratio-1-1'
  return 'ratio-9-16'
}

/**
 * 生成参数配置页面。
 *
 * @returns 音色/成片素材/字幕/音乐配置表单与预览侧栏
 *
 * 逻辑：
 * - 默认使用上传音色与自拍视频，满足用户克隆本人音色与形象的主流程；
 * - uploaded_voice/uploaded_video 模式需上传文件并勾选授权；
 * - submitConfig 校验完整性后 save 或 save+startGenerate；
 * - 文案未确认时禁止启动生成并引导回文案页。
 */
export function ConfigPage() {
  const { taskId = '' } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const hydratedRef = useRef(false)

  const taskQuery = useQuery({ queryKey: ['task', taskId], queryFn: () => mockApi.getTask(taskId) })
  const runtimeQuery = useQuery({ queryKey: ['runtime-info'], queryFn: () => mockApi.getRuntimeInfo(), staleTime: 60_000 })
  const modelHealthQuery = useQuery({
    queryKey: ['model-service-health'],
    queryFn: probeModelServices,
    staleTime: 30_000,
    refetchInterval: 60_000,
  })
  const riskQuery = useQuery({
    queryKey: ['riskChecks', taskId, 'script'],
    queryFn: () => mockApi.getRiskChecks(taskId, 'script'),
    enabled: !!taskId,
  })
  const voiceQuery = useQuery({ queryKey: ['voiceProfiles'], queryFn: mockApi.getVoiceProfiles })
  const avatarQuery = useQuery({ queryKey: ['avatarProfiles'], queryFn: mockApi.getAvatarProfiles })
  const musicQuery = useQuery({ queryKey: ['musicTracks'], queryFn: mockApi.getMusicTracks })
  const refetchMusicTracks = musicQuery.refetch

  const [voiceId, setVoiceId] = useState('voice_default_female')
  const [generationVoiceMode, setGenerationVoiceMode] = useState<GenerationVoiceMode>('uploaded_voice')
  const [customVoiceFile, setCustomVoiceFile] = useState<File | null>(null)
  const [customVoicePromptText, setCustomVoicePromptText] = useState('')
  const [avatarId, setAvatarId] = useState('avatar_studio_a')
  const [generationVideoMode, setGenerationVideoMode] = useState<GenerationVideoMode>('uploaded_video')
  const [customVideoFile, setCustomVideoFile] = useState<File | null>(null)
  const [authorizationConfirmed, setAuthorizationConfirmed] = useState(false)
  const [backgroundMusicPath, setBackgroundMusicPath] = useState('')
  const [backgroundMusicMode, setBackgroundMusicMode] = useState<BackgroundMusicMode>('fixed')
  const [backgroundMusicVolume, setBackgroundMusicVolume] = useState(0.18)
  const [voiceSpeed, setVoiceSpeed] = useState(1)
  const [aiWatermarkEnabled, setAiWatermarkEnabled] = useState(false)
  const [exportWithoutSubtitle, setExportWithoutSubtitle] = useState(false)
  const [avatarEngine, setAvatarEngine] = useState<'heygem' | 'tuilionnx'>('heygem')
  const [generationQuality, setGenerationQuality] = useState<GenerationQuality>('full')
  const [tuilionnxSyncOffset, setTuilionnxSyncOffset] = useState(0)
  const [hasTriedSubmit, setHasTriedSubmit] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [subtitleStyle, setSubtitleStyle] = useState<SubtitleStyle>(DEFAULT_SUBTITLE_STYLE)
  const [failureModalOpen, setFailureModalOpen] = useState(false)

  const task = taskQuery.data
  const latestRiskCheck = riskQuery.data?.[0] ?? null

  useEffect(() => {
    if (!task || taskQuery.isLoading || taskQuery.isFetching) return
    if ((location.state as { skipConfigGuard?: boolean } | null)?.skipConfigGuard) return
    if (isGenerationInProgress(task.status)) {
      navigate(buildTaskStepUrl(taskId, task.status, task.error_code), { replace: true })
      return
    }
    if (!canAccessConfigPage(task.status, task.error_code)) {
      navigate(buildTaskStepUrl(taskId, task.status, task.error_code), { replace: true })
    }
  }, [location.state, navigate, task, taskId, taskQuery.isFetching, taskQuery.isLoading])

  useEffect(() => {
    // 仅在任务首次加载时把服务端数据灌入本地可编辑表单状态，hydratedRef 保证只跑一次，
    // 之后的用户编辑不会被覆盖；这里不是「同步状态」意义上的级联更新。
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!task || hydratedRef.current) return
    hydratedRef.current = true
    if (task.voice_profile_id) setVoiceId(task.voice_profile_id)
    if (task.avatar_profile_id) setAvatarId(task.avatar_profile_id)
    if (task.generation_voice_mode) {
      // 已上传音色样本时，优先保持「上传自己的音色」，避免误用默认音色
      setGenerationVoiceMode(
        task.custom_voice_path && task.generation_voice_mode === 'preset_voice'
          ? 'uploaded_voice'
          : task.generation_voice_mode,
      )
    } else if (task.custom_voice_path) {
      setGenerationVoiceMode('uploaded_voice')
    }
    if (task.custom_voice_prompt_text) setCustomVoicePromptText(task.custom_voice_prompt_text)
    if (task.generation_video_mode) {
      setGenerationVideoMode(
        task.custom_video_path && task.generation_video_mode === 'preset_avatar'
          ? 'uploaded_video'
          : task.generation_video_mode,
      )
    } else if (task.custom_video_path) {
      setGenerationVideoMode('uploaded_video')
    }
    if (task.custom_voice_path || task.custom_video_path) {
      setAuthorizationConfirmed(true)
    }
    if (task.subtitle_style) {
      const loaded = task.subtitle_style
      // 兼容旧版默认字号 42，回落到当前默认 20
      setSubtitleStyle(
        loaded.font_size === 42
          ? { ...DEFAULT_SUBTITLE_STYLE, ...loaded, font_size: 20 }
          : loaded,
      )
    }
    if (typeof task.voice_speed === 'number') setVoiceSpeed(task.voice_speed)
    if (task.background_music_path) setBackgroundMusicPath(task.background_music_path)
    if (task.background_music_mode) setBackgroundMusicMode(task.background_music_mode)
    if (typeof task.background_music_volume === 'number') setBackgroundMusicVolume(task.background_music_volume)
    if (typeof task.ai_watermark_enabled === 'boolean') setAiWatermarkEnabled(task.ai_watermark_enabled)
    if (typeof task.export_without_subtitle === 'boolean') setExportWithoutSubtitle(task.export_without_subtitle)
    if (task.avatar_engine) setAvatarEngine(task.avatar_engine)
    if (task.generation_quality) setGenerationQuality(task.generation_quality)
    if (typeof task.tuilionnx_sync_offset === 'number') setTuilionnxSyncOffset(task.tuilionnx_sync_offset)
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [task])

  const saveConfigMutation = useMutation({
    mutationFn: async () => {
      setError(null)
      return mockApi.saveGenerationConfig(taskId, {
        voice_profile_id: voiceId,
        avatar_profile_id: avatarId,
        generation_voice_mode: generationVoiceMode,
        custom_voice_file: customVoiceFile,
        custom_voice_file_name: customVoiceFile?.name,
        custom_voice_prompt_text: generationVoiceMode === 'uploaded_voice' ? customVoicePromptText.trim() : null,
        generation_video_mode: generationVideoMode,
        custom_video_file: customVideoFile,
        custom_video_file_name: customVideoFile?.name,
        authorization_confirmed: authorizationConfirmed,
        aspect_ratio: task?.aspect_ratio ?? '9:16',
        subtitle_style: subtitleStyle,
        background_music_path: backgroundMusicMode === 'fixed' ? backgroundMusicPath || null : null,
        background_music_mode: backgroundMusicMode,
        background_music_volume: backgroundMusicVolume,
        voice_speed: voiceSpeed,
        ai_watermark_enabled: aiWatermarkEnabled,
        export_without_subtitle: exportWithoutSubtitle,
        avatar_engine: avatarEngine,
        generation_quality: generationQuality,
        tuilionnx_sync_offset: tuilionnxSyncOffset,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task', taskId] })
    },
    onError: (err) => setError(err instanceof Error ? err.message : '保存配置失败'),
  })

  const startMutation = useMutation({
    mutationFn: async () => {
      await saveConfigMutation.mutateAsync()
      return mockApi.startGenerate(taskId)
    },
    onSuccess: (nextTask) => {
      queryClient.invalidateQueries({ queryKey: ['task', taskId] })
      navigate(`/tasks/${nextTask.id}/progress`)
    },
    onError: (err) => setError(err instanceof Error ? err.message : '启动生成失败'),
  })

  const selectedVoice = voiceQuery.data?.find((voice) => voice.id === voiceId)
  const selectedAvatar = avatarQuery.data?.find((avatar) => avatar.id === avatarId)
  const needsMaterialAuthorization = generationVoiceMode === 'uploaded_voice' || generationVideoMode === 'uploaded_video'
  const needsCustomVoice = generationVoiceMode === 'uploaded_voice' && !customVoiceFile && !task?.custom_voice_path
  const recommendsCustomVoicePrompt = generationVoiceMode === 'uploaded_voice' && !customVoicePromptText.trim()
  const needsCustomVideo = generationVideoMode === 'uploaded_video' && !customVideoFile && !task?.custom_video_path
  const needsAuthorizationConfirmation = needsMaterialAuthorization && !authorizationConfirmed

  const scriptGate = useMemo(
    () =>
      resolveScriptGate({
        status: task?.status,
        errorCode: task?.error_code,
        latestRiskCheck,
      }),
    [task?.status, task?.error_code, latestRiskCheck],
  )

  const configIssues = useMemo(() => {
    const issues: string[] = []
    if (needsCustomVoice) issues.push('请上传音色样本，或切换为「使用默认音色」')
    if (needsCustomVideo) issues.push('请上传自拍视频，或切换为「使用默认数字人」')
    if (needsAuthorizationConfirmation) issues.push('请勾选上传素材的合法使用授权')
    return issues
  }, [needsCustomVoice, recommendsCustomVoicePrompt, needsCustomVideo, needsAuthorizationConfirmation])

  const isConfigIncomplete = configIssues.length > 0
  const isBusy = saveConfigMutation.isPending || startMutation.isPending
  const canStartGenerate = !scriptGate.blocked && !isConfigIncomplete && !isBusy
  const previewRatioClass = getPreviewRatioClass(task?.aspect_ratio)
  const previewMaterialLabel =
    generationVideoMode === 'uploaded_video'
      ? customVideoFile?.name || (task?.custom_video_path ? '已保存自拍视频' : '待上传素材')
      : selectedAvatar?.name ?? '默认数字人'
  const previewVoiceLabel =
    generationVoiceMode === 'uploaded_voice'
      ? customVoiceFile?.name || (task?.custom_voice_path ? '已保存音色样本' : '待上传音色')
      : selectedVoice?.name ?? '默认音色'

  const submitConfig = (action: 'save' | 'start') => {
    setHasTriedSubmit(true)
    setError(null)
    if (scriptGate.blocked) return
    if (isConfigIncomplete) return

    if (action === 'save') {
      saveConfigMutation.mutate()
      return
    }
    startMutation.mutate()
  }

  const modelHealth = modelHealthQuery.data
  const cosyvoiceHealth = {
    ok: runtimeQuery.data?.cosyvoice_ok ?? modelHealth?.cosyvoice.ok ?? false,
    mode: runtimeQuery.data?.cosyvoice_mode ?? modelHealth?.cosyvoice.mode ?? null,
  }
  const heygemHealth = {
    ok: runtimeQuery.data?.heygem_ok ?? modelHealth?.heygem.ok ?? false,
    mode: runtimeQuery.data?.heygem_mode ?? modelHealth?.heygem.mode ?? null,
  }
  const tuilionnxHealth = {
    ok: runtimeQuery.data?.tuilionnx_ok ?? modelHealth?.tuilionnx.ok ?? false,
    mode: runtimeQuery.data?.tuilionnx_mode ?? modelHealth?.tuilionnx.mode ?? null,
  }
  const showStubHint =
    [cosyvoiceHealth.mode, heygemHealth.mode, tuilionnxHealth.mode].includes('stub') ||
    (modelHealth ? hasStubModelMode(modelHealth) : false)

  if (taskQuery.isLoading || voiceQuery.isLoading || avatarQuery.isLoading || musicQuery.isLoading) {
    return <div className="page">正在加载生成配置...</div>
  }

  const taskFallback = resolveTaskQueryFallback({
    query: taskQuery,
    loadingMessage: '正在加载生成配置...',
  })
  if (taskFallback) return taskFallback

  if (!task) return <div className="page">任务不存在。</div>

  const generationFailure =
    task.status === 'failed' ? parseGenerationFailure(task.error_code, task.error_message) : null

  return (
    <section className="page config-page">
      <StepNav current={2} />
      <div className="page-heading row-heading">
        <div>
          <p className="eyebrow">生成配置</p>
          <h1>选择音色、数字人和字幕样式</h1>
          <p>配置会保存到任务中，后续会使用这些参数生成配音、数字人画面与字幕。</p>
        </div>
        <StatusBadge
          status={task.status}
          label={getStatusMessage(task.status)}
          onClick={generationFailure ? () => setFailureModalOpen(true) : undefined}
          title={generationFailure ? '点击查看生成失败详情' : undefined}
        />
      </div>

      {generationFailure ? (
        <GenerationFailureModal
          failure={generationFailure}
          open={failureModalOpen}
          onClose={() => setFailureModalOpen(false)}
          note="系统已保留文案和中间产物。请根据详细错误排查，修复后到生成进度页重试。"
          cosyvoiceHint={
            runtimeQuery.data?.cosyvoice_mode === 'unconfigured' && generationFailure.category === 'dubbing'
              ? '检测到 8002 配音服务未配置。请在 `.env` 设置 `ALLOW_MODEL_SERVICE_STUB_OUTPUT=true` 并重启。'
              : null
          }
          actions={
            <>
              <Link className="ghost-button" to={`/tasks/${taskId}/script`} onClick={() => setFailureModalOpen(false)}>
                返回文案与合规
              </Link>
              <Link className="primary-button" to={`/tasks/${taskId}/progress`} onClick={() => setFailureModalOpen(false)}>
                去生成进度重试
              </Link>
            </>
          }
        />
      ) : null}

      {scriptGate.blocked ? (
        <div className="panel config-gate-banner">
          <strong>还不能开始生成</strong>
          <p>{scriptGate.message}</p>
          <div className="config-gate-actions">
            {scriptGate.primaryAction ? (
              <ScriptGateLink
                taskId={taskId}
                action={scriptGate.primaryAction}
                className="secondary-button"
              />
            ) : null}
            {scriptGate.secondaryAction ? (
              <ScriptGateLink
                taskId={taskId}
                action={scriptGate.secondaryAction}
                className="ghost-button"
              />
            ) : null}
          </div>
        </div>
      ) : (
        <div className="panel config-quick-tip">
          <strong>上传素材</strong>
          <span>已默认选中「上传自己的音色」与「上传自己拍的视频」。请上传素材并勾选授权后再开始生成；如需快速试跑，可在下方切换为默认音色与数字人。</span>
        </div>
      )}

      {(runtimeQuery.data || modelHealth) && !scriptGate.blocked ? (
        <div className="panel config-model-banner">
          <strong>模型服务状态</strong>
          <span>
            CosyVoice（8002）{formatModelServiceLabel(cosyvoiceHealth)}
            {' · '}
            HeyGem（8003）{formatModelServiceLabel(heygemHealth)}
            {' · '}
            TuiliONNX（8004）{formatModelServiceLabel(tuilionnxHealth)}
            {showStubHint ? '（当前为占位模式，非真实 AI 配音/口型）' : ''}
          </span>
        </div>
      ) : null}

      <div className="config-workspace panel">
        <div className="config-workspace-body two-column">
          <main className="config-panel">
            <section className="config-section">
              <div className="config-section-head">
                <h2>音色选择</h2>
                <p>决定成片配音的来源与风格。</p>
              </div>
              <div className="material-mode-grid">
                <button
                  type="button"
                  className={`select-card ${generationVoiceMode === 'uploaded_voice' ? 'active' : ''}`}
                  onClick={() => {
                    setGenerationVoiceMode('uploaded_voice')
                  }}
                >
                  <strong>上传自己的音色</strong>
                  <span>上传本人或已获授权的声音样本，用前面确认过的文案生成专属配音。</span>
                </button>
                <button
                  type="button"
                  className={`select-card ${generationVoiceMode === 'preset_voice' ? 'active' : ''}`}
                  onClick={() => {
                    setGenerationVoiceMode('preset_voice')
                    setCustomVoiceFile(null)
                  }}
                >
                  <strong>使用默认音色</strong>
                  <span>直接选择系统内置音色，适合快速生成样片或没有授权声音素材时使用。</span>
                </button>
              </div>

              {generationVoiceMode === 'uploaded_voice' ? (
                <div className="custom-media-card">
                  <FileDrop
                    file={customVoiceFile}
                    onChange={setCustomVoiceFile}
                    accept="audio/*,.wav,.mp3,.m4a,.aac,.ogg"
                    title="拖拽音频到这里，或点击选择文件"
                    description="支持 WAV / MP3 / M4A，建议 3-8 秒清晰人声"
                  />
                  {task.custom_voice_path && !customVoiceFile ? (
                    <p className="muted config-saved-hint">已保存音色样本，重新上传可替换。</p>
                  ) : null}
                  <label className="field-stack">
                    <span>音色样本文本</span>
                    <textarea
                      value={customVoicePromptText}
                      onChange={(event) => setCustomVoicePromptText(event.target.value)}
                      rows={3}
                      maxLength={500}
                      placeholder="请填写上传音频里实际说的话，例如：大家好，我是 Jaden，今天分享一个项目进展。"
                    />
                    <small>
                      建议上传 3-8 秒清晰人声，并填写与音频完全一致的文字；填写后可启用更快更稳的 zero-shot 克隆，不填也能克隆（速度较慢）。
                    </small>
                    {recommendsCustomVoicePrompt ? (
                      <p className="muted config-saved-hint">未填写样本文本时仍可使用你的音色，但合成会更慢。</p>
                    ) : null}
                  </label>
                  <div className="upload-guidance">
                    <strong>音色建议</strong>
                    <span>请使用本人或已获授权的声音，避免背景音乐和多人对话；系统会自动截取前 5 秒作为音色样本。</span>
                  </div>
                </div>
              ) : (
                <div className="card-grid default-voice-grid">
                  {voiceQuery.data?.map((voice) => (
                    <button
                      type="button"
                      key={voice.id}
                      className={`select-card ${voiceId === voice.id ? 'active' : ''}`}
                      onClick={() => setVoiceId(voice.id)}
                    >
                      <strong>{voice.name}</strong>
                      <span>{voice.config.description}</span>
                    </button>
                  ))}
                </div>
              )}
            </section>

            <section className="config-section">
              <div className="config-section-head">
                <h2>成片素材</h2>
                <p>选择自拍视频拼接，或使用数字人口播。</p>
              </div>
              <div className="material-mode-grid">
                <button
                  type="button"
                  className={`select-card ${generationVideoMode === 'uploaded_video' ? 'active' : ''}`}
                  onClick={() => {
                    setGenerationVideoMode('uploaded_video')
                  }}
                >
                  <strong>上传自己拍的视频</strong>
                  <span>用前面确认过的文案生成配音和字幕，再与自拍视频拼接成最终视频。</span>
                </button>
                <button
                  type="button"
                  className={`select-card ${generationVideoMode === 'preset_avatar' ? 'active' : ''}`}
                  onClick={() => {
                    setGenerationVideoMode('preset_avatar')
                    setCustomVideoFile(null)
                  }}
                >
                  <strong>使用默认数字人</strong>
                  <span>没有现成自拍视频时，可先用系统内置数字人完成口播视频。</span>
                </button>
              </div>

              {generationVideoMode === 'uploaded_video' ? (
                <div className="custom-media-card">
                  <FileDrop file={customVideoFile} onChange={setCustomVideoFile} />
                  {task.custom_video_path && !customVideoFile ? (
                    <p className="muted config-saved-hint">已保存自拍视频，重新上传可替换。</p>
                  ) : null}
                  <div className="upload-guidance">
                    <strong>拍摄建议</strong>
                    <span>保持人像居中、环境安静、光线稳定，尽量使用和输出比例一致的横屏或竖屏素材。</span>
                  </div>
                </div>
              ) : (
                <div className="card-grid">
                  {avatarQuery.data?.map((avatar) => (
                    <button
                      type="button"
                      key={avatar.id}
                      className={`select-card ${avatarId === avatar.id ? 'active' : ''}`}
                      onClick={() => setAvatarId(avatar.id)}
                    >
                      <strong>{avatar.name}</strong>
                      <span>{avatar.config.description}</span>
                    </button>
                  ))}
                </div>
              )}
            </section>
          </main>

          <aside className="config-preview-panel">
            <div className="config-preview-scroll">
              <header className="config-preview-header">
                <div>
                  <p className="eyebrow">实时预览</p>
                  <h2>成片效果</h2>
                </div>
                <span className={`config-status-pill ${scriptGate.blocked ? 'warn' : 'ok'}`}>
                  {scriptGate.blocked ? '待确认文案' : '可生成'}
                </span>
              </header>

              {scriptGate.blocked ? (
                <div className="config-inline-alert">
                  <strong>文案尚未就绪</strong>
                  <p>{scriptGate.message}</p>
                  <div className="config-inline-alert-actions">
                    {scriptGate.primaryAction ? (
                      <ScriptGateLink
                        taskId={taskId}
                        action={scriptGate.primaryAction}
                        className="ghost-button config-inline-alert-link"
                      />
                    ) : null}
                    {scriptGate.secondaryAction ? (
                      <ScriptGateLink
                        taskId={taskId}
                        action={scriptGate.secondaryAction}
                        className="ghost-button config-inline-alert-link"
                      />
                    ) : null}
                  </div>
                </div>
              ) : null}

              <div className="config-preview-stage">
                <div className={`config-frame ${previewRatioClass}`}>
                  <div className="config-frame-inner">
                    <span className="config-frame-badge">
                      {generationVideoMode === 'uploaded_video' ? '自拍拼接' : '数字人口播'}
                    </span>
                    <div className="config-frame-media">
                      <span className="config-frame-media-icon" aria-hidden>
                        {generationVideoMode === 'uploaded_video' ? '🎬' : '🧑‍💼'}
                      </span>
                      <strong>{previewMaterialLabel}</strong>
                      <small>{task.aspect_ratio ?? '9:16'} · {previewVoiceLabel}</small>
                    </div>
                    {subtitleStyle.enabled ? (
                      <p
                        className={`config-frame-subtitle pos-${subtitleStyle.position}${subtitleStyle.stroke ? ' with-stroke' : ''}`}
                        style={{
                          color: subtitleStyle.color,
                          fontSize: `${Math.max(11, Math.min(16, subtitleStyle.font_size / 2.8))}px`,
                        }}
                      >
                        字幕效果预览
                      </p>
                    ) : (
                      <p className="config-frame-subtitle muted-caption pos-bottom">字幕已关闭</p>
                    )}
                  </div>
                </div>
              </div>

              <div className="config-summary-grid">
                <div className="config-summary-card">
                  <span>文案来源</span>
                  <strong>{task.script_source === 'video_asr' ? '视频提取' : '手动粘贴'}</strong>
                </div>
                <div className="config-summary-card">
                  <span>输出比例</span>
                  <strong>{task.aspect_ratio ?? '9:16'}</strong>
                </div>
                <div className="config-summary-card">
                  <span>成片素材</span>
                  <strong title={previewMaterialLabel}>{previewMaterialLabel}</strong>
                </div>
                <div className="config-summary-card">
                  <span>配音音色</span>
                  <strong title={previewVoiceLabel}>{previewVoiceLabel}</strong>
                </div>
              </div>

              <section className="config-side-block">
                <div className="config-side-block-head">
                  <h3>字幕与语速</h3>
                  <span>右侧预览会同步变化</span>
                </div>
                <div className="config-control-card">
                  <SubtitleStyleControls value={subtitleStyle} onChange={setSubtitleStyle} />
                  <TtsSpeedControl value={voiceSpeed} onChange={setVoiceSpeed} />
                </div>
              </section>

              <section className="config-side-block">
                <div className="config-side-block-head">
                  <h3>导出选项</h3>
                </div>
                <div className="config-toggle-list">
                  <label className="config-toggle-row">
                    <span>
                      <strong>AI 水印</strong>
                      <small>成片角落标注 AI 生成</small>
                    </span>
                    <input
                      type="checkbox"
                      checked={aiWatermarkEnabled}
                      onChange={(e) => setAiWatermarkEnabled(e.target.checked)}
                    />
                  </label>
                  <label className="config-toggle-row">
                    <span>
                      <strong>无字幕版本</strong>
                      <small>额外导出一份无字幕成片</small>
                    </span>
                    <input
                      type="checkbox"
                      checked={exportWithoutSubtitle}
                      onChange={(e) => setExportWithoutSubtitle(e.target.checked)}
                    />
                  </label>
                  <label className="config-field-row">
                    <span>
                      <strong>生成质量</strong>
                      <small>快速模式先出片再精修，完整模式用于正式成片</small>
                    </span>
                    <select
                      value={generationQuality}
                      onChange={(e) => {
                        const next = e.target.value as GenerationQuality
                        setGenerationQuality(next)
                        if (next === 'fast' && avatarEngine === 'tuilionnx') {
                          setAvatarEngine('heygem')
                        }
                        if (next === 'full' && avatarEngine === 'heygem') {
                          setAvatarEngine('tuilionnx')
                        }
                      }}
                    >
                      <option value="fast">快速（预览 / 短文案）</option>
                      <option value="full">完整（克隆音色 + 高画质口型）</option>
                    </select>
                  </label>
                  <label className="config-field-row">
                    <span>
                      <strong>数字人引擎</strong>
                      <small>{generationQuality === 'fast' ? '推荐 HeyGem 追求速度' : '推荐 TuiliONNX 追求口型质量'}</small>
                    </span>
                    <select value={avatarEngine} onChange={(e) => setAvatarEngine(e.target.value as 'heygem' | 'tuilionnx')}>
                      <option value="heygem">HeyGem（需 Docker，速度优先）</option>
                      <option value="tuilionnx">TuiliONNX（本地 ONNX，需先安装）</option>
                    </select>
                  </label>
                  {avatarEngine === 'tuilionnx' ? (
                    <label className="config-field-row">
                      <span>
                        <strong>口型同步微调</strong>
                        <small>高级选项：-10～10 帧，正值延后口型</small>
                      </span>
                      <input
                        type="number"
                        min={-10}
                        max={10}
                        value={tuilionnxSyncOffset}
                        onChange={(e) => setTuilionnxSyncOffset(Number(e.target.value))}
                      />
                    </label>
                  ) : null}
                </div>
              </section>

              <section className="config-side-block">
                <div className="config-side-block-head">
                  <h3>背景音乐</h3>
                  <span>{backgroundMusicMode === 'none' ? '未添加' : backgroundMusicMode === 'random' ? '随机' : '指定曲目'}</span>
                </div>
                <div className="config-control-card">
                  <BackgroundMusicPicker
                    tracks={musicQuery.data ?? []}
                    mode={backgroundMusicMode}
                    selectedPath={backgroundMusicPath}
                    volume={backgroundMusicVolume}
                    onModeChange={setBackgroundMusicMode}
                    onPathChange={setBackgroundMusicPath}
                    onVolumeChange={setBackgroundMusicVolume}
                    onTracksRefresh={() => refetchMusicTracks()}
                  />
                </div>
              </section>

              {needsMaterialAuthorization ? (
                <label className="config-auth-card">
                  <input
                    type="checkbox"
                    checked={authorizationConfirmed}
                    onChange={(event) => setAuthorizationConfirmed(event.target.checked)}
                  />
                  <span>我确认拥有视频、声音、肖像等素材的合法使用授权，可用于 AI 生成与对外发布。</span>
                </label>
              ) : null}
            </div>
          </aside>
        </div>

        <footer className="config-action-bar">
          <div className="config-action-meta">
            {hasTriedSubmit && configIssues.length > 0 ? (
              <ul className="config-issue-list">
                {configIssues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            ) : null}
            {hasTriedSubmit && scriptGate.blocked ? <p className="form-error">{scriptGate.message}</p> : null}
            {error ? <p className="form-error">{error}</p> : null}
            {!hasTriedSubmit && !scriptGate.blocked && isConfigIncomplete ? (
              <p className="muted">完成左侧配置后，即可保存或开始生成。</p>
            ) : null}
            {!scriptGate.blocked && !isConfigIncomplete ? (
              <p className="muted">配置完整，点击「开始生成视频」后将进入生成进度页。</p>
            ) : null}
          </div>
          <div className="config-action-buttons">
            <Link className="ghost-button" to={`/tasks/${taskId}/script`}>
              返回文案
            </Link>
            <button
              className="secondary-button"
              type="button"
              disabled={isBusy || scriptGate.blocked}
              onClick={() => submitConfig('save')}
            >
              {saveConfigMutation.isPending ? '保存中...' : '保存配置'}
            </button>
            <button
              className="primary-button"
              type="button"
              disabled={!canStartGenerate}
              onClick={() => submitConfig('start')}
            >
              {startMutation.isPending ? '启动中...' : '开始生成视频'}
            </button>
          </div>
        </footer>
      </div>
    </section>
  )
}
