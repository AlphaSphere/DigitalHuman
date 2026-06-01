import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { StatusBadge } from '../components/StatusBadge'
import { StepNav } from '../components/StepNav'
import { getStatusMessage, mockApi } from '../lib/api-client/mockApi'
import type { SubtitleStyle } from '../types/domain'

export function ConfigPage() {
  const { taskId = '' } = useParams()
  const navigate = useNavigate()
  const taskQuery = useQuery({ queryKey: ['task', taskId], queryFn: () => mockApi.getTask(taskId) })
  const voiceQuery = useQuery({ queryKey: ['voiceProfiles'], queryFn: mockApi.getVoiceProfiles })
  const avatarQuery = useQuery({ queryKey: ['avatarProfiles'], queryFn: mockApi.getAvatarProfiles })

  const [voiceId, setVoiceId] = useState('voice_default_female')
  const [avatarId, setAvatarId] = useState('avatar_studio_a')
  const [subtitleStyle, setSubtitleStyle] = useState<SubtitleStyle>({
    enabled: true,
    font_size: 42,
    position: 'bottom',
    color: '#FFFFFF',
    stroke: true,
  })

  const saveConfigMutation = useMutation({
    mutationFn: () =>
      mockApi.saveGenerationConfig(taskId, {
        voice_profile_id: voiceId,
        avatar_profile_id: avatarId,
        aspect_ratio: taskQuery.data?.aspect_ratio ?? '9:16',
        subtitle_style: subtitleStyle,
      }),
  })

  const startMutation = useMutation({
    mutationFn: async () => {
      await saveConfigMutation.mutateAsync()
      return mockApi.startGenerate(taskId)
    },
    onSuccess: (task) => navigate(`/tasks/${task.id}/progress`),
  })

  if (taskQuery.isLoading || voiceQuery.isLoading || avatarQuery.isLoading) {
    return <div className="page">正在加载生成配置...</div>
  }

  if (!taskQuery.data) return <div className="page">任务不存在。</div>

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
          <div className="card-grid">
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
        </main>

        <aside className="panel">
          <h2>实时预览</h2>
          <div className="compliance-note">
            <strong>内容风险已处理</strong>
            <span>配置生成前已完成文案风险检查或人工确认。</span>
          </div>
          <div className="avatar-preview">
            <span>数字人预览画面</span>
            {subtitleStyle.enabled ? (
              <strong style={{ color: subtitleStyle.color, fontSize: Math.max(18, subtitleStyle.font_size / 2) }}>
                字幕效果预览
              </strong>
            ) : null}
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
        </aside>
      </div>

      <footer className="action-bar">
        <Link className="ghost-button" to={`/tasks/${taskId}/script`}>
          返回文案
        </Link>
        <Link className="ghost-button" to={`/tasks/${taskId}/risk-review`}>
          查看风险检查
        </Link>
        <button className="secondary-button" type="button" onClick={() => saveConfigMutation.mutate()}>
          {saveConfigMutation.isPending ? '保存中...' : '保存配置'}
        </button>
        <button className="primary-button" type="button" onClick={() => startMutation.mutate()}>
          {startMutation.isPending ? '启动中...' : '开始生成视频'}
        </button>
      </footer>
    </section>
  )
}
