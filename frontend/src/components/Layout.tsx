import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useProfile } from '../auth/ProfileContext'
import { notificationApi } from '../api/endpoints'
import { centsToYuan } from '../utils/money'
import { BrandMark, Icon } from './Icon'
import type { IconName } from './Icon'

interface NavItem {
  to: string
  label: string
  icon: IconName
  mobile: boolean
}

const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: '记账',
    items: [
      { to: '/', label: '首页', icon: 'home', mobile: true },
      { to: '/bills', label: '账单', icon: 'receipt', mobile: true },
      { to: '/budgets', label: '预算', icon: 'wallet', mobile: true },
      { to: '/analytics', label: '分析', icon: 'chart', mobile: true },
    ],
  },
  {
    label: '规划',
    items: [
      { to: '/ai', label: 'AI 助手', icon: 'sparkles', mobile: false },
      { to: '/goals', label: '储蓄目标', icon: 'target', mobile: false },
    ],
  },
  {
    label: '管理',
    items: [
      { to: '/notifications', label: '提醒', icon: 'bell', mobile: false },
      { to: '/reports', label: '报告', icon: 'file-text', mobile: false },
      { to: '/settings', label: '设置', icon: 'settings', mobile: true },
    ],
  },
]

const NAV = NAV_GROUPS.flatMap((g) => g.items)

function todayLabel() {
  const d = new Date()
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日 · ${weekdays[d.getDay()]}`
}

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
  const initial = user?.username.slice(0, 1).toUpperCase() ?? '?'

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <BrandMark size={38} />
          <div>
            <div className="brand-name">钱途</div>
            <div className="brand-sub">大学生智能财务</div>
          </div>
        </div>

        <nav className="side-nav" aria-label="主导航">
          {NAV_GROUPS.map((group) => (
            <div className="side-group" key={group.label}>
              <p className="side-group-label">{group.label}</p>
              {group.items.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  end={n.to === '/'}
                  className={({ isActive }) => `side-link ${isActive ? 'active' : ''}`}
                >
                  <span className="nav-icon"><Icon name={n.icon} size={19} /></span>
                  <span>{n.label}</span>
                  {n.to === '/notifications' && unread > 0 && (
                    <span className="badge badge-danger nav-badge">{unread > 99 ? '99+' : unread}</span>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="side-user">
          <div className="avatar">{initial}</div>
          <div className="side-user-info">
            <div className="side-user-name">{user?.username}</div>
            <div className="side-user-sub">
              {profile?.initialized
                ? `资产 ¥${centsToYuan(profile.current_assets_cents)}`
                : '资料未初始化'}
            </div>
          </div>
          <button
            type="button"
            className="icon-btn"
            title="退出登录"
            aria-label="退出登录"
            onClick={() => { logout(); navigate('/login') }}
          >
            <Icon name="logout" size={18} />
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-heading">
            <h1 className="page-title">{current?.label ?? '钱途'}</h1>
            <span className="topbar-date">{todayLabel()}</span>
          </div>
          <div className="topbar-right">
            <button
              type="button"
              className={`icon-btn topbar-ai ${location.pathname === '/ai' ? 'active' : ''}`}
              aria-label="AI 助手"
              title="AI 助手"
              onClick={() => navigate('/ai')}
            >
              <Icon name="sparkles" size={19} />
            </button>
            <button
              type="button"
              className="icon-btn bell"
              aria-label={unread > 0 ? `提醒，${unread} 条未读` : '提醒'}
              onClick={() => navigate('/notifications')}
            >
              <Icon name="bell" size={19} />
              {unread > 0 && (
                <span className="badge badge-danger bell-badge">{unread > 99 ? '99+' : unread}</span>
              )}
            </button>
            <div className="topbar-user-wrap">
              <span className="topbar-avatar" aria-hidden="true">{initial}</span>
              <span className="topbar-user">{user?.username}</span>
            </div>
          </div>
        </header>

        <main className="content">
          <Outlet />
        </main>
      </div>

      <nav className="bottom-nav" aria-label="移动端导航">
        {NAV.filter((n) => n.mobile).map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === '/'}
            className={({ isActive }) => `bottom-link ${isActive ? 'active' : ''}`}
          >
            <span className="bottom-icon"><Icon name={n.icon} size={20} /></span>
            <span className="bottom-label">{n.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
