/**
 * src/api/teamApi.js
 * ------------------
 * Axios API calls for Team / Workspace management.
 */

import api from './authApi'

export const teamApi = {
  getTeams:         ()                     => api.get('/teams'),
  createTeam:       (data)                 => api.post('/teams', data),
  getTeam:          (teamId)               => api.get(`/teams/${teamId}`),
  updateTeam:       (teamId, data)         => api.patch(`/teams/${teamId}`, data),
  addMember:        (teamId, data)         => api.post(`/teams/${teamId}/members`, data),
  updateMemberRole: (teamId, memberId, data) => api.patch(`/teams/${teamId}/members/${memberId}`, data),
  removeMember:     (teamId, memberId)     => api.delete(`/teams/${teamId}/members/${memberId}`),
}

export default teamApi
