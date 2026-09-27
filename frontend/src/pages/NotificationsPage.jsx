/**
 * src/pages/NotificationsPage.jsx
 * --------------------------------
 * Full Notifications Page — Notification Module (Milestone 4).
 * All data comes from the real backend database. No fake/static data.
 * Features: paginated list, type filter, unread filter, mark read, mark all read, delete, loading/empty/error states.
 */

import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bell, CheckCheck, Trash2, RefreshCw, AlertCircle,
  CheckCircle2, Calendar, Megaphone, Info,
} from 'lucide-react'
import AppShell from '../components/AppShell'
import GlowCard from '../components/ui/GlowCard'
import Button from '../components/ui/Button'
import EmptyState from '../components/ui/EmptyState'
import notificationsApi from '../api/notificationsApi'
import { useNotifications } from '../context/NotificationContext'
import './NotificationsPage.css'

// ── Type metadata ────────────────────────────────────────────────
const TYPE_META = {
  post_published:    { icon: CheckCircle2, color: '#10b981', label: 'Published',   emoji: '✅' },
  post_failed:       { icon: AlertCircle,  color: '#ef4444', label: 'Failed',      emoji: '❌' },
  post_scheduled:    { icon: Calendar,     color: '#6366f1', label: 'Scheduled',   emoji: '📅' },
  campaign_created:  { icon: Megaphone,    color: '#f59e0b', label: 'Campaign',    emoji: '🎯' },
  campaign_updated:  { icon: Megaphone,    color: '#8b5cf6', label: 'Campaign',    emoji: '🎯' },
  campaign_completed:{ icon: CheckCheck,   color: '#10b981', label: 'Campaign',    emoji: '🏆' },
  account_issue:     { icon: AlertCircle,  color: '#f97316', label: 'Account',     emoji: '⚠️' },
  system_alert:      { icon: Info,         color: '#6366f1', label: 'System',      emoji: 'ℹ️' },
}

function getTypeMeta(type) {
  return TYPE_META[type] || { icon: Bell, color: '#6366f1', label: 'Notification', emoji: '🔔' }
}

function formatRelativeTime(dateStr) {
  if (!dateStr) return ''
  const now = new Date()
  const date = new Date(dateStr)
  const diffMs = now - date
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return 'just now'
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} min ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay < 7) return `${diffDay} days ago`
  return date.toLocaleDateString()
}

const TYPE_FILTERS = [
  { id: 'all',               label: 'All' },
  { id: 'post_published',    label: '✅ Published' },
  { id: 'post_failed',       label: '❌ Failed' },
  { id: 'post_scheduled',    label: '📅 Scheduled' },
  { id: 'campaign_created',  label: '🎯 Campaign Created' },
  { id: 'campaign_updated',  label: '🎯 Campaign Updated' },
  { id: 'campaign_completed',label: '🏆 Campaign Done' },
  { id: 'account_issue',     label: '⚠️ Account Issue' },
  { id: 'system_alert',      label: 'ℹ️ System' },
]

export default function NotificationsPage() {
  const navigate = useNavigate()
  const { refreshNotifs } = useNotifications()

  const [notifications, setNotifications] = useState([])
  const [total, setTotal] = useState(0)
  const [unreadCount, setUnreadCount] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [deletingId, setDeletingId] = useState(null)

  const PAGE_SIZE = 20

  const fetchNotifications = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = {
        page,
        page_size: PAGE_SIZE,
        unread_only: unreadOnly,
      }
      if (typeFilter !== 'all') params.type = typeFilter

      const { data } = await notificationsApi.list(params)
      setNotifications(data.items ?? [])
      setTotal(data.total ?? 0)
      setUnreadCount(data.unread_count ?? 0)
    } catch (err) {
      setError('Could not load notifications. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [page, typeFilter, unreadOnly])

  useEffect(() => {
    fetchNotifications()
  }, [fetchNotifications])

  const handleMarkRead = async (id) => {
    try {
      await notificationsApi.markRead(id)
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      )
      setUnreadCount((c) => Math.max(0, c - 1))
      refreshNotifs()
    } catch { /* ignore */ }
  }

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllRead()
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
      setUnreadCount(0)
      refreshNotifs()
    } catch { /* ignore */ }
  }

  const handleDelete = async (id) => {
    setDeletingId(id)
    try {
      await notificationsApi.delete(id)
      const deleted = notifications.find((n) => n.id === id)
      setNotifications((prev) => prev.filter((n) => n.id !== id))
      setTotal((t) => t - 1)
      if (deleted && !deleted.is_read) {
        setUnreadCount((c) => Math.max(0, c - 1))
        refreshNotifs()
      }
    } catch { /* ignore */ } finally {
      setDeletingId(null)
    }
  }

  const handleNotifClick = async (notif) => {
    if (!notif.is_read) await handleMarkRead(notif.id)
    if (notif.related_entity_type === 'post') navigate('/posts')
    else if (notif.related_entity_type === 'campaign') navigate('/campaigns')
    else if (notif.related_entity_type === 'social_account') navigate('/accounts')
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <AppShell pageTitle="Notifications" pageSubtitle="Publishing events, campaign activity, and system alerts">

      {/* Header Row */}
      <div className="notif-page-header">
        <div className="notif-page-stats">
          <span className="notif-page-count">{total} notification{total !== 1 ? 's' : ''}</span>
          {unreadCount > 0 && (
            <span className="notif-unread-chip">{unreadCount} unread</span>
          )}
        </div>
        <div className="notif-page-actions">
          <button
            className={`notif-filter-toggle ${unreadOnly ? 'active' : ''}`}
            onClick={() => { setUnreadOnly((u) => !u); setPage(1) }}
          >
            <Bell size={13} />
            Unread only
          </button>
          {unreadCount > 0 && (
            <Button variant="ghost" size="sm" onClick={handleMarkAllRead}>
              <CheckCheck size={14} /> Mark all read
            </Button>
          )}
          <button className="notif-refresh-btn" onClick={fetchNotifications} title="Refresh">
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Type Filters */}
      <div className="notif-filter-row">
        {TYPE_FILTERS.map((f) => (
          <button
            key={f.id}
            className={`notif-filter-chip ${typeFilter === f.id ? 'active' : ''}`}
            onClick={() => { setTypeFilter(f.id); setPage(1) }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="notif-loading">
          <div className="spinner-lg" />
          <span>Loading notifications...</span>
        </div>
      ) : error ? (
        <GlowCard className="notif-error-card">
          <AlertCircle size={24} color="#ef4444" />
          <p>{error}</p>
          <Button variant="ghost" size="sm" onClick={fetchNotifications}>Try again</Button>
        </GlowCard>
      ) : notifications.length === 0 ? (
        <EmptyState
          icon="🔔"
          title="No notifications yet"
          description={
            unreadOnly
              ? "You're all caught up! No unread notifications."
              : typeFilter !== 'all'
              ? "No notifications in this category."
              : "Post scheduling, publishing outcomes, and campaign activity will appear here."
          }
          actionLabel="Schedule a Post"
          onAction={() => navigate('/posts?tab=create')}
          size="md"
        />
      ) : (
        <>
          <div className="notif-list">
            {notifications.map((notif) => {
              const meta = getTypeMeta(notif.type)
              const Icon = meta.icon
              return (
                <div
                  key={notif.id}
                  className={`notif-row ${!notif.is_read ? 'unread' : ''}`}
                >
                  {/* Icon */}
                  <div
                    className="notif-row-icon"
                    style={{ background: `${meta.color}18`, color: meta.color }}
                  >
                    <Icon size={16} />
                  </div>

                  {/* Body — clickable */}
                  <button
                    className="notif-row-body"
                    onClick={() => handleNotifClick(notif)}
                  >
                    <div className="notif-row-top">
                      <span className="notif-row-title">{notif.title}</span>
                      {!notif.is_read && <span className="notif-row-new-dot" />}
                      <span className="notif-row-type-pill" style={{ color: meta.color, background: `${meta.color}15` }}>
                        {meta.label}
                      </span>
                      {notif.email_status === 'sent' && (
                        <span className="notif-row-type-pill" style={{ color: '#10b981', background: 'rgba(16,185,129,0.12)' }} title="Email notification delivered">
                          📧 Sent
                        </span>
                      )}
                      {notif.email_status === 'failed' && (
                        <span className="notif-row-type-pill" style={{ color: '#ef4444', background: 'rgba(239,68,68,0.12)' }} title={notif.email_error || 'Email delivery failed'}>
                          📧 Failed
                        </span>
                      )}
                    </div>
                    <p className="notif-row-msg">{notif.message}</p>
                    <span className="notif-row-time">{formatRelativeTime(notif.created_at)}</span>
                  </button>

                  {/* Actions */}
                  <div className="notif-row-actions">
                    {!notif.is_read && (
                      <button
                        className="notif-action-btn"
                        onClick={() => handleMarkRead(notif.id)}
                        title="Mark as read"
                      >
                        <CheckCircle2 size={14} />
                      </button>
                    )}
                    <button
                      className="notif-action-btn danger"
                      onClick={() => handleDelete(notif.id)}
                      disabled={deletingId === notif.id}
                      title="Delete notification"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="notif-pagination">
              <button
                className="notif-page-btn"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                ← Previous
              </button>
              <span className="notif-page-indicator">
                Page {page} of {totalPages}
              </span>
              <button
                className="notif-page-btn"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </AppShell>
  )
}
