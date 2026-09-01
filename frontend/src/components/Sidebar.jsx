/**
 * src/components/Sidebar.jsx
 * ---------------------------
 * Navigation sidebar for SocialPilot aligned strictly with the Architecture & Modules PDF.
 * Provides active links for Dashboard, Accounts, Posts & Calendar, Campaigns, Analytics, Notifications, Team, Profile, and Settings.
 */

import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import logoImg from '../assets/logo.png'
import './Sidebar.css'

export default function Sidebar({ mobileOpen, onCloseMobile }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [loggingOut, setLoggingOut] = useState(false)

  const handleLogout = async () => {
    setLoggingOut(true)
    await logout()
    navigate('/login', { replace: true })
  }

  const initials = user?.full_name
    ? user.full_name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
    : 'U'

  const mainNav = [
    { label: 'Overview', path: '/dashboard', icon: '🏠' },
    { label: 'Accounts', path: '/accounts',  icon: '🔗' },
  ]

  const publishingNav = [
    { label: 'Posts & Calendar', path: '/posts',         icon: '📝' },
    { label: 'Campaigns',        path: '/campaigns',     icon: '🎯' },
    { label: 'Analytics',        path: '/analytics',     icon: '📊' },
    { label: 'Notifications',    path: '/notifications', icon: '🔔' },
  ]

  const adminNav = [
    { label: 'Team Workspace',  path: '/team',     icon: '👥' },
    { label: 'Profile',         path: '/profile',  icon: '👤' },
    { label: 'Settings',        path: '/settings', icon: '⚙️' },
  ]

  const renderNavGroup = (items) => (
    <nav className="sidebar-nav">
      {items.map((item) => {
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
  )

  return (
    <>
      {mobileOpen && <div className="sidebar-backdrop" onClick={onCloseMobile} />}
      <aside className={`dashboard-sidebar glass-card ${mobileOpen ? 'open' : ''}`}>
        <Link to="/dashboard" className="sidebar-brand" style={{ textDecoration: 'none' }}>
          <img src={logoImg} alt="SocialPilot Logo" className="brand-icon-sm" />
          <span className="brand-name-sm">SocialPilot</span>
          {mobileOpen && (
            <button className="sidebar-close-btn" onClick={(e) => { e.preventDefault(); onCloseMobile(); }} aria-label="Close menu">
              ✕
            </button>
          )}
        </Link>

        <div className="sidebar-section-label">MAIN WORKSPACE</div>
        {renderNavGroup(mainNav)}

        <div className="sidebar-section-label">PUBLISHING & ANALYTICS</div>
        {renderNavGroup(publishingNav)}

        <div className="sidebar-section-label">ADMINISTRATION</div>
        {renderNavGroup(adminNav)}

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
            aria-label="Sign out"
          >
            {loggingOut ? '…' : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            )}
          </button>
        </div>
      </aside>
    </>
  )
}
