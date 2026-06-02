/**
 * 用途：定义数字人口播工作台的前端路由表与页面映射。
 */
import { Navigate, createBrowserRouter } from 'react-router-dom'
import { AppLayout } from '../components/AppLayout'
import { ConfigPage } from '../pages/ConfigPage'
import { NewTaskPage } from '../pages/NewTaskPage'
import { PrePublishPage } from '../pages/PrePublishPage'
import { ProgressPage } from '../pages/ProgressPage'
import { ResultPage } from '../pages/ResultPage'
import { RiskReviewPage } from '../pages/RiskReviewPage'
import { ScriptPage } from '../pages/ScriptPage'

/**
 * 浏览器路由实例，覆盖任务创建到发布前检查的完整流程。
 *
 * 逻辑：
 * - 根路径重定向至 /tasks/new；
 * - 所有业务页嵌套在 AppLayout 下以共享顶栏；
 * - taskId 动态段贯穿文案、风险、配置、进度、结果与发布页。
 */
export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/tasks/new" replace /> },
      { path: 'tasks/new', element: <NewTaskPage /> },
      { path: 'tasks/:taskId/script', element: <ScriptPage /> },
      { path: 'tasks/:taskId/risk-review', element: <RiskReviewPage /> },
      { path: 'tasks/:taskId/config', element: <ConfigPage /> },
      { path: 'tasks/:taskId/progress', element: <ProgressPage /> },
      { path: 'tasks/:taskId/result', element: <ResultPage /> },
      { path: 'tasks/:taskId/pre-publish', element: <PrePublishPage /> },
    ],
  },
])
