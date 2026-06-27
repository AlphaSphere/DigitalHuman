/**
 * 一键追爆款入口：提交对标链接并进入流水线进度页。
 */
import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileDrop } from '../components/FileDrop'
import { mockApi } from '../lib/api-client/mockApi'
import type { AspectRatio, GenerationQuality, GenerationVoiceMode } from '../types/domain'

export function QuickPipelinePage() {
  const navigate = useNavigate()
  const [sourceUrl, setSourceUrl] = useState('')
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>('9:16')
  const [generationQuality, setGenerationQuality] = useState<GenerationQuality>('fast')
  const [generationVoiceMode, setGenerationVoiceMode] = useState<GenerationVoiceMode>('uploaded_voice')
  const [customVoiceFile, setCustomVoiceFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)

  const startMutation = useMutation({
    mutationFn: () =>
      mockApi.startOneClickPipeline({
        payload: {
          source_url: sourceUrl.trim(),
          aspect_ratio: aspectRatio,
          rewrite_enabled: true,
          auto_generate_cover: true,
          auto_generate_metadata: true,
          generation_quality: generationQuality,
          generation_voice_mode: generationVoiceMode,
          require_config_before_generate: generationVoiceMode === 'uploaded_voice' && !customVoiceFile,
          avatar_engine: generationQuality === 'fast' ? 'heygem' : 'tuilionnx',
        },
        custom_voice_file: customVoiceFile,
      }),
    onSuccess: (task) => navigate(`/tasks/${task.id}/pipeline-progress`),
    onError: (err) => setError(err instanceof Error ? err.message : '启动失败'),
  })

  return (
    <section className="page">
      <div className="page-heading">
        <p className="eyebrow">一键追爆款</p>
        <h1>输入对标链接，自动走完识别 → 仿写 → 生成</h1>
        <p>适合批量对标场景；如需逐步确认文案与合规，请使用「分步创作」。</p>
      </div>
      <div className="panel hero-panel">
        <label className="field-stack">
          对标视频链接
          <input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="粘贴抖音/快手/B站等公开链接" />
        </label>
        <label className="field-row">
          输出比例
          <select value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value as AspectRatio)}>
            <option value="9:16">9:16 竖屏</option>
            <option value="16:9">16:9 横屏</option>
            <option value="1:1">1:1 方形</option>
          </select>
        </label>
        <label className="field-row">
          生成质量
          <select value={generationQuality} onChange={(e) => setGenerationQuality(e.target.value as GenerationQuality)}>
            <option value="fast">快速（先出片）</option>
            <option value="full">完整（正式成片）</option>
          </select>
        </label>
        <div className="material-mode-grid">
          <button
            type="button"
            className={`select-card ${generationVoiceMode === 'uploaded_voice' ? 'active' : ''}`}
            onClick={() => setGenerationVoiceMode('uploaded_voice')}
          >
            <strong>使用自己的音色</strong>
            <span>上传样本后克隆配音；未上传时会在配置页暂停补全。</span>
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
            <span>跳过上传，适合快速试跑。</span>
          </button>
        </div>
        {generationVoiceMode === 'uploaded_voice' ? (
          <div className="field-stack">
            <span>音色样本（可选，建议上传）</span>
            <FileDrop file={customVoiceFile} onChange={setCustomVoiceFile} />
          </div>
        ) : null}
        {error ? <p className="form-error">{error}</p> : null}
        <button
          className="primary-button"
          type="button"
          disabled={!sourceUrl.trim() || startMutation.isPending}
          onClick={() => startMutation.mutate()}
        >
          {startMutation.isPending ? '启动中...' : '开始一键生成'}
        </button>
      </div>
    </section>
  )
}
