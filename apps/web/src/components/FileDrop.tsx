interface FileDropProps {
  file: File | null
  onChange: (file: File | null) => void
  accept?: string
  title?: string
  description?: string
}

export function FileDrop({
  file,
  onChange,
  accept = 'video/mp4,video/quicktime',
  title = '拖拽视频到这里，或点击选择文件',
  description = '支持 MP4 / MOV，MVP 建议 3 分钟以内',
}: FileDropProps) {
  return (
    <label className="file-drop">
      <input
        type="file"
        accept={accept}
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
      <span className="file-drop-title">{file ? file.name : title}</span>
      <span className="file-drop-desc">
        {file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : description}
      </span>
    </label>
  )
}
