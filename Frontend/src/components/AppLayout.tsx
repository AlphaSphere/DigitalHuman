/**
 * 用途：全站布局壳，提供顶栏导航与子路由出口。
 */
import { NavLink, Outlet } from 'react-router-dom'

/**
 * 应用主布局：顶栏品牌区 + 主导航 + 页面内容区。
 *
 * @returns 包含 header 与 main/Outlet 的布局结构
 *
 * 逻辑：
 * - NavLink 高亮当前路由；
 * - Outlet 渲染嵌套子路由页面。
 */
export function AppLayout() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to="/tasks/new" className="brand">
          <span className="brand-mark">DH</span>
          <span>
            <strong>Digital Human Studio</strong>
            <small>数字人口播生成工作台</small>
          </span>
        </NavLink>
        <nav className="topnav" aria-label="主导航">
          <NavLink to="/tasks/new">任务</NavLink>
          <span>模板</span>
          <span>分发</span>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  )
}
