/**
 * src/api/socialApi.js
 * --------------------
 * Social account management API calls.
 */
import api from './authApi'

export const socialApi = {
  // Platform discovery
  getPlatforms: () => api.get('/social/platforms'),

  // OAuth flows
  getAuthorizeUrl: (platform, teamId = null) => {
    const params = teamId ? `?team_id=${teamId}` : ''
    return api.get(`/social/oauth/${platform}/authorize${params}`)
  },

  // Account CRUD
  getAccounts: (teamId = null) => {
    const params = teamId ? `?team_id=${teamId}` : ''
    return api.get(`/social/accounts${params}`)
  },
  getAccount: (id) => api.get(`/social/accounts/${id}`),
  syncAccount: (id) => api.post(`/social/accounts/${id}/sync`),
  disconnectAccount: (id) => api.delete(`/social/accounts/${id}`),
  getPermissions: (id) => api.get(`/social/accounts/${id}/permissions`),
}

export default socialApi
