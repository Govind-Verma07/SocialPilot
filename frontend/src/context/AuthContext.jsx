/**
 * src/context/AuthContext.jsx
 * ---------------------------
 * Provides global auth state (user, loading) and actions (register, login, logout).
 * Persists JWT token and user object in localStorage under 'sp_access_token' / 'sp_user'.
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { authApi } from '../api/authApi'

// ── Context ──────────────────────────────────────────────────────────────────
const AuthContext = createContext(null)

// ── Provider ─────────────────────────────────────────────────────────────────
export function AuthProvider({ children }) {
  const [user, setUser]       = useState(() => {
    try { return JSON.parse(localStorage.getItem('sp_user')) ?? null }
    catch { return null }
  })
  const [loading, setLoading] = useState(false)

  // On mount, re-validate token with the server if we have one
  useEffect(() => {
    const token = localStorage.getItem('sp_access_token')
    if (!token) return

    let cancelled = false
    authApi.me()
      .then(({ data }) => {
        if (!cancelled) setUser(data.user ?? data)
      })
      .catch(() => {
        if (!cancelled) {
          localStorage.removeItem('sp_access_token')
          localStorage.removeItem('sp_user')
          setUser(null)
        }
      })
    return () => { cancelled = true }
  }, [])

  // ── register ───────────────────────────────────────────────────────────────
  const register = useCallback(async ({ fullName, email, password, role }) => {
    setLoading(true)
    try {
      const { data } = await authApi.register({ full_name: fullName, email, password, role })
      return { success: true, data }
    } catch (err) {
      let message = 'Registration failed. Please try again.'
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') {
        message = detail
      } else if (Array.isArray(detail)) {
        message = detail.map((d) => d.msg || d.message).join('; ')
      } else if (err.response?.data?.message) {
        message = err.response.data.message
      } else if (err.message) {
        message = err.message
      }
      return { success: false, message }
    } finally {
      setLoading(false)
    }
  }, [])

  // ── login ──────────────────────────────────────────────────────────────────
  const login = useCallback(async ({ email, password }) => {
    setLoading(true)
    try {
      const { data } = await authApi.login({ email, password })
      const token = data.access_token ?? data.accessToken ?? data.token
      const userData = data.user ?? { email }
      if (token) localStorage.setItem('sp_access_token', token)
      localStorage.setItem('sp_user', JSON.stringify(userData))
      setUser(userData)
      return { success: true, user: userData }
    } catch (err) {
      let message = 'Invalid email or password.'
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') {
        message = detail
      } else if (Array.isArray(detail)) {
        message = detail.map((d) => d.msg || d.message).join('; ')
      } else if (err.response?.data?.message) {
        message = err.response.data.message
      } else if (err.message) {
        message = err.message
      }
      return { success: false, message }
    } finally {
      setLoading(false)
    }
  }, [])

  // ── logout ─────────────────────────────────────────────────────────────────
  const logout = useCallback(async () => {
    try {
      if (typeof authApi.logout === 'function') {
        await authApi.logout()
      }
    } catch {
      // Ignore API errors during logout
    } finally {
      localStorage.removeItem('sp_access_token')
      localStorage.removeItem('sp_user')
      setUser(null)
    }
  }, [])

  // ── updateUser (for ProfilePage / SettingsPage) ────────────────────────────
  const updateUser = useCallback((partial) => {
    setUser((prev) => {
      const next = { ...prev, ...partial }
      localStorage.setItem('sp_user', JSON.stringify(next))
      return next
    })
  }, [])

  // ── loginWithToken (OAuth) ──────────────────────────────────────────────────
  const loginWithToken = useCallback((token, userData) => {
    if (token) localStorage.setItem('sp_access_token', token)
    if (userData) localStorage.setItem('sp_user', JSON.stringify(userData))
    setUser(userData)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, isAuthenticated: !!user, register, login, loginWithToken, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  )
}

// ── Hook ──────────────────────────────────────────────────────────────────────
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
