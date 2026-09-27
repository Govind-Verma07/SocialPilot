/**
 * src/api/campaignsApi.js
 * -----------------------
 * API client for Milestone 3: Campaign Management & Tracking.
 * Communicates with backend endpoints under /api/v1/campaigns.
 */

import api from './authApi'

export const campaignsApi = {
  // Retrieve list of campaigns with optional filters (status, platform, search, page, page_size)
  getCampaigns: (params = {}) => api.get('/campaigns', { params }),

  // Retrieve single campaign by ID with full tracking metrics
  getCampaign: (id) => api.get(`/campaigns/${id}`),

  // Create a new campaign
  createCampaign: (data) => api.post('/campaigns', data),

  // Update existing campaign
  updateCampaign: (id, data) => api.put(`/campaigns/${id}`, data),

  // Delete campaign
  deleteCampaign: (id) => api.delete(`/campaigns/${id}`),

  // Attach posts to campaign
  attachPosts: (campaignId, postIds) => api.post(`/campaigns/${campaignId}/posts`, { post_ids: postIds }),

  // Remove post from campaign
  detachPost: (campaignId, postId) => api.delete(`/campaigns/${campaignId}/posts/${postId}`),

  // Retrieve all posts attached to a campaign
  getCampaignPosts: (campaignId) => api.get(`/campaigns/${campaignId}/posts`),
}

export default campaignsApi
