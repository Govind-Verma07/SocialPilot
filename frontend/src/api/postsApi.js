/**
 * src/api/postsApi.js
 * -------------------
 * API client methods for Phase 1: Content Scheduling Foundation.
 * Communicates with backend endpoints under /api/v1/posts.
 */

import api from './authApi'

export const postsApi = {
  // Retrieve list of posts (optionally filtered by status)
  getPosts: (params = {}) => api.get('/posts', { params }),

  // Retrieve a single post by ID
  getPost: (id) => api.get(`/posts/${id}`),

  // Create a post (scheduled or draft)
  createPost: (data) => api.post('/posts', data),

  // Update an existing post or draft (including DRAFT -> SCHEDULED)
  updatePost: (id, data) => api.put(`/posts/${id}`, data),

  // Delete a post by ID
  deletePost: (id) => api.delete(`/posts/${id}`),

  // Phase 4: Recurring Posts API
  getRecurringRules: (params = {}) => api.get('/recurring-posts', { params }),
  getRecurringRule: (id) => api.get(`/recurring-posts/${id}`),
  createRecurringRule: (data) => api.post('/recurring-posts', data),
  updateRecurringRule: (id, data) => api.put(`/recurring-posts/${id}`, data),
  deleteRecurringRule: (id) => api.delete(`/recurring-posts/${id}`),

  // Phase 5: Manual Publishing API
  publishPost: (id) => api.post(`/posts/${id}/publish`),

  // Phase 9: Publishing Logs & Tracking API
  getPublishingLogs: (id, params = {}) => api.get(`/posts/${id}/publishing-logs`, { params }),
  exportPublishingLogs: (id) => api.get(`/posts/${id}/publishing-logs/export`, { responseType: 'blob' }),
  getRawPublishingLogs: (id) => api.get(`/posts/${id}/publishing-logs/export`, { responseType: 'text' }),

  // Unified Content & Media Storage API
  uploadMedia: (file, usageType = 'single', onUploadProgress) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('usage_type', usageType)
    return api.post('/media/upload', formData, {
      onUploadProgress,
    })
  },
  getMedia: (mediaId) => api.get(`/media/${mediaId}`),
  deleteMedia: (mediaId) => api.delete(`/media/${mediaId}`),
  getPostContent: (id) => api.get(`/posts/${id}/content`),
}

export default postsApi


