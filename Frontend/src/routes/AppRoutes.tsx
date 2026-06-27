/**

 * 用途：定义数字人口播工作台的前端路由表与页面映射。

 */

import { Navigate, createBrowserRouter } from 'react-router-dom'

import { AppLayout } from '../components/AppLayout'

import { ConfigPage } from '../pages/ConfigPage'

import { NewTaskPage } from '../pages/NewTaskPage'

import { PipelineProgressPage } from '../pages/PipelineProgressPage'

import { PrePublishPage } from '../pages/PrePublishPage'

import { ProgressPage } from '../pages/ProgressPage'

import { QuickPipelinePage } from '../pages/QuickPipelinePage'

import { ResultPage } from '../pages/ResultPage'

import { RiskReviewPage } from '../pages/RiskReviewPage'

import { ScriptPage } from '../pages/ScriptPage'

import { TaskFlowRedirect } from '../pages/TaskFlowRedirect'

import { TaskListPage } from '../pages/TaskListPage'



export const router = createBrowserRouter([

  {

    path: '/',

    element: <AppLayout />,

    children: [

      { index: true, element: <Navigate to="/tasks/new" replace /> },

      { path: 'quick', element: <QuickPipelinePage /> },

      { path: 'tasks', element: <TaskListPage /> },

      { path: 'tasks/new', element: <NewTaskPage /> },

      { path: 'tasks/:taskId/script', element: <ScriptPage /> },

      { path: 'tasks/:taskId/risk-review', element: <RiskReviewPage /> },

      { path: 'tasks/:taskId/config', element: <ConfigPage /> },

      { path: 'tasks/:taskId/progress', element: <ProgressPage /> },

      { path: 'tasks/:taskId/pipeline', element: <TaskFlowRedirect /> },

      { path: 'tasks/:taskId/pipeline-progress', element: <PipelineProgressPage /> },

      { path: 'tasks/:taskId/result', element: <ResultPage /> },

      { path: 'tasks/:taskId/pre-publish', element: <PrePublishPage /> },

    ],

  },

])


