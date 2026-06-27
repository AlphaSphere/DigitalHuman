/** 背景音乐选择（含随机 + 用户上传） */
import { useRef, useState } from 'react'
import type { BackgroundMusicMode, MusicTrack } from '../types/domain'
import { mockApi as api } from '../lib/api-client/mockApi'

interface Props {
  tracks: MusicTrack[]
  mode: BackgroundMusicMode
  selectedPath: string
  volume: number
  onModeChange: (mode: BackgroundMusicMode) => void
  onPathChange: (path: string) => void
  onVolumeChange: (volume: number) => void
  /** 上传成功后通知父组件刷新曲目列表 */
  onTracksRefresh?: () => void
}

export function BackgroundMusicPicker({
  tracks,
  mode,
  selectedPath,
  volume,
  onModeChange,
  onPathChange,
  onVolumeChange,
  onTracksRefresh,
}: Props) {
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setUploadError(null)
    try {
      const track = await api.uploadMusicTrack(file)
      onTracksRefresh?.()
      // 上传成功后自动切换到「指定曲目」模式并选中新上传的曲目
      onModeChange('fixed')
      onPathChange(track.path)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : '上传失败')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div className="bgm-picker">
      <label className="bgm-field">
        <span>模式</span>
        <select value={mode} onChange={(e) => onModeChange(e.target.value as BackgroundMusicMode)}>
          <option value="none">不添加</option>
          <option value="fixed">指定曲目</option>
          <option value="random">随机选择</option>
        </select>
      </label>
      {mode === 'fixed' ? (
        <div className="bgm-fixed-row">
          <label className="bgm-field bgm-field-grow">
            <span>曲目</span>
            <select value={selectedPath} onChange={(e) => onPathChange(e.target.value)}>
              <option value="">请选择</option>
              {tracks.map((track) => (
                <option key={track.id} value={track.path}>
                  {track.name}
                </option>
              ))}
            </select>
          </label>
          <div className="bgm-upload-btn-wrap">
            <input
              ref={fileInputRef}
              type="file"
              accept=".mp3,.wav,.m4a,.aac,.flac,.ogg"
              style={{ display: 'none' }}
              onChange={handleFileUpload}
            />
            <button
              type="button"
              className="bgm-upload-btn"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
              title="上传本地 BGM 文件（mp3/wav/m4a）"
            >
              {uploading ? '上传中…' : '+ 上传'}
            </button>
          </div>
        </div>
      ) : null}
      {uploadError ? <p className="bgm-upload-error">{uploadError}</p> : null}
      <div className="bgm-volume">
        <div className="bgm-volume-head">
          <span>音量</span>
          <strong>{Math.round(volume * 100)}%</strong>
        </div>
        <input type="range" min={0} max={1} step={0.01} value={volume} onChange={(e) => onVolumeChange(Number(e.target.value))} />
      </div>
    </div>
  )
}
