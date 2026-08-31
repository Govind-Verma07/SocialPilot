/**
 * src/context/AuthContext.jsx
 * ----------------------------
 * Global authentication state.
 * Persists access token + user profile in localStorage so sessions survive
 * page refreshes.
 */

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { authApi } from '../api/authApi'

const AuthContext = createContext(null)

const TOKEN_KEY = 'sp_access_token'
const USER_KEY  = 'sp_user'

export function AuthProvider({ children }) {
  const [user,  setUser]  = useState(() => {
    try { return JSON.parse(localStorage.getItem(USER_KEY)) } catch { return null }
  })
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? null)
  const [loading, setLoading] = useState(false)

  // ── Persist helpers ─────────────────────────────────────────────────────
  const persist = useCallback((accessToken, userObj) => {
    localStorage.setItem(TOKEN_KEY, accessToken)
    localStorage.setItem(USER_KEY, JSON.stringify(userObj))
    setToken(accessToken)
    setUser(userObj)
  }, [])

  const clear = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
  }, [])

  const formatError = (err, defaultMsg) => {
    if (!err.response) {
      return 'Unable to connect to backend server. Please verify the backend is running at http://localhost:8000.'
    }
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || item.message || JSON.stringify(item)).join('. ')
    }
    if (detail && typeof detail === 'object') {
      return detail.msg || detail.message || JSON.stringify(detail)
    }
    return defaultMsg
  }

  // ── Actions ─────────────────────────────────────────────────────────────
  const register = useCallback(async ({ fullName, email, password, role }) => {
    setLoading(true)
    try {
      const { data } = await authApi.register({
        full_name: fullName,
        email,
        password,
        role: role || 'content_creator',
      })
      persist(data.access_token, data.user)
      return { success: true }
    } catch (err) {
      return { success: false, message: formatError(err, 'Registration failed.') }
    } finally {
      setLoading(false)
    }
  }, [persist])

  const login = useCallback(async ({ email, password }) => {
    setLoading(true)
    try {
      const { data } = await authApi.login({ email, password })
      persist(data.access_token, data.user)
      return { success: true }
    } catch (err) {
      return { success: false, message: formatError(err, 'Login failed.') }
    } finally {
      setLoading(false)
    }
  }, [persist])

  const updateProfile = useCallback(async (profileData) => {
    setLoading(true)
    try {
      const { data } = await authApi.updateProfile(profileData)
      setUser(data)
      localStorage.setItem(USER_KEY, JSON.stringify(data))
      return { success: true, user: data }
    } catch (err) {
      return { success: false, message: formatError(err, 'Failed to update profile.') }
    } finally {
      setLoading(false)
    }
  }, [])

  const logout = useCallback(async () => {
    try { await authApi.logout() } catch { /* ignore */ }
    clear()
  }, [clear])

  // ── Re-validate token on mount ──────────────────────────────────────────
  useEffect(() => {
    if (!token) return
    authApi.me()
      .then(({ data }) => setUser(data))
      .catch(() => clear())
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <AuthContext.Provider value={{ user, token, loading, register, login, logout, updateProfile, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
