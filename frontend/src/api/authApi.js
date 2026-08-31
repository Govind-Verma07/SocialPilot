/**
 * src/api/authApi.js
 * ------------------
 * Axios instance pre-configured with the API base URL.
 * Request interceptor automatically attaches the JWT Bearer token.
 * Response interceptor clears localStorage on 401 (token expired / invalid).
 */

import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL}/api/v1`
  : '/api/v1'

const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
})

// ── Request: inject Bearer token ────────────────────────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('sp_access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
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
    }
    return Promise.reject(error)
  }
)

// ── Auth & User endpoints ───────────────────────────────────────────────────
export const authApi = {
  register:       (data) => api.post('/auth/register', data),
  login:          (data) => api.post('/auth/login', data),
  me:             ()     => api.get('/auth/me'),
  logout:         ()     => api.post('/auth/logout'),
  updateProfile:  (data) => api.patch('/users/me', data),
  getSettings:    ()     => api.get('/users/me/settings'),
  updateSettings: (data) => api.put('/users/me/settings', data),
}

export default api
