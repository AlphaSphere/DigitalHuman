interface FileDropProps {
  file: File | null
  onChange: (file: File | null) => void
}

export function FileDrop({ file, onChange }: FileDropProps) {
  return (
    <label className="file-drop">
      <input
        type="file"
        accept="video/mp4,video/quicktime"
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
      <span className="file-drop-title">{file ? file.name : '拖拽视频到这里，或点击选择文件'}</span>
      <span className="file-drop-desc">
        {file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : '支持 MP4 / MOV，MVP 建议 3 分钟以内'}
      </span>
    </label>
  )
}
