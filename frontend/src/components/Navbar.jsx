/**
 * src/components/Navbar.jsx
 * Modern top bar — search, quick create, notifications bell with real backend data, theme toggle, user menu.
 * Preserves all existing auth/logout logic.
 * Notification bell shows real unread count from backend and a dropdown with recent notifications.
 */

import { Link, useNavigate } from 'react-router-dom'
import { useState, useEffect, useRef, useCallback } from 'react'
import { useAuth } from '../context/AuthContext'
import { useNotifications } from '../context/NotificationContext'
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
  CheckCheck,
  Megaphone,
  AlertCircle,
  CheckCircle2,
  Clock,
  Calendar,
  X,
} from 'lucide-react'
import GlobalSearch from './GlobalSearch'
import './Navbar.css'

// Map notification type to icon and color
const NOTIF_TYPE_META = {
  post_published:    { icon: CheckCircle2, color: '#10b981', label: 'Published' },
  post_failed:       { icon: AlertCircle,  color: '#ef4444', label: 'Failed' },
  post_scheduled:    { icon: Calendar,     color: '#6366f1', label: 'Scheduled' },
  campaign_created:  { icon: Megaphone,    color: '#f59e0b', label: 'Campaign' },
  campaign_updated:  { icon: Megaphone,    color: '#8b5cf6', label: 'Campaign' },
  campaign_completed:{ icon: CheckCheck,   color: '#10b981', label: 'Campaign' },
  account_issue:     { icon: AlertCircle,  color: '#f97316', label: 'Account' },
  system_alert:      { icon: Bell,         color: '#6366f1', label: 'System' },
}

function getNotifMeta(type) {
  return NOTIF_TYPE_META[type] || { icon: Bell, color: '#6366f1', label: 'Notification' }
}

function formatRelativeTime(dateStr) {
  if (!dateStr) return ''
  const now = new Date()
  const date = new Date(dateStr)
  const diffMs = now - date
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return 'just now'
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay < 7) return `${diffDay}d ago`
  return date.toLocaleDateString()
}

function NotificationDropdown({ onClose }) {
  const navigate = useNavigate()
  const { recentNotifs, unreadCount, markRead, markAllRead, refreshNotifs } = useNotifications()

  useEffect(() => {
    refreshNotifs()
  }, [refreshNotifs])

  const handleNotifClick = async (notif) => {
    if (!notif.is_read) {
      await markRead(notif.id)
    }
    onClose()
    // Navigate to related entity
    if (notif.related_entity_type === 'post') {
      navigate('/posts')
    } else if (notif.related_entity_type === 'campaign') {
      navigate('/campaigns')
    } else if (notif.related_entity_type === 'social_account') {
      navigate('/accounts')
    }
  }

  const handleMarkAll = async (e) => {
    e.stopPropagation()
    await markAllRead()
  }

  return (
    <div className="sp-notif-dropdown" role="dialog" aria-label="Notifications">
      {/* Header */}
      <div className="sp-notif-dropdown-header">
        <span className="sp-notif-dropdown-title">
          🔔 Notifications
          {unreadCount > 0 && (
            <span className="sp-notif-dropdown-badge">{unreadCount}</span>
          )}
        </span>
        <div className="sp-notif-dropdown-actions">
          {unreadCount > 0 && (
            <button
              className="sp-notif-mark-all-btn"
              onClick={handleMarkAll}
              title="Mark all as read"
            >
              <CheckCheck size={13} />
              <span>Mark all read</span>
            </button>
          )}
          <button className="sp-notif-close-btn" onClick={onClose} aria-label="Close">
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Notification items */}
      <div className="sp-notif-dropdown-list">
        {recentNotifs.length === 0 ? (
          <div className="sp-notif-empty">
            <Bell size={28} strokeWidth={1.4} />
            <p>No notifications yet.</p>
            <span>Activity from posts, campaigns, and accounts will appear here.</span>
          </div>
        ) : (
          recentNotifs.map((notif) => {
            const meta = getNotifMeta(notif.type)
            const Icon = meta.icon
            return (
              <button
                key={notif.id}
                className={`sp-notif-item ${!notif.is_read ? 'unread' : ''}`}
                onClick={() => handleNotifClick(notif)}
              >
                <span
                  className="sp-notif-item-icon"
                  style={{ background: `${meta.color}18`, color: meta.color }}
                >
                  <Icon size={14} />
                </span>
                <span className="sp-notif-item-body">
                  <span className="sp-notif-item-title">
                    {notif.title}
                    {!notif.is_read && <span className="sp-notif-dot" />}
                  </span>
                  <span className="sp-notif-item-msg">{notif.message}</span>
                  <span className="sp-notif-item-time">
                    {formatRelativeTime(notif.created_at)}
                  </span>
                </span>
              </button>
            )
          })
        )}
      </div>

      {/* Footer: view all */}
      <div className="sp-notif-dropdown-footer">
        <Link
          to="/notifications"
          className="sp-notif-view-all"
          onClick={onClose}
        >
          View all notifications →
        </Link>
      </div>
    </div>
  )
}

export default function Navbar({ pageTitle, pageSubtitle, onMobileMenu, onSidebarToggle }) {
  const { user, logout } = useAuth()
  const { unreadCount } = useNotifications()
  const navigate = useNavigate()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false)
  const [theme, setTheme] = useState(() => localStorage.getItem('sp-theme') || 'dark')
  const notifRef = useRef(null)

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

  // Close dropdown on outside click
  useEffect(() => {
    if (!notifOpen) return
    const handleOutside = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) {
        setNotifOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [notifOpen])

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

        {/* Notifications Bell with Badge */}
        <div className="sp-notif-wrapper" ref={notifRef}>
          <button
            className={`sp-topbar-icon-btn sp-notif-bell-btn ${notifOpen ? 'active' : ''}`}
            onClick={() => setNotifOpen((o) => !o)}
            title="Notifications"
            id="topbar-notifications"
            aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
          >
            <Bell size={17} />
            {unreadCount > 0 && (
              <span className="sp-notif-badge" aria-hidden="true">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>

          {notifOpen && (
            <NotificationDropdown onClose={() => setNotifOpen(false)} />
          )}
        </div>

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
