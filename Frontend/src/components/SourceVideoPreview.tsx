/**
 * 参考视频预览：优先播放本地转存文件，识别中显示状态提示。
 */
import { useState } from 'react'
import { mockApi } from '../lib/api-client/mockApi'
import { isTranscribeFailure } from '../lib/scriptGate'
import type { Task } from '../types/domain'

interface SourceVideoPreviewProps {
  task: Task
  hasScriptText?: boolean
}

export function SourceVideoPreview({ task, hasScriptText = true }: SourceVideoPreviewProps) {
  const [playbackError, setPlaybackError] = useState(false)
  const isTranscribing = ['uploaded', 'transcribing', 'audio_extracted'].includes(task.status)
  const previewUrl = mockApi.getSourceVideoPreviewUrl(task.id)
  const canPreview = task.script_source === 'video_asr' && !isTranscribing && !playbackError
  const showTranscribeFailure = isTranscribeFailure(task.status, task.error_code, hasScriptText)

  if (task.script_source !== 'video_asr') {
    return <div className="video-placeholder">粘贴文案来源</div>
  }

  if (isTranscribing) {
    return (
      <div className="video-placeholder video-placeholder-loading">
        <strong>视频处理中</strong>
        <span className="muted">识别进度见页面上方，完成后可预览</span>
      </div>
    )
  }

  if (showTranscribeFailure) {
    return (
      <div className="video-placeholder video-placeholder-error">
        <strong>识别失败</strong>
        <span>{task.error_message ?? '请返回重新创建任务'}</span>
      </div>
    )
  }

  return (
    <div className="video-preview-wrap">
      {canPreview ? (
        <video
          className="source-video-player"
          controls
          preload="metadata"
          src={previewUrl}
          onError={() => setPlaybackError(true)}
        />
      ) : (
        <div className="video-placeholder">
          <strong>参考视频</strong>
          <span>{playbackError ? '预览加载失败，可稍后重试' : '视频预览暂不可用'}</span>
        </div>
      )}
    </div>
  )
}
