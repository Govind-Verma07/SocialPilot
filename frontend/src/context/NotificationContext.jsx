/**
 * src/context/NotificationContext.jsx
 * ------------------------------------
 * Global notification state: unread count, polling, mark-as-read helpers.
 * Uses lightweight 30-second polling — no WebSocket needed.
 * All notifications come from the real backend database.
 */

import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { useAuth } from './AuthContext'
import notificationsApi from '../api/notificationsApi'

const NotificationContext = createContext(null)

const POLL_INTERVAL_MS = 30_000 // 30 seconds

export function NotificationProvider({ children }) {
  const { isAuthenticated } = useAuth()
  const [unreadCount, setUnreadCount] = useState(0)
  const [recentNotifs, setRecentNotifs] = useState([]) // up to 5 for dropdown
  const [loading, setLoading] = useState(false)
  const intervalRef = useRef(null)

  const fetchUnreadCount = useCallback(async () => {
    if (!isAuthenticated) return
    try {
      const { data } = await notificationsApi.unreadCount()
      setUnreadCount(data.unread_count ?? 0)
    } catch {
      // Silently ignore polling errors
    }
  }, [isAuthenticated])

  const fetchRecentNotifs = useCallback(async () => {
    if (!isAuthenticated) return
    try {
      const { data } = await notificationsApi.list({ page: 1, page_size: 5 })
      setRecentNotifs(data.items ?? [])
      setUnreadCount(data.unread_count ?? 0)
    } catch {
      // Silently ignore
    }
  }, [isAuthenticated])

  // On login/auth change, fetch immediately
  useEffect(() => {
    if (isAuthenticated) {
      fetchRecentNotifs()
    } else {
      setUnreadCount(0)
      setRecentNotifs([])
    }
  }, [isAuthenticated, fetchRecentNotifs])

  // Set up polling
  useEffect(() => {
    if (!isAuthenticated) {
      if (intervalRef.current) clearInterval(intervalRef.current)
      return
    }
    intervalRef.current = setInterval(fetchUnreadCount, POLL_INTERVAL_MS)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [isAuthenticated, fetchUnreadCount])

  const markRead = useCallback(async (id) => {
    try {
      await notificationsApi.markRead(id)
      setRecentNotifs((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      )
      setUnreadCount((c) => Math.max(0, c - 1))
    } catch { /* ignore */ }
  }, [])

  const markAllRead = useCallback(async () => {
    try {
      await notificationsApi.markAllRead()
      setRecentNotifs((prev) => prev.map((n) => ({ ...n, is_read: true })))
      setUnreadCount(0)
    } catch { /* ignore */ }
  }, [])

  const deleteNotif = useCallback(async (id) => {
    try {
      await notificationsApi.delete(id)
      const wasUnread = recentNotifs.find((n) => n.id === id && !n.is_read)
      setRecentNotifs((prev) => prev.filter((n) => n.id !== id))
      if (wasUnread) setUnreadCount((c) => Math.max(0, c - 1))
    } catch { /* ignore */ }
  }, [recentNotifs])

  const refreshNotifs = useCallback(() => {
    fetchRecentNotifs()
  }, [fetchRecentNotifs])

  return (
    <NotificationContext.Provider
      value={{
        unreadCount,
        recentNotifs,
        loading,
        markRead,
        markAllRead,
        deleteNotif,
        refreshNotifs,
      }}
    >
      {children}
    </NotificationContext.Provider>
  )
}

export function useNotifications() {
  const ctx = useContext(NotificationContext)
  if (!ctx) throw new Error('useNotifications must be used inside <NotificationProvider>')
  return ctx
}
