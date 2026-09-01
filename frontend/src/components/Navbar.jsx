/**
 * src/components/Navbar.jsx
 * Top navigation bar with page title, search, and user profile actions.
 */

import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import './Navbar.css'

export default function Navbar({ pageTitle, pageSubtitle, mobileMenuLabel = 'Open menu', onMobileMenu }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const initials = user?.full_name
    ? user.full_name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
    : 'U'

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="dashboard-navbar glass-card">
      <div className="navbar-left">
        {onMobileMenu && (
          <button className="navbar-menu-btn" onClick={onMobileMenu} aria-label={mobileMenuLabel}>
            ☰
          </button>
        )}
        <div className="navbar-title-group">
          <h1 className="navbar-page-title">{pageTitle}</h1>
          {pageSubtitle && <p className="navbar-page-subtitle">{pageSubtitle}</p>}
        </div>
      </div>

      <div className="navbar-right">
        <div className="navbar-user">
          <Link to="/profile" className="navbar-user-link">
            <div className="navbar-avatar">{initials}</div>
            <div className="navbar-user-info">
              <span className="navbar-user-name">{user?.full_name || 'User'}</span>
              <span className="navbar-user-role">{user?.role?.replace('_', ' ') || 'member'}</span>
            </div>
          </Link>
          <button
            className="navbar-logout-btn"
            onClick={handleLogout}
            aria-label="Sign out"
            title="Sign out"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
          </button>
        </div>
      </div>
    </header>
  )
}
