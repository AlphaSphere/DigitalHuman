/** 字幕样式控件 */
import type { SubtitleStyle } from '../types/domain'

/** 可选字体列表（系统内置中文字体 + 英文通用字体） */
const FONT_FAMILIES = [
  { value: 'SimHei', label: '黑体 (SimHei)' },
  { value: 'Microsoft YaHei', label: '微软雅黑' },
  { value: 'SimSun', label: '宋体 (SimSun)' },
  { value: 'KaiTi', label: '楷体 (KaiTi)' },
  { value: 'FangSong', label: '仿宋 (FangSong)' },
  { value: 'Arial', label: 'Arial' },
  { value: 'Impact', label: 'Impact' },
]

interface Props {
  value: SubtitleStyle
  onChange: (value: SubtitleStyle) => void
}

export function SubtitleStyleControls({ value, onChange }: Props) {
  return (
    <div className="subtitle-style-controls">
      <label className="subtitle-toggle-row">
        <span>启用字幕</span>
        <input
          type="checkbox"
          checked={value.enabled}
          onChange={(e) => onChange({ ...value, enabled: e.target.checked })}
        />
      </label>

      <div className="subtitle-style-grid">
        <label className="subtitle-field">
          <span>字号</span>
          <input
            type="number"
            min={12}
            max={72}
            value={value.font_size}
            onChange={(e) => onChange({ ...value, font_size: Number(e.target.value) })}
          />
        </label>
        <label className="subtitle-field">
          <span>颜色</span>
          <input type="color" value={value.color} onChange={(e) => onChange({ ...value, color: e.target.value })} />
        </label>
      </div>

      <label className="subtitle-field subtitle-font-row">
        <span>字体</span>
        <select
          value={value.font_family ?? 'SimHei'}
          onChange={(e) => onChange({ ...value, font_family: e.target.value })}
        >
          {FONT_FAMILIES.map(({ value: v, label }) => (
            <option key={v} value={v}>{label}</option>
          ))}
        </select>
      </label>

      <div className="subtitle-position-row">
        <span>位置</span>
        <div className="subtitle-position-tabs">
          {(
            [
              ['bottom', '底部'],
              ['middle', '中部'],
              ['top', '顶部'],
            ] as const
          ).map(([pos, label]) => (
            <button
              key={pos}
              type="button"
              className={value.position === pos ? 'active' : ''}
              onClick={() => onChange({ ...value, position: pos })}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <label className="subtitle-toggle-row">
        <span>描边</span>
        <input type="checkbox" checked={value.stroke} onChange={(e) => onChange({ ...value, stroke: e.target.checked })} />
      </label>
    </div>
  )
}
