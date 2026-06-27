/**
 * 用途：展示数字人视频生成流程的步骤导航条。
 */

/** 固定五步流程文案，与页面 StepNav current 索引对应。 */
const steps = ['创建任务', '文案与合规', '配置生成', '生成中', '查看结果']

interface StepNavProps {
  /** 当前所处步骤的零基索引 */
  current: number
}

/**
 * 横向步骤导航，标记已完成、进行中与待处理步骤。
 *
 * @param props.current - 当前步骤索引（0-4）
 * @returns 有序列表形式的步骤导航
 *
 * 逻辑：
 * - index < current → done；
 * - index === current → current；
 * - 其余 → pending。
 */
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
