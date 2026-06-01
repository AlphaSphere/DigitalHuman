import { Navigate, createBrowserRouter } from 'react-router-dom'
import { AppLayout } from '../components/AppLayout'
import { ConfigPage } from '../pages/ConfigPage'
import { NewTaskPage } from '../pages/NewTaskPage'
import { PrePublishPage } from '../pages/PrePublishPage'
import { ProgressPage } from '../pages/ProgressPage'
import { ResultPage } from '../pages/ResultPage'
import { RiskReviewPage } from '../pages/RiskReviewPage'
import { ScriptPage } from '../pages/ScriptPage'

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
