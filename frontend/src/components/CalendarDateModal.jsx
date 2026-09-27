/**
 * src/components/CalendarDateModal.jsx
 * Reusable modal for displaying all scheduled, published, or draft posts on a selected date.
 */

import React, { useMemo } from 'react'
import Modal from './Modal'
import Button from './ui/Button'

export default function CalendarDateModal({
  isOpen,
  onClose,
  date,
  posts = [],
  platformMeta = {},
  onSelectPost,
  onViewInQueue,
  onPublishNow,
  publishingPostId,
  onQuickSchedule,
}) {
  const formattedDateTitle = useMemo(() => {
    if (!date) return ''
    const d = date instanceof Date ? date : new Date(date)
    return d.toLocaleDateString(undefined, {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    })
  }, [date])

  const stats = useMemo(() => {
    const published = posts.filter(
      (p) => (p.status || '').toLowerCase() === 'published' || (p.status || '').toLowerCase() === 'completed' || Boolean(p.published_at)
    ).length
    const scheduled = posts.filter(
      (p) => (p.status || '').toLowerCase() === 'scheduled' || (p.status || '').toLowerCase() === 'publishing'
    ).length
    const failed = posts.filter((p) => (p.status || '').toLowerCase() === 'failed').length
    const draft = posts.filter((p) => (p.status || '').toLowerCase() === 'draft').length
    return { published, scheduled, failed, draft, total: posts.length }
  }, [posts])

  // Helper for status badge styling
  const getStatusBadge = (post) => {
    const rawStatus = (post.status || '').toLowerCase()
    if (rawStatus === 'published' || rawStatus === 'completed' || Boolean(post.published_at)) {
      return {
        label: 'Published',
        className: 'status-published',
        dotColor: '#10b981',
      }
    }
    if (rawStatus === 'publishing') {
      return {
        label: 'Publishing...',
        className: 'status-publishing',
        dotColor: '#3b82f6',
      }
    }
    if (rawStatus === 'failed') {
      return {
        label: 'Failed',
        className: 'status-failed',
        dotColor: '#ef4444',
      }
    }
    if (rawStatus === 'draft') {
      return {
        label: 'Draft',
        className: 'status-draft',
        dotColor: '#94a3b8',
      }
    }
    return {
      label: 'Scheduled',
      className: 'status-scheduled',
      dotColor: '#f59e0b',
    }
  }

  // Helper for time formatting
  const formatPostTime = (post) => {
    const dateToUse = post.scheduled_at || post.published_at
    if (!dateToUse) return 'No time set'
    return new Date(dateToUse).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    })
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="lg"
      title={null}
    >
      <div className="calendar-modal-container">
        {/* Custom Modal Header */}
        <div className="calendar-modal-header">
          <div className="calendar-modal-header-text">
            <div className="calendar-modal-badge">
              📅 Date View
            </div>
            <h3 className="calendar-modal-title">{formattedDateTitle}</h3>
            <div className="calendar-modal-stats">
              <span className="stat-item total">{stats.total} {stats.total === 1 ? 'post' : 'posts'}</span>
              {stats.scheduled > 0 && (
                <span className="stat-item scheduled">
                  • <span className="stat-dot" style={{ backgroundColor: '#f59e0b' }} /> {stats.scheduled} scheduled
                </span>
              )}
              {stats.published > 0 && (
                <span className="stat-item published">
                  • <span className="stat-dot" style={{ backgroundColor: '#10b981' }} /> {stats.published} published
                </span>
              )}
              {stats.failed > 0 && (
                <span className="stat-item failed">
                  • <span className="stat-dot" style={{ backgroundColor: '#ef4444' }} /> {stats.failed} failed
                </span>
              )}
              {stats.draft > 0 && (
                <span className="stat-item draft">
                  • <span className="stat-dot" style={{ backgroundColor: '#94a3b8' }} /> {stats.draft} draft
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Scrollable Post List */}
        <div className="calendar-modal-post-list">
          {posts.length === 0 ? (
            <div className="calendar-modal-empty">
              <span>📅</span>
              <p>No posts scheduled or published on this date.</p>
            </div>
          ) : (
            posts.map((post) => {
              const statusInfo = getStatusBadge(post)
              const timeStr = formatPostTime(post)
              const isPublishing = publishingPostId === post.id

              return (
                <div
                  key={post.id}
                  className={`calendar-modal-card ${statusInfo.className}`}
                  onClick={() => onSelectPost && onSelectPost(post)}
                >
                  {/* Top Bar: Time, Status, Platforms */}
                  <div className="calendar-modal-card-top">
                    <div className="calendar-modal-card-time-group">
                      <span className="time-indicator">🕒 {timeStr}</span>
                      {post.recurring_rule_id && (
                        <span className="recurring-chip" title="Recurring Post">🔄 Recurring</span>
                      )}
                      <span className={`calendar-modal-status-badge ${statusInfo.className}`}>
                        <span
                          className="status-dot"
                          style={{ backgroundColor: statusInfo.dotColor }}
                        />
                        {statusInfo.label}
                      </span>
                    </div>

                    {/* Target Platforms */}
                    <div className="calendar-modal-platforms">
                      {post.social_accounts && post.social_accounts.length > 0 ? (
                        post.social_accounts.map((sa) => {
                          const meta = platformMeta[sa.platform?.toLowerCase()] || {
                            icon: '📱',
                            label: sa.platform,
                          }
                          return (
                            <span
                              key={sa.id}
                              className="platform-chip"
                              title={`${meta.label}: ${sa.account_name || sa.account_username || ''}`}
                            >
                              <span className="platform-icon">{meta.icon}</span>
                              <span className="platform-name">
                                {sa.account_name || sa.account_username || meta.label}
                              </span>
                            </span>
                          )
                        })
                      ) : (
                        <span className="no-platforms-label">No accounts</span>
                      )}
                    </div>
                  </div>

                  {/* Caption Content */}
                  <div className="calendar-modal-caption">
                    {post.content ? (
                      post.content
                    ) : (
                      <em style={{ color: '#64748b' }}>(Untitled post caption)</em>
                    )}
                  </div>

                  {/* Bottom Meta & Quick Action Buttons */}
                  <div className="calendar-modal-card-bottom">
                    <div className="calendar-modal-type-tag">
                      Format: <strong>{(post.post_type || 'TEXT').toUpperCase()}</strong>
                    </div>

                    <div
                      className="calendar-modal-card-actions"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {/* Publish Now for scheduled/failed posts */}
                      {onPublishNow &&
                        ['scheduled', 'failed'].includes((post.status || '').toLowerCase()) && (
                          <button
                            type="button"
                            className="btn-modal-action-publish"
                            disabled={isPublishing}
                            onClick={() => onPublishNow(post)}
                            title="Publish immediately across connected social accounts"
                          >
                            {isPublishing ? 'Publishing...' : '🚀 Publish Now'}
                          </button>
                        )}

                      {/* View Details */}
                      {onSelectPost && (
                        <button
                          type="button"
                          className="btn-modal-action-subtle"
                          onClick={() => onSelectPost(post)}
                          title="Open full post details"
                        >
                          🔍 Details
                        </button>
                      )}

                      {/* View in Queue */}
                      {onViewInQueue && (
                        <button
                          type="button"
                          className="btn-modal-action-subtle"
                          onClick={() => {
                            onClose()
                            onViewInQueue(post.id)
                          }}
                          title="Highlight in Scheduled Posts Queue"
                        >
                          📋 View in Queue
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>

        {/* Modal Footer */}
        <div className="calendar-modal-footer">
          {onQuickSchedule && date && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                onClose()
                onQuickSchedule(date)
              }}
            >
              + Schedule Post on This Date
            </Button>
          )}
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={onClose}
            style={{ marginLeft: 'auto' }}
          >
            Close
          </Button>
        </div>
      </div>
    </Modal>
  )
}
