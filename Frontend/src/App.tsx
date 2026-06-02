/**
 * 用途：应用根组件，注入 React Query 与 React Router 全局上下文。
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { router } from './routes/AppRoutes'

const queryClient = new QueryClient()

/**
 * 应用根组件，组合数据请求与路由能力。
 *
 * @returns 包裹 RouterProvider 的 QueryClientProvider 树
 *
 * 逻辑：
 * - 创建单例 QueryClient 供全站 useQuery/useMutation 复用；
 * - 通过 RouterProvider 渲染 AppRoutes 定义的路由表。
 */
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}

export default App
