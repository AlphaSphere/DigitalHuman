/** TTS 语速调节 */
interface Props {
  value: number
  onChange: (value: number) => void
}

export function TtsSpeedControl({ value, onChange }: Props) {
  return (
    <div className="tts-speed-control">
      <div className="tts-speed-head">
        <span>语速</span>
        <strong>{value.toFixed(1)}x</strong>
      </div>
      <input type="range" min={0.5} max={2} step={0.1} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <div className="tts-speed-marks">
        <span>0.5x</span>
        <span>1.0x</span>
        <span>2.0x</span>
      </div>
    </div>
  )
}
