import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { FileDrop } from '../components/FileDrop'
import { StatusBadge } from '../components/StatusBadge'
import { StepNav } from '../components/StepNav'
import { getStatusMessage, mockApi } from '../lib/api-client/mockApi'
import type { GenerationVideoMode, GenerationVoiceMode, SubtitleStyle } from '../types/domain'

export function ConfigPage() {
  const { taskId = '' } = useParams()
  const navigate = useNavigate()
  const taskQuery = useQuery({ queryKey: ['task', taskId], queryFn: () => mockApi.getTask(taskId) })
  const voiceQuery = useQuery({ queryKey: ['voiceProfiles'], queryFn: mockApi.getVoiceProfiles })
  const avatarQuery = useQuery({ queryKey: ['avatarProfiles'], queryFn: mockApi.getAvatarProfiles })
  const musicQuery = useQuery({ queryKey: ['musicTracks'], queryFn: mockApi.getMusicTracks })

  const [voiceId, setVoiceId] = useState('voice_default_female')
  const [generationVoiceMode, setGenerationVoiceMode] = useState<GenerationVoiceMode>('uploaded_voice')
  const [customVoiceFile, setCustomVoiceFile] = useState<File | null>(null)
  const [avatarId, setAvatarId] = useState('avatar_studio_a')
  const [generationVideoMode, setGenerationVideoMode] = useState<GenerationVideoMode>('uploaded_video')
  const [customVideoFile, setCustomVideoFile] = useState<File | null>(null)
  const [authorizationConfirmed, setAuthorizationConfirmed] = useState(false)
  const [backgroundMusicPath, setBackgroundMusicPath] = useState('')
  const [backgroundMusicVolume, setBackgroundMusicVolume] = useState(0.18)
  const [hasTriedSubmit, setHasTriedSubmit] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [subtitleStyle, setSubtitleStyle] = useState<SubtitleStyle>({
    enabled: true,
    font_size: 42,
    position: 'bottom',
    color: '#FFFFFF',
    stroke: true,
  })

  const saveConfigMutation = useMutation({
    mutationFn: async () => {
      setError(null)
      return mockApi.saveGenerationConfig(taskId, {
        voice_profile_id: voiceId,
        avatar_profile_id: avatarId,
        generation_voice_mode: generationVoiceMode,
        custom_voice_file: customVoiceFile,
        custom_voice_file_name: customVoiceFile?.name,
        generation_video_mode: generationVideoMode,
        custom_video_file: customVideoFile,
        custom_video_file_name: customVideoFile?.name,
        authorization_confirmed: authorizationConfirmed,
        aspect_ratio: taskQuery.data?.aspect_ratio ?? '9:16',
        subtitle_style: subtitleStyle,
        background_music_path: backgroundMusicPath || null,
        background_music_volume: backgroundMusicVolume,
      })
    },
    onError: (err) => setError(err instanceof Error ? err.message : '保存配置失败'),
  })

  const startMutation = useMutation({
    mutationFn: async () => {
      await saveConfigMutation.mutateAsync()
      return mockApi.startGenerate(taskId)
    },
    onSuccess: (task) => navigate(`/tasks/${task.id}/progress`),
    onError: (err) => setError(err instanceof Error ? err.message : '启动生成失败'),
  })

  if (taskQuery.isLoading || voiceQuery.isLoading || avatarQuery.isLoading || musicQuery.isLoading) {
    return <div className="page">正在加载生成配置...</div>
  }

  if (!taskQuery.data) return <div className="page">任务不存在。</div>

  const selectedVoice = voiceQuery.data?.find((voice) => voice.id === voiceId)
  const selectedAvatar = avatarQuery.data?.find((avatar) => avatar.id === avatarId)
  const needsMaterialAuthorization = generationVoiceMode === 'uploaded_voice' || generationVideoMode === 'uploaded_video'
  const needsCustomVoice = generationVoiceMode === 'uploaded_voice' && !customVoiceFile
  const needsCustomVideo = generationVideoMode === 'uploaded_video' && !customVideoFile
  const needsAuthorizationConfirmation = needsMaterialAuthorization && !authorizationConfirmed
  const isConfigIncomplete = needsCustomVoice || needsCustomVideo || needsAuthorizationConfirmation

  const submitConfig = (action: 'save' | 'start') => {
    setHasTriedSubmit(true)
    setError(null)
    if (isConfigIncomplete) return

    if (action === 'save') {
      saveConfigMutation.mutate()
      return
    }
    startMutation.mutate()
  }

  return (
    <section className="page">
      <StepNav current={3} />
      <div className="page-heading row-heading">
        <div>
          <p className="eyebrow">生成配置</p>
          <h1>选择音色、数字人和字幕样式</h1>
          <p>配置会保存到任务中，后续真实后端会使用这些参数生成音频和画面。</p>
        </div>
        <StatusBadge status={taskQuery.data.status} label={getStatusMessage(taskQuery.data.status)} />
      </div>

      <div className="two-column">
        <main className="panel config-panel">
          <h2>音色选择</h2>
          <div className="material-mode-grid">
            <button
              type="button"
              className={`select-card ${generationVoiceMode === 'uploaded_voice' ? 'active' : ''}`}
              onClick={() => setGenerationVoiceMode('uploaded_voice')}
            >
              <strong>上传自己的音色</strong>
              <span>上传本人或已获授权的声音样本，用前面确认过的文案生成专属配音。</span>
            </button>
            <button
              type="button"
              className={`select-card ${generationVoiceMode === 'preset_voice' ? 'active' : ''}`}
              onClick={() => setGenerationVoiceMode('preset_voice')}
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
                accept="audio/wav,audio/mpeg,audio/mp4,audio/x-m4a"
                title="拖拽音频到这里，或点击选择文件"
                description="支持 WAV / MP3 / M4A，建议 10-60 秒清晰人声"
              />
              <div className="upload-guidance">
                <strong>音色建议</strong>
                <span>请使用本人或已获授权的声音，避免背景音乐和多人对话，方便后续生成稳定配音。</span>
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

          <h2>成片素材</h2>
          <div className="material-mode-grid">
            <button
              type="button"
              className={`select-card ${generationVideoMode === 'uploaded_video' ? 'active' : ''}`}
              onClick={() => setGenerationVideoMode('uploaded_video')}
            >
              <strong>上传自己拍的视频</strong>
              <span>用前面确认过的文案生成配音和字幕，再与自拍视频拼接成最终视频。</span>
            </button>
            <button
              type="button"
              className={`select-card ${generationVideoMode === 'preset_avatar' ? 'active' : ''}`}
              onClick={() => setGenerationVideoMode('preset_avatar')}
            >
              <strong>使用默认数字人</strong>
              <span>没有现成自拍视频时，可先用系统内置数字人完成口播视频。</span>
            </button>
          </div>

          {generationVideoMode === 'uploaded_video' ? (
            <div className="custom-media-card">
              <FileDrop file={customVideoFile} onChange={setCustomVideoFile} />
              <div className="upload-guidance">
                <strong>拍摄建议</strong>
                <span>保持人像居中、环境安静、光线稳定，尽量使用和输出比例一致的横屏或竖屏素材。</span>
              </div>
            </div>
          ) : (
            <>
              <h2>数字人选择</h2>
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
            </>
          )}
        </main>

        <aside className="panel">
          <h2>实时预览</h2>
          <div className="compliance-note">
            <strong>内容风险已处理</strong>
            <span>配置生成前已完成文案风险检查或人工确认。</span>
          </div>
          <div className="avatar-preview">
            <span>{generationVideoMode === 'uploaded_video' ? '自拍视频预览画面' : '数字人预览画面'}</span>
            <em>{generationVideoMode === 'uploaded_video' ? customVideoFile?.name || '待上传素材' : selectedAvatar?.name}</em>
            {subtitleStyle.enabled ? (
              <strong style={{ color: subtitleStyle.color, fontSize: Math.max(18, subtitleStyle.font_size / 2) }}>
                字幕效果预览
              </strong>
            ) : null}
          </div>
          <div className="config-summary">
            <div>
              <span>文案来源</span>
              <strong>{taskQuery.data.script_source === 'video_asr' ? '视频提取文案' : '手动粘贴文案'}</strong>
            </div>
            <div>
              <span>成片素材</span>
              <strong>{generationVideoMode === 'uploaded_video' ? customVideoFile?.name || '待上传自拍视频' : selectedAvatar?.name}</strong>
            </div>
            <div>
              <span>配音音色</span>
              <strong>{generationVoiceMode === 'uploaded_voice' ? customVoiceFile?.name || '待上传音色样本' : selectedVoice?.name}</strong>
            </div>
          </div>
          <h2>字幕样式</h2>
          <label className="check-row">
            <input
              type="checkbox"
              checked={subtitleStyle.enabled}
              onChange={(event) => setSubtitleStyle({ ...subtitleStyle, enabled: event.target.checked })}
            />
            启用字幕
          </label>
          <label className="field-row">
            字号
            <input
              type="number"
              value={subtitleStyle.font_size}
              min={24}
              max={72}
              onChange={(event) => setSubtitleStyle({ ...subtitleStyle, font_size: Number(event.target.value) })}
            />
          </label>
          <label className="field-row">
            颜色
            <input
              type="color"
              value={subtitleStyle.color}
              onChange={(event) => setSubtitleStyle({ ...subtitleStyle, color: event.target.value })}
            />
          </label>
          <h2>背景音乐</h2>
          <label className="field-stack">
            CC0 音乐素材
            <select value={backgroundMusicPath} onChange={(event) => setBackgroundMusicPath(event.target.value)}>
              <option value="">不添加背景音乐</option>
              {musicQuery.data?.map((track) => (
                <option key={track.path} value={track.path}>
                  {track.name}
                </option>
              ))}
            </select>
            <span className="muted">请把 CC0-1.0 Music 文件放到后端配置的音乐目录，系统会自动扫描。</span>
          </label>
          {backgroundMusicPath ? (
            <label className="field-row">
              音乐音量
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={backgroundMusicVolume}
                onChange={(event) => setBackgroundMusicVolume(Number(event.target.value))}
              />
            </label>
          ) : null}
          {needsMaterialAuthorization ? (
            <label className="check-row material-auth-check">
              <input
                type="checkbox"
                checked={authorizationConfirmed}
                onChange={(event) => setAuthorizationConfirmed(event.target.checked)}
              />
              我确认拥有视频、字幕、声音、肖像和图片素材的合法使用授权，且内容可用于 AI 生成和对外发布。
            </label>
          ) : null}
          {hasTriedSubmit && needsCustomVoice ? (
            <p className="form-error">请上传自己的音色样本后再保存或开始生成。</p>
          ) : null}
          {hasTriedSubmit && needsCustomVideo ? (
            <p className="form-error">请上传自拍视频后再保存或开始生成。</p>
          ) : null}
          {hasTriedSubmit && needsAuthorizationConfirmation ? <p className="form-error">请先确认上传素材授权。</p> : null}
          {error ? <p className="form-error">{error}</p> : null}
        </aside>
      </div>

      <footer className="action-bar">
        <Link className="ghost-button" to={`/tasks/${taskId}/script`}>
          返回文案
        </Link>
        <Link className="ghost-button" to={`/tasks/${taskId}/risk-review`}>
          查看风险检查
        </Link>
        <button
          className="secondary-button"
          type="button"
          disabled={saveConfigMutation.isPending}
          onClick={() => submitConfig('save')}
        >
          {saveConfigMutation.isPending ? '保存中...' : '保存配置'}
        </button>
        <button
          className="primary-button"
          type="button"
          disabled={startMutation.isPending}
          onClick={() => submitConfig('start')}
        >
          {startMutation.isPending ? '启动中...' : '开始生成视频'}
        </button>
      </footer>
    </section>
  )
}
