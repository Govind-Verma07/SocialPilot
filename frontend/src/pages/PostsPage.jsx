/**
 * src/pages/PostsPage.jsx
 * -----------------------
 * Content Scheduling & Multi-Platform Publishing Engine (Module 3 & 5 from PDF Spec).
 * Supports Text Posts, Images, Videos, Carousels, Stories, Reels across Facebook, Instagram, LinkedIn, X, YouTube, and Pinterest.
 */

import { useState } from 'react'
import Sidebar from '../components/Sidebar'
import Navbar from '../components/Navbar'
import GlowCard from '../components/ui/GlowCard'
import Button from '../components/ui/Button'
import StatusBadge from '../components/ui/StatusBadge'
import EmptyState from '../components/ui/EmptyState'
import './PostsPage.css'

const CONTENT_TYPES = [
  { id: 'text', label: '📝 Text Post', icon: '📝' },
  { id: 'image', label: '📸 Image', icon: '📸' },
  { id: 'video', label: '🎬 Video', icon: '🎬' },
  { id: 'carousel', label: '🎠 Carousel', icon: '🎠' },
  { id: 'story', label: '⚡ Story', icon: '⚡' },
  { id: 'reel', label: '🎞️ Reel', icon: '🎞️' },
]

const PLATFORMS = [
  { id: 'facebook', label: 'Facebook', icon: '📘' },
  { id: 'instagram', label: 'Instagram', icon: '📸' },
  { id: 'linkedin', label: 'LinkedIn', icon: '💼' },
  { id: 'x', label: 'X (Twitter)', icon: '𝕏' },
  { id: 'youtube', label: 'YouTube', icon: '▶️' },
  { id: 'pinterest', label: 'Pinterest', icon: '📌' },
]

const INITIAL_SCHEDULED_POSTS = [
  {
    id: 'post-101',
    caption: '🚀 Product Launch Announcement — SocialPilot 2.0 is live!',
    contentType: 'Carousel',
    platforms: ['facebook', 'linkedin', 'x'],
    scheduledAt: '2026-09-02T10:00:00',
    status: 'scheduled',
  },
  {
    id: 'post-102',
    caption: 'Behind the scenes: How our AI scheduler powers 10x engagement 💡',
    contentType: 'Reel',
    platforms: ['instagram', 'youtube'],
    scheduledAt: '2026-09-03T15:30:00',
    status: 'scheduled',
  },
  {
    id: 'post-103',
    caption: '5 Essential Social Media Strategies for SMB Founders in 2026',
    contentType: 'Text Post',
    platforms: ['linkedin', 'facebook'],
    scheduledAt: '2026-09-01T09:00:00',
    status: 'published',
  },
]

export default function PostsPage() {
  const [mobileNav, setMobileNav] = useState(false)
  const [activeTab, setActiveTab] = useState('queue') // 'queue', 'calendar', 'drafts', 'recurring'
  const [showComposer, setShowComposer] = useState(false)

  // Form State
  const [contentType, setContentType] = useState('text')
  const [selectedPlatforms, setSelectedPlatforms] = useState(['facebook', 'instagram'])
  const [caption, setCaption] = useState('')
  const [scheduleDate, setScheduleDate] = useState('')
  const [scheduledPosts, setScheduledPosts] = useState(INITIAL_SCHEDULED_POSTS)
  const [drafts, setDrafts] = useState([
    { id: 'draft-1', caption: 'Draft: Weekly Analytics Highlights video summary...', contentType: 'Video', platforms: ['youtube'] }
  ])

  const togglePlatform = (id) => {
    setSelectedPlatforms((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    )
  }

  const handleCreatePost = (e) => {
    e.preventDefault()
    if (!caption.trim()) return

    const newPost = {
      id: `post-${Date.now()}`,
      caption: caption.trim(),
      contentType: CONTENT_TYPES.find((t) => t.id === contentType)?.label.split(' ')[1] || 'Post',
      platforms: [...selectedPlatforms],
      scheduledAt: scheduleDate || new Date().toISOString(),
      status: scheduleDate ? 'scheduled' : 'published',
    }

    setScheduledPosts([newPost, ...scheduledPosts])
    setCaption('')
    setShowComposer(false)
  }

  const handleSaveDraft = () => {
    if (!caption.trim()) return
    setDrafts([{ id: `draft-${Date.now()}`, caption, contentType, platforms: selectedPlatforms }, ...drafts])
    setCaption('')
    setShowComposer(false)
  }

  return (
    <div className="app-layout body-bg">
      <Sidebar mobileOpen={mobileNav} onCloseMobile={() => setMobileNav(false)} />

      <main className="app-main">
        <Navbar
          pageTitle="Content Scheduling & Publishing Engine"
          pageSubtitle="Create, schedule, and automate posts across all 6 social media platforms"
          mobileMenuLabel="Open menu"
          onMobileMenu={() => setMobileNav(true)}
        />

        {/* Header Action Bar */}
        <div className="posts-header-row">
          <div className="posts-tabs">
            <button
              className={`posts-tab-btn ${activeTab === 'queue' ? 'active' : ''}`}
              onClick={() => setActiveTab('queue')}
            >
              📋 Scheduled Queue ({scheduledPosts.length})
            </button>
            <button
              className={`posts-tab-btn ${activeTab === 'calendar' ? 'active' : ''}`}
              onClick={() => setActiveTab('calendar')}
            >
              📅 Publishing Calendar
            </button>
            <button
              className={`posts-tab-btn ${activeTab === 'drafts' ? 'active' : ''}`}
              onClick={() => setActiveTab('drafts')}
            >
              📝 Drafts ({drafts.length})
            </button>
            <button
              className={`posts-tab-btn ${activeTab === 'recurring' ? 'active' : ''}`}
              onClick={() => setActiveTab('recurring')}
            >
              🔄 Recurring Schedules
            </button>
          </div>

          <Button variant="primary" onClick={() => setShowComposer(!showComposer)}>
            {showComposer ? '✕ Close Composer' : '+ Create & Schedule Post'}
          </Button>
        </div>

        {/* Composer Modal / Section */}
        {showComposer && (
          <GlowCard className="composer-card" hover>
            <h2 className="section-heading">Create New Social Post</h2>

            <form onSubmit={handleCreatePost} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Content Type Selector */}
              <div>
                <label className="form-label" style={{ marginBottom: '8px', display: 'block' }}>
                  Select Content Format
                </label>
                <div className="content-type-selector">
                  {CONTENT_TYPES.map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      className={`content-type-chip ${contentType === t.id ? 'selected' : ''}`}
                      onClick={() => setContentType(t.id)}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Target Platforms with Select All option */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <label className="form-label">Target Social Media Accounts / Platforms</label>
                  <button
                    type="button"
                    onClick={() => {
                      if (selectedPlatforms.length === PLATFORMS.length) {
                        setSelectedPlatforms([])
                      } else {
                        setSelectedPlatforms(PLATFORMS.map((p) => p.id))
                      }
                    }}
                    style={{
                      background: 'rgba(124, 58, 237, 0.15)',
                      border: '1px solid rgba(124, 58, 237, 0.4)',
                      color: '#c084fc',
                      padding: '4px 12px',
                      borderRadius: '8px',
                      fontSize: '12px',
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    {selectedPlatforms.length === PLATFORMS.length ? '✓ Unselect All' : '☐ Select All (All 6 Platforms)'}
                  </button>
                </div>
                <div className="platform-checkboxes">
                  {PLATFORMS.map((p) => {
                    const checked = selectedPlatforms.includes(p.id)
                    return (
                      <button
                        key={p.id}
                        type="button"
                        className={`platform-check-btn ${checked ? 'checked' : ''}`}
                        onClick={() => togglePlatform(p.id)}
                      >
                        <span>{p.icon}</span>
                        <span>{p.label}</span>
                        <span>{checked ? '✓' : '+'}</span>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Caption / Content Input */}
              <div className="form-group">
                <label className="form-label">Post Caption / Message</label>
                <textarea
                  className="form-input post-textarea"
                  value={caption}
                  onChange={(e) => setCaption(e.target.value)}
                  placeholder="Write your post caption, hashtags, and links..."
                  required
                />
              </div>

              {/* Schedule Date Time */}
              <div className="form-group">
                <label className="form-label">Publishing Date & Time</label>
                <input
                  type="datetime-local"
                  className="form-input"
                  value={scheduleDate}
                  onChange={(e) => setScheduleDate(e.target.value)}
                />
              </div>

              <div className="form-actions" style={{ marginTop: '8px' }}>
                <Button type="button" variant="ghost" onClick={handleSaveDraft}>
                  Save as Draft 💾
                </Button>
                <Button type="submit" variant="primary">
                  Schedule Post 🚀
                </Button>
              </div>
            </form>
          </GlowCard>
        )}

        {/* TAB 1: SCHEDULED QUEUE */}
        {activeTab === 'queue' && (
          <div className="posts-grid-list">
            {scheduledPosts.map((post) => (
              <GlowCard key={post.id} className="post-item-card" hover>
                <div className="post-item-left">
                  <div className="post-type-icon">
                    {CONTENT_TYPES.find((c) => c.id === post.contentType.toLowerCase())?.icon || '📝'}
                  </div>
                  <div className="post-info-meta">
                    <div className="post-caption">{post.caption}</div>
                    <div className="post-sub-meta">
                      <span>Format: <strong>{post.contentType}</strong></span>
                      <span>•</span>
                      <span>Platforms: {post.platforms.map((p) => PLATFORMS.find((pl) => pl.id === p)?.icon).join(' ')}</span>
                      <span>•</span>
                      <span>Scheduled: {new Date(post.scheduledAt).toLocaleString()}</span>
                    </div>
                  </div>
                </div>
                <StatusBadge
                  status={post.status === 'published' ? 'success' : post.status === 'scheduled' ? 'warning' : 'info'}
                  label={post.status}
                  showDot
                />
              </GlowCard>
            ))}
          </div>
        )}

        {/* TAB 2: CALENDAR VIEW */}
        {activeTab === 'calendar' && (
          <GlowCard style={{ padding: '24px' }}>
            <h3 className="section-heading" style={{ marginBottom: '16px' }}>September 2026 — Publishing Calendar</h3>
            <div className="calendar-grid">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
                <div key={d} style={{ fontSize: '12px', fontWeight: 700, color: '#94a3b8', textAlign: 'center', paddingBottom: '8px' }}>
                  {d}
                </div>
              ))}
              {Array.from({ length: 30 }, (_, i) => i + 1).map((day) => {
                const hasPost = day === 2 || day === 3 || day === 5
                return (
                  <div key={day} className="calendar-day-box">
                    <div className="calendar-day-num">{day}</div>
                    {hasPost && <div className="calendar-post-badge">Post @ 10:00 AM</div>}
                  </div>
                )
              })}
            </div>
          </GlowCard>
        )}

        {/* TAB 3: DRAFTS */}
        {activeTab === 'drafts' && (
          <div>
            {drafts.length === 0 ? (
              <EmptyState
                icon="📝"
                title="No saved drafts"
                description="Save draft posts while composing to edit and schedule them later."
                size="md"
              />
            ) : (
              <div className="posts-grid-list">
                {drafts.map((d) => (
                  <GlowCard key={d.id} className="post-item-card" hover>
                    <div className="post-item-left">
                      <div className="post-type-icon">📝</div>
                      <div className="post-info-meta">
                        <div className="post-caption">{d.caption}</div>
                        <div className="post-sub-meta">Draft saved in workspace</div>
                      </div>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => setShowComposer(true)}>
                      Edit & Schedule →
                    </Button>
                  </GlowCard>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: RECURRING POSTS */}
        {activeTab === 'recurring' && (
          <GlowCard style={{ padding: '24px' }}>
            <h3 className="section-heading">Automated & Recurring Scheduling Rules</h3>
            <p className="section-subheading">Set recurring post intervals to automatically keep your channels active.</p>
            <div className="post-item-card" style={{ background: 'rgba(255,255,255,0.02)', borderRadius: '12px' }}>
              <div>
                <strong>Weekly Tips & Industry News Round-up</strong>
                <div style={{ fontSize: '12px', color: '#94a3b8' }}>Repeats every Monday at 09:00 AM on LinkedIn & X</div>
              </div>
              <StatusBadge status="success" label="Active Recurring Rule" showDot />
            </div>
          </GlowCard>
        )}
      </main>
    </div>
  )
}
