import { NavLink, Outlet } from 'react-router-dom'

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
