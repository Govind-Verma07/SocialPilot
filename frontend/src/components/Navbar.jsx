/**
 * src/components/Navbar.jsx
 * Modern top bar — search, quick create, notifications, theme toggle, user menu.
 * Preserves all existing auth/logout logic.
 */

import { Link, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import {
  Search,
  Bell,
  PlusCircle,
  Sun,
  Moon,
  ChevronDown,
  User,
  Settings,
  LogOut,
  Menu,
  PanelLeft,
} from 'lucide-react'
import GlobalSearch from './GlobalSearch'
import './Navbar.css'

export default function Navbar({ pageTitle, pageSubtitle, onMobileMenu, onSidebarToggle }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false)
  const [theme, setTheme] = useState(() => localStorage.getItem('sp-theme') || 'dark')

  useEffect(() => {
    document.documentElement.classList.toggle('light', theme === 'light')
    localStorage.setItem('sp-theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))

  const initials = user?.full_name
    ? user.full_name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
    : 'U'

  const handleLogout = async () => {
    setUserMenuOpen(false)
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="sp-topbar">
      {/* Left: mobile menu + page title */}
      <div className="sp-topbar-left">
        {onMobileMenu && (
          <button
            className="sp-topbar-menu-btn"
            onClick={onMobileMenu}
            aria-label="Open sidebar"
          >
            <Menu size={18} />
          </button>
        )}
        {onSidebarToggle && (
          <button
            className="sp-topbar-sidebar-toggle"
            onClick={onSidebarToggle}
            aria-label="Toggle sidebar view"
            title="Toggle sidebar (compact / expanded)"
          >
            <PanelLeft size={18} />
          </button>
        )}
        {pageTitle && (
          <div className="sp-topbar-title-group">
            <h1 className="sp-topbar-title">{pageTitle}</h1>
            {pageSubtitle && <p className="sp-topbar-subtitle">{pageSubtitle}</p>}
          </div>
        )}
      </div>

      {/* Center: Live Global Search */}
      <div className="sp-topbar-search-wrapper">
        <GlobalSearch isMobileOpen={false} />
      </div>

      {/* Mobile Search Modal if toggled */}
      {mobileSearchOpen && (
        <GlobalSearch
          isMobileOpen={true}
          onCloseMobileSearch={() => setMobileSearchOpen(false)}
        />
      )}

      {/* Right: actions */}
      <div className="sp-topbar-actions">
        {/* Mobile Search Trigger Button */}
        <button
          className="sp-topbar-icon-btn sp-mobile-search-trigger"
          onClick={() => setMobileSearchOpen(true)}
          title="Search"
          aria-label="Search"
        >
          <Search size={17} />
        </button>

        {/* Quick Create */}
        <button
          className="sp-topbar-create-btn"
          onClick={() => navigate('/posts?tab=create')}
          title="Create post"
          id="topbar-create-post"
        >
          <PlusCircle size={15} />
          <span>Create</span>
        </button>

        {/* Notifications */}
        <Link to="/notifications" className="sp-topbar-icon-btn" title="Notifications" id="topbar-notifications">
          <Bell size={17} />
        </Link>

        {/* Theme toggle */}
        <button
          className="sp-topbar-icon-btn"
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          id="topbar-theme-toggle"
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
        </button>

        {/* User menu */}
        <div className="sp-user-menu-wrapper">
          <button
            className="sp-topbar-user-btn"
            onClick={() => setUserMenuOpen((o) => !o)}
            aria-haspopup="true"
            aria-expanded={userMenuOpen}
            id="topbar-user-menu-btn"
          >
            <div className="sp-topbar-avatar">{initials}</div>
            <span className="sp-topbar-user-name">{user?.full_name?.split(' ')[0] ?? 'User'}</span>
            <ChevronDown size={13} className={`sp-chevron ${userMenuOpen ? 'open' : ''}`} />
          </button>

          {userMenuOpen && (
            <>
              <div className="sp-user-menu-backdrop" onClick={() => setUserMenuOpen(false)} />
              <div className="sp-user-menu">
                <div className="sp-user-menu-header">
                  <div className="sp-um-avatar">{initials}</div>
                  <div className="sp-um-info">
                    <p className="sp-um-name">{user?.full_name}</p>
                    <p className="sp-um-email">{user?.email}</p>
                  </div>
                </div>
                <div className="sp-user-menu-divider" />
                <Link to="/profile" className="sp-user-menu-item" onClick={() => setUserMenuOpen(false)}>
                  <User size={14} /> Profile
                </Link>
                <Link to="/settings" className="sp-user-menu-item" onClick={() => setUserMenuOpen(false)}>
                  <Settings size={14} /> Settings
                </Link>
                <div className="sp-user-menu-divider" />
                <button className="sp-user-menu-item destructive" onClick={handleLogout}>
                  <LogOut size={14} /> Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
