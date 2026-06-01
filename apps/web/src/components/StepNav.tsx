const steps = ['创建任务', '确认文案', '风险检查', '配置生成', '生成中', '查看结果']

interface StepNavProps {
  current: number
}

export function StepNav({ current }: StepNavProps) {
  return (
    <ol className="step-nav" aria-label="生成步骤">
      {steps.map((step, index) => {
        const state = index < current ? 'done' : index === current ? 'current' : 'pending'
        return (
          <li key={step} className={`step-item ${state}`}>
            <span>{index + 1}</span>
            {step}
          </li>
        )
      })}
    </ol>
  )
}
