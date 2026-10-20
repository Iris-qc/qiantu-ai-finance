import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useProfile } from '../auth/ProfileContext'
import { notificationApi } from '../api/endpoints'

const NAV = [
  { to: '/', label: '首页', icon: '🏠', mobile: true },
  { to: '/bills', label: '账单', icon: '📒', mobile: true },
  { to: '/budgets', label: '预算', icon: '💰', mobile: true },
  { to: '/analytics', label: '分析', icon: '📈', mobile: true },
  { to: '/ai', label: 'AI 助手', icon: '🤖', mobile: false },
  { to: '/goals', label: '储蓄目标', icon: '🎯', mobile: false },
  { to: '/notifications', label: '提醒', icon: '🔔', mobile: false },
  { to: '/reports', label: '报告', icon: '📄', mobile: false },
  { to: '/settings', label: '设置', icon: '⚙️', mobile: true },
]

function useUnread() {
  const [unread, setUnread] = useState(0)
  useEffect(() => {
    let cancelled = false
    const load = () => {
      notificationApi.list()
        .then((r) => { if (!cancelled) setUnread(r.unread_count) })
        .catch(() => { /* 顶部角标失败不打扰 */ })
    }
    load()
    window.addEventListener('csaifm:refresh-notifs', load)
    return () => {
      cancelled = true
      window.removeEventListener('csaifm:refresh-notifs', load)
    }
  }, [])
  return unread
}

export default function Layout() {
  const { user, logout } = useAuth()
  const { profile } = useProfile()
  const location = useLocation()
  const navigate = useNavigate()
  const unread = useUnread()
  const current = NAV.find((n) => n.to === location.pathname)

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-icon">🎓</span>
          <div>
            <div className="brand-name">智能财务</div>
            <div className="brand-sub">大学生理财平台</div>
          </div>
        </div>
        <nav className="side-nav">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'}
                     className={({ isActive }) => `side-link ${isActive ? 'active' : ''}`}>
              <span className="nav-icon">{n.icon}</span>
              <span>{n.label}</span>
              {n.to === '/notifications' && unread > 0 && (
                <span className="badge badge-danger nav-badge">{unread}</span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="side-user">
          <div className="avatar">{user?.username.slice(0, 1).toUpperCase()}</div>
          <div className="side-user-info">
            <div className="side-user-name">{user?.username}</div>
            {profile?.initialized && (
              <div className="side-user-sub">资产 ¥{profile.current_assets_cents / 100}</div>
            )}
          </div>
          <button type="button" className="icon-btn" title="退出登录" onClick={() => { logout(); navigate('/login') }}>⏻</button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <h1 className="page-title">{current?.label ?? ''}</h1>
          <div className="topbar-right">
            <button type="button" className="icon-btn bell" aria-label="提醒"
                    onClick={() => navigate('/notifications')}>
              🔔
              {unread > 0 && <span className="badge badge-danger bell-badge">{unread}</span>}
            </button>
            <span className="topbar-user">{user?.username}</span>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>

      {/* AI 助手悬浮按钮（移动端） */}
      <button type="button" className="fab"
              title="AI 智能记账"
              onClick={() => navigate('/ai')}
              style={{ display: location.pathname === '/ai' ? 'none' : undefined }}>
        🤖
      </button>

      <nav className="bottom-nav">
        {NAV.filter((n) => n.mobile).map((n) => (
          <NavLink key={n.to} to={n.to} end={n.to === '/'}
                   className={({ isActive }) => `bottom-link ${isActive ? 'active' : ''}`}>
            <span className="bottom-icon">{n.icon}</span>
            <span className="bottom-label">{n.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
