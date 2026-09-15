/**
 * src/api/authApi.js
 * ------------------
 * Axios instance pre-configured with the API base URL.
 * Request interceptor automatically attaches the JWT Bearer token.
 * Response interceptor clears localStorage on 401 (token expired / invalid).
 */

import axios from 'axios'

const getBaseURL = () => {
  const envUrl = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_BACKEND_URL || ''
  if (!envUrl) return '/api/v1'
  const trimmed = envUrl.replace(/\/+$/, '')
  if (trimmed.endsWith('/api/v1')) return trimmed
  if (trimmed.endsWith('/api')) return `${trimmed}/v1`
  return `${trimmed}/api/v1`
}

const baseURL = getBaseURL()

const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 10000,
})

// ── Request: inject Bearer token ────────────────────────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('sp_access_token')
  if (token) {
    if (config.headers?.set) {
      config.headers.set('Authorization', `Bearer ${token}`)
    } else {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }
  }
  // If sending FormData, delete Content-Type so browser/Axios sets boundary automatically
  if (config.data instanceof FormData) {
    if (config.headers?.delete) {
      config.headers.delete('Content-Type')
    } else if (config.headers) {
      delete config.headers['Content-Type']
    }
  }
  return config
})

// ── Response: handle 401 gracefully ────────────────────────────────────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('sp_access_token')
      localStorage.removeItem('sp_user')
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('auth:unauthorized'))
      }
    }
    return Promise.reject(error)
  }
)

// ── Auth & User endpoints ───────────────────────────────────────────────────
export const authApi = {
  register:       (data) => api.post('/auth/register', data),
  login:          (data) => api.post('/auth/login', data),
  logout:         ()     => api.post('/auth/logout'),
  me:             ()     => api.get('/auth/me'),
  getGoogleAuthUrl: ()   => api.get('/auth/google/url'),
  updateProfile:  (data) => api.patch('/users/me', data),
  getSettings:    ()     => api.get('/users/me/settings'),
  updateSettings: (data) => api.put('/users/me/settings', data),
  resetPassword:  (data) => api.post('/auth/reset-password', data),
}

export default api
