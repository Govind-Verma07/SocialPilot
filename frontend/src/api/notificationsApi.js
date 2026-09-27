/**
 * src/api/notificationsApi.js
 * ---------------------------
 * Notification Module API client.
 * All requests use the shared axios instance (JWT injected automatically).
 */

import api from './authApi'

const notificationsApi = {
  /** Get all notifications (paginated, filterable) */
  list: (params = {}) => api.get('/notifications', { params }),

  /** Get unread notification count (for badge) */
  unreadCount: () => api.get('/notifications/unread-count'),

  /** Mark a single notification as read */
  markRead: (id) => api.patch(`/notifications/${id}/read`),

  /** Mark all notifications as read */
  markAllRead: () => api.patch('/notifications/read-all'),

  /** Delete a notification */
  delete: (id) => api.delete(`/notifications/${id}`),

  /** Get user notification preferences */
  getPreferences: () => api.get('/notifications/preferences'),

  /** Update user notification preferences */
  updatePreferences: (data) => api.put('/notifications/preferences', data),

  /** Send authenticated SMTP test email */
  sendTestEmail: (data = {}) => api.post('/notifications/test-email', data),
}

export default notificationsApi
