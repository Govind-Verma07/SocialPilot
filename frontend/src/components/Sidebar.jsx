/**
 * src/components/Sidebar.jsx
 * --------------------------
 * Navigation sidebar for SocialPilot account management.
 */

import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import './Sidebar.css'

export default function Sidebar({ mobileOpen, onCloseMobile }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [loggingOut, setLoggingOut] = useState(false)

  const handleLogout = async () => {
    setLoggingOut(true)
    await logout()
    navigate('/login')
  }

  const initials = user?.full_name
    ? user.full_name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
    : 'U'

  const navItems = [
    { label: 'Overview', path: '/dashboard', icon: '🏠' },
    { label: 'Accounts', path: '/accounts',  icon: '🔗' },
    { label: 'Team',     path: '/team',      icon: '👥' },
    { label: 'Profile',  path: '/profile',   icon: '👤' },
    { label: 'Settings', path: '/settings',  icon: '⚙️' },
  ]

  const futureItems = [
    { label: 'Posts & Drafts', icon: '📝' },
    { label: 'Calendar',       icon: '📅' },
    { label: 'Campaigns',      icon: '🎯' },
    { label: 'Analytics',      icon: '📊' },
  ]

  return (
    <>
      {mobileOpen && <div className="sidebar-backdrop" onClick={onCloseMobile} />}
      <aside className={`dashboard-sidebar glass-card ${mobileOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <span className="brand-icon-sm">🚀</span>
          <span className="brand-name-sm">SocialPilot</span>
          {mobileOpen && (
            <button className="sidebar-close-btn" onClick={onCloseMobile} aria-label="Close menu">
              ✕
            </button>
          )}
        </div>

        <div className="sidebar-section-label">MANAGEMENT</div>
        <nav className="sidebar-nav">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`nav-item ${isActive ? 'active' : ''}`}
                onClick={onCloseMobile}
              >
                <span className="nav-icon">{item.icon}</span>
                <span className="nav-label">{item.label}</span>
              </Link>
            )
          })}
        </nav>

        <div className="sidebar-section-label" style={{ marginTop: '16px' }}>
          SCHEDULE & PUBLISH
        </div>
        <div className="sidebar-nav future-nav">
          {futureItems.map((item) => (
            <div key={item.label} className="nav-item future-item" title="Coming in Milestone 2+">
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
              <span className="badge-soon">Soon</span>
            </div>
          ))}
        </div>

        {/* User profile in sidebar */}
        <div className="sidebar-user">
          <div className="user-avatar">{initials}</div>
          <div className="user-info">
            <p className="user-name" title={user?.full_name}>{user?.full_name ?? 'User'}</p>
            <p className="user-role-tag">{user?.role?.replace('_', ' ') ?? 'member'}</p>
          </div>
          <button
            className="logout-btn"
            onClick={handleLogout}
            disabled={loggingOut}
            title="Sign out"
            id="logout-btn"
          >
            {loggingOut ? '…' : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                <polyline points="16 17 21 12 16 7"/>
                <line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
            )}
          </button>
        </div>
      </aside>
    </>
  )
}
