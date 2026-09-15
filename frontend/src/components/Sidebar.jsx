/**
 * src/components/Sidebar.jsx
 * Modernized SocialPilot sidebar — collapsible, grouped nav, Lucide icons, user footer.
 * Preserves all existing routes and auth/logout logic.
 */

import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import logoImg from '../assets/logo.png'
import {
  LayoutDashboard,
  SquarePen,
  FileText,
  CalendarDays,
  BookMarked,
  RefreshCw,
  Clock,
  Users2,
  BookImage,
  Megaphone,
  BarChart2,
  TrendingUp,
  UsersRound,
  Bell,
  Settings,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Briefcase,
} from 'lucide-react'
import './Sidebar.css'

const NAV_GROUPS = [
  {
    label: 'Overview',
    items: [
      { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    ],
  },
  {
    label: 'Publishing',
    items: [
      { label: 'Create Post',      path: '/posts?tab=create',    icon: SquarePen },
      { label: 'Posts',            path: '/posts',               icon: FileText },
      { label: 'Calendar',         path: '/posts?tab=calendar',  icon: CalendarDays },
      { label: 'Drafts',           path: '/posts?tab=drafts',    icon: BookMarked },
      { label: 'Recurring Posts',  path: '/posts?tab=recurring', icon: RefreshCw },
      { label: 'Publishing Queue', path: '/posts?tab=queue',     icon: Clock },
    ],
  },
  {
    label: 'Management',
    items: [
      { label: 'Social Accounts', path: '/accounts',   icon: Users2 },
      { label: 'Media Library',   path: '/posts?tab=media', icon: BookImage },
      { label: 'Campaigns',       path: '/campaigns',  icon: Megaphone },
    ],
  },
  {
    label: 'Insights',
    items: [
      { label: 'Analytics',   path: '/analytics', icon: BarChart2 },
      { label: 'Reports',     path: '/analytics', icon: TrendingUp },
    ],
  },
  {
    label: 'System',
    items: [
      { label: 'Notifications',   path: '/notifications', icon: Bell },
      { label: 'Team & Workspace', path: '/team',         icon: UsersRound },
      { label: 'Settings',        path: '/settings',      icon: Settings },
    ],
  },
]

export default function Sidebar({ mobileOpen, onCloseMobile, collapsed, onToggleCollapse }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [loggingOut, setLoggingOut] = useState(false)

  // Close mobile sidebar on Escape key
  useEffect(() => {
    if (!mobileOpen) return
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onCloseMobile()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [mobileOpen, onCloseMobile])

  const handleLogout = async () => {
    setLoggingOut(true)
    await logout()
    navigate('/login', { replace: true })
  }

  const initials = user?.full_name
    ? user.full_name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
    : 'U'

  const isActive = (path) => {
    const [pathname, search] = path.split('?')
    if (search) {
      const params = new URLSearchParams('?' + search)
      const tab = params.get('tab')
      return location.pathname === pathname && new URLSearchParams(location.search).get('tab') === tab
    }
    return location.pathname === pathname && !new URLSearchParams(location.search).get('tab')
  }

  return (
    <>
      {mobileOpen && <div className="sidebar-backdrop" onClick={onCloseMobile} />}
      <aside className={`sp-sidebar ${mobileOpen ? 'mobile-open' : ''} ${collapsed ? 'collapsed' : ''}`}>
        {/* Brand */}
        <div className="sp-sidebar-header">
          <Link to="/dashboard" className="sp-brand" onClick={onCloseMobile}>
            <img src={logoImg} alt="SocialPilot" className="sp-brand-icon" />
            {!collapsed && <span className="sp-brand-name">SocialPilot</span>}
          </Link>
          <button
            className="sp-collapse-btn"
            onClick={onToggleCollapse}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand' : 'Collapse'}
          >
            {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          </button>
          {mobileOpen && (
            <button className="sp-sidebar-close" onClick={onCloseMobile} aria-label="Close menu">
              ✕
            </button>
          )}
        </div>

        {/* Navigation */}
        <nav className="sp-sidebar-nav">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="sp-nav-group">
              {!collapsed && (
                <span className="sp-nav-group-label">{group.label}</span>
              )}
              {group.items.map((item) => {
                const Icon = item.icon
                const active = isActive(item.path)
                return (
                  <Link
                    key={item.path + item.label}
                    to={item.path}
                    className={`sp-nav-item ${active ? 'active' : ''}`}
                    onClick={onCloseMobile}
                    title={collapsed ? item.label : undefined}
                  >
                    <span className="sp-nav-icon">
                      <Icon size={16} strokeWidth={active ? 2.2 : 1.8} />
                    </span>
                    {!collapsed && <span className="sp-nav-label">{item.label}</span>}
                    {collapsed && (
                      <span className="sp-nav-tooltip">{item.label}</span>
                    )}
                  </Link>
                )
              })}
            </div>
          ))}
        </nav>

        {/* User Footer */}
        <div className="sp-sidebar-footer">
          <div className="sp-user-card">
            <Link to="/profile" className="sp-user-avatar" onClick={onCloseMobile} title="View profile">
              {initials}
            </Link>
            {!collapsed && (
              <div className="sp-user-info">
                <p className="sp-user-name" title={user?.full_name}>
                  {user?.full_name ?? 'User'}
                </p>
                <p className="sp-user-role">
                  <Briefcase size={10} />
                  {user?.role?.replace(/_/g, ' ') ?? 'member'}
                </p>
              </div>
            )}
            <button
              className="sp-logout-btn"
              onClick={handleLogout}
              disabled={loggingOut}
              title="Sign out"
              id="logout-btn"
              aria-label="Sign out"
            >
              {loggingOut
                ? <span className="spinner" style={{ width: 14, height: 14 }} />
                : <LogOut size={14} />
              }
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}
