/**
 * src/api/analyticsApi.js
 * -----------------------
 * API client for Milestone 3: Real Performance Analytics & Reporting.
 * Communicates with backend endpoints under /api/v1/analytics.
 */

import api from './authApi'

export const analyticsApi = {
  // Retrieve content performance analytics (overview, platform breakdown, top posts, daily trend)
  getContentAnalytics: (params = {}) => api.get('/analytics/content', { params }),

  // Retrieve audience & connected accounts analytics
  getAudienceAnalytics: () => api.get('/analytics/audience'),

  // Retrieve campaign performance analytics & ROI
  getCampaignAnalytics: (params = {}) => api.get('/analytics/campaigns', { params }),

  // Side-by-side campaign comparison
  compareCampaigns: (campaignIds) => api.post('/analytics/comparison', { campaign_ids: campaignIds }),

  // Export analytics report (CSV download or JSON)
  exportCsv: (exportType = 'all') =>
    api.get('/analytics/export', {
      params: { format: 'csv', export_type: exportType },
      responseType: 'blob',
    }),

  exportJson: (exportType = 'all') =>
    api.get('/analytics/export', {
      params: { format: 'json', export_type: exportType },
    }),

  // Record or update post metrics
  recordMetric: (data) => api.post('/analytics/metrics', data),

  // On-demand real social media analytics sync from platform APIs
  syncAnalytics: (days = 30) => api.post('/analytics/sync', null, { params: { days } }),

  // Diagnostic connection and analytics permission status for connected platforms
  getDiagnostics: () => api.get('/analytics/diagnostics'),
}

export default analyticsApi
