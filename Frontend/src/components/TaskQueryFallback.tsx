/**
 * 用途：任务 Query 加载/错误/空数据统一占位 UI。
 */
import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'

interface TaskQueryFallbackProps<T> {
  query: Pick<UseQueryResult<T>, 'isLoading' | 'isError' | 'error' | 'refetch' | 'data'>
  loadingMessage?: string
  notFoundMessage?: string
}

/** 返回占位 UI；数据就绪时返回 null，供页面 early return 使用。 */
export function resolveTaskQueryFallback<T>({
  query,
  loadingMessage = '正在加载...',
  notFoundMessage = '任务不存在。',
}: TaskQueryFallbackProps<T>): ReactNode {
  if (query.isLoading) {
    return <div className="page">{loadingMessage}</div>
  }

  if (query.isError) {
    const message = query.error instanceof Error ? query.error.message : '网络或服务异常'
    return (
      <div className="page panel form-error">
        <strong>加载失败</strong>
        <p>{message}</p>
        <button type="button" className="secondary-button" onClick={() => query.refetch()}>
          重试
        </button>
      </div>
    )
  }

  if (query.data === undefined || query.data === null) {
    return <div className="page">{notFoundMessage}</div>
  }

  return null
}

export function TaskQueryFallback<T>(props: TaskQueryFallbackProps<T>) {
  return resolveTaskQueryFallback(props)
}
