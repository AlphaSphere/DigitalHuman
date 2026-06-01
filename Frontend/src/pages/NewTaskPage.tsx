import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { FileDrop } from '../components/FileDrop'
import { StepNav } from '../components/StepNav'
import { mockApi } from '../lib/api-client/mockApi'
import type { AspectRatio } from '../types/domain'

const taskSchema = z.object({
  sourceMode: z.enum(['video', 'script']),
  videoInputMode: z.enum(['upload', 'url']),
  videoUrl: z.string(),
  content: z.string(),
  aspectRatio: z.enum(['9:16', '16:9', '1:1']),
})

type TaskFormValues = z.infer<typeof taskSchema>

const aspectRatioOptions: Array<{ value: AspectRatio; label: string; description: string }> = [
  { value: '9:16', label: '9:16', description: '竖屏' },
  { value: '16:9', label: '16:9', description: '横屏' },
  { value: '1:1', label: '1:1', description: '方屏' },
]

const isValidHttpUrl = (value: string) => {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

export function NewTaskPage() {
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)

  const form = useForm<TaskFormValues>({
    resolver: zodResolver(taskSchema),
    defaultValues: {
      sourceMode: 'video',
      videoInputMode: 'url',
      videoUrl: '',
      content: '',
      aspectRatio: '9:16',
    },
  })
  const sourceMode = useWatch({ control: form.control, name: 'sourceMode' })
  const videoInputMode = useWatch({ control: form.control, name: 'videoInputMode' })

  const mutation = useMutation({
    mutationFn: async (values: TaskFormValues) => {
      if (values.sourceMode === 'video') {
        if (values.videoInputMode === 'upload' && !file) throw new Error('请先选择参考视频')
        if (values.videoInputMode === 'url' && !isValidHttpUrl(values.videoUrl)) {
          throw new Error('请输入有效的视频链接，需以 http:// 或 https:// 开头')
        }

        return mockApi.createVideoTask({
          file: values.videoInputMode === 'upload' ? file : null,
          fileName: values.videoInputMode === 'upload' ? file?.name : undefined,
          source_url: values.videoInputMode === 'url' ? values.videoUrl.trim() : undefined,
          aspect_ratio: values.aspectRatio as AspectRatio,
        })
      }

      return mockApi.createScriptTask({
        content: values.content,
        content_type: 'pasted_script',
        aspect_ratio: values.aspectRatio as AspectRatio,
      })
    },
    onSuccess: (task) => navigate(`/tasks/${task.id}/script`),
    onError: (err) => setError(err instanceof Error ? err.message : '创建任务失败'),
  })

  const resetForm = () => {
    setFile(null)
    setError(null)
    form.reset()
  }

  const setVideoInputMode = (mode: TaskFormValues['videoInputMode']) => {
    form.setValue('videoInputMode', mode)
    if (mode === 'upload') {
      form.setValue('videoUrl', '')
      return
    }
    setFile(null)
  }

  return (
    <section className="page">
      <StepNav current={0} />
      <div className="page-heading">
        <p className="eyebrow">MVP 任务创建</p>
        <h1>创建数字人口播视频</h1>
        <p>上传参考视频自动识别文案，或直接粘贴已有字幕 / 口播稿。</p>
      </div>

      <form className="three-column" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <aside className="panel">
          <h2>输入方式</h2>
          <label className="radio-card">
            <input type="radio" value="video" {...form.register('sourceMode')} />
            上传参考视频
          </label>
          <label className="radio-card">
            <input type="radio" value="script" {...form.register('sourceMode')} />
            粘贴字幕 / 文案
          </label>

          <h2>输出比例</h2>
          <div className="segmented">
            {aspectRatioOptions.map((option) => (
              <label key={option.value} className="aspect-ratio-option">
                <input type="radio" value={option.value} {...form.register('aspectRatio')} />
                <span className="ratio-preview-shell">
                  <span className={`ratio-preview ratio-preview-${option.value.replace(':', '-')}`} />
                </span>
                <span className="ratio-copy">
                  <strong>{option.label}</strong>
                  <small>{option.description}</small>
                </span>
              </label>
            ))}
          </div>
        </aside>

        <main className="panel hero-panel">
          {sourceMode === 'video' ? (
            <div className="video-source-panel">
              <div className="video-source-choice">
                <label className="video-source-option">
                  <input
                    type="radio"
                    value="url"
                    checked={videoInputMode === 'url'}
                    onChange={() => setVideoInputMode('url')}
                  />
                  填写链接
                </label>
                <label className="video-source-option">
                  <input
                    type="radio"
                    value="upload"
                    checked={videoInputMode === 'upload'}
                    onChange={() => setVideoInputMode('upload')}
                  />
                  上传视频
                </label>
              </div>
              {videoInputMode === 'upload' ? (
                <FileDrop file={file} onChange={setFile} />
              ) : (
                <label className="field-stack">
                  参考视频链接
                  <input
                    className="url-input"
                    placeholder="https://example.com/reference-video.mp4"
                    {...form.register('videoUrl')}
                  />
                  <span className="muted">支持公开可访问的视频链接，后续后端会下载或转存到任务存储目录。</span>
                </label>
              )}
            </div>
          ) : (
            <textarea
              className="script-input"
              rows={14}
              placeholder="粘贴 SRT、带序号字幕、逐字稿或口播文案..."
              {...form.register('content')}
            />
          )}
          {error ? <p className="form-error hero-panel-error">{error}</p> : null}
        </main>

        <aside className="panel">
          <h2>创建说明</h2>
          <ul className="hint-list">
            <li>视频格式：MP4 / MOV</li>
            <li>参考视频可上传文件或填写公开链接，二选一</li>
            <li>MVP 建议 3 分钟以内</li>
            <li>文案会进入确认页，不会直接生成</li>
            <li>确认文案后会进行内容风险检查</li>
            <li>素材授权会在上传音色或自拍视频时确认</li>
          </ul>
        </aside>

        <footer className="action-bar">
          <button type="button" className="ghost-button" onClick={resetForm}>
            重置
          </button>
          <button type="submit" className="primary-button" disabled={mutation.isPending}>
            {mutation.isPending ? '创建中...' : '创建任务'}
          </button>
        </footer>
      </form>
    </section>
  )
}
