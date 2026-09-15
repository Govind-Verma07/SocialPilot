import { getBackendBaseURL } from '../api/authApi'

/**
 * Resolves a media item or URL into a browser-safe, production-ready absolute or blob URL.
 * 
 * - Preserves newly uploaded client-side blob/data URLs.
 * - Anchors relative paths (/api/v1/media/...) to the configured production backend base.
 * - Replaces stale localhost URLs with the production backend base in production mode.
 * - Resolves from preview_url, public_url, download_url, or constructs via media_id.
 */
export const resolveMediaUrl = (itemOrUrl) => {
  if (!itemOrUrl) return ''

  let rawUrl = ''
  let mediaId = ''

  if (typeof itemOrUrl === 'string') {
    rawUrl = itemOrUrl.trim()
  } else if (typeof itemOrUrl === 'object') {
    mediaId = itemOrUrl.media_id || ''
    rawUrl = (
      itemOrUrl.preview_url ||
      itemOrUrl.public_url ||
      itemOrUrl.download_url ||
      (mediaId ? `/api/v1/media/${mediaId}/download` : '')
    )
  }

  if (!rawUrl) return ''

  // 1. Browser-local blob or data URLs (from fresh file selection in composer)
  if (rawUrl.startsWith('blob:') || rawUrl.startsWith('data:')) {
    return rawUrl
  }

  const backendBase = getBackendBaseURL()

  // 2. Already absolute HTTP(S) URL
  if (/^https?:\/\//i.test(rawUrl)) {
    // If on production, replace any stale localhost/127.0.0.1 port 8000 URL with live backend URL
    if (backendBase && !backendBase.includes('localhost') && !backendBase.includes('127.0.0.1')) {
      if (rawUrl.includes('localhost:8000') || rawUrl.includes('127.0.0.1:8000')) {
        return rawUrl.replace(/^https?:\/\/(localhost|127\.0\.0\.1):8000/i, backendBase)
      }
    }
    return rawUrl
  }

  // 3. Relative path (e.g. /api/v1/media/{media_id}/download)
  const cleanPath = rawUrl.startsWith('/') ? rawUrl : `/${rawUrl}`
  return backendBase ? `${backendBase}${cleanPath}` : cleanPath
}

export default resolveMediaUrl
