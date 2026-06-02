/**
 * 用途：可复用的文件拖拽/点击上传区域组件。
 */

interface FileDropProps {
  /** 当前已选文件，未选时为 null */
  file: File | null
  /** 文件变更回调 */
  onChange: (file: File | null) => void
  /** input accept 属性，限制可选 MIME 类型 */
  accept?: string
  /** 未选文件时的主标题文案 */
  title?: string
  /** 未选文件时的副标题/说明文案 */
  description?: string
}

/**
 * 文件选择拖拽区，选中后展示文件名与大小。
 *
 * @param props - 文件状态、回调与展示文案
 * @returns label 包裹的隐藏 file input 与提示文本
 *
 * 逻辑：
 * - 使用 label 扩大点击热区；
 * - onChange 从 event.target.files 取首个文件或 null；
 * - 已选文件时展示 MB 大小（保留一位小数）。
 */
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
