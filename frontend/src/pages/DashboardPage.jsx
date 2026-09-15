/**
 * src/pages/DashboardPage.jsx
 * Premium SaaS Dashboard — wired to real backend endpoints.
 * Uses new AppShell with collapsible sidebar + Navbar.
 */

import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import AppShell from '../components/AppShell'
import Button from '../components/ui/Button'
import GlowCard from '../components/ui/GlowCard'
import StatusBadge from '../components/ui/StatusBadge'
import LoadingState from '../components/ui/LoadingState'
import EmptyState from '../components/ui/EmptyState'
import { socialApi } from '../api/socialApi'
import { postsApi } from '../api/postsApi'
import {
  Link2,
  Clock,
  Rocket,
  FileText,
  SquarePen,
  Megaphone,
  CalendarDays,
  ArrowRight,
  TrendingUp,
} from 'lucide-react'
import './DashboardPage.css'

const PLATFORM_META = {
  facebook:  { icon: '📘', color: '#1877f2' },
  instagram: { icon: '📸', color: '#e1306c' },
  linkedin:  { icon: '💼', color: '#0a66c2' },
  x:         { icon: '𝕏', color: '#e7e9ea' },
  youtube:   { icon: '▶️', color: '#ff0000' },
  pinterest: { icon: '📌', color: '#e60023' },
}

function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

export default function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [accounts, setAccounts] = useState([])
  const [scheduledPosts, setScheduledPosts] = useState([])
  const [publishedPosts, setPublishedPosts] = useState([])
  const [draftPosts, setDraftPosts] = useState([])
  const [recentPosts, setRecentPosts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadDashboardData() {
      setLoading(true)
      try {
        const [accRes, schedRes, pubRes, draftRes, recentRes] = await Promise.allSettled([
          socialApi.getAccounts(),
          postsApi.getPosts({ status: 'scheduled' }),
          postsApi.getPosts({ status: 'published' }),
          postsApi.getPosts({ status: 'draft' }),
          postsApi.getPosts({ limit: 8 }),
        ])

        if (accRes.status === 'fulfilled') {
          setAccounts(Array.isArray(accRes.value.data) ? accRes.value.data : [])
        }
        if (schedRes.status === 'fulfilled') {
          setScheduledPosts(schedRes.value.data?.items || [])
        }
        if (pubRes.status === 'fulfilled') {
          setPublishedPosts(pubRes.value.data?.items || [])
        }
        if (draftRes.status === 'fulfilled') {
          setDraftPosts(draftRes.value.data?.items || [])
        }
        if (recentRes.status === 'fulfilled') {
          setRecentPosts(recentRes.value.data?.items || [])
        }
      } catch (err) {
        console.error('Failed to load dashboard backend data:', err)
      } finally {
        setLoading(false)
      }
    }

    loadDashboardData()
  }, [])

  const firstName = user?.full_name?.split(' ')[0] ?? 'there'
  const initials = user?.full_name
    ? user.full_name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
    : 'U'
  const formattedRole = (user?.role || 'content_creator')
    .split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
  const joinDate = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    : '—'

  const connectedCount = accounts.filter((a) => a.status === 'connected').length

  const nextScheduled = scheduledPosts.length > 0 && scheduledPosts[0].scheduled_at
    ? new Date(scheduledPosts[0].scheduled_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : null

  const kpis = [
    {
      label: 'Connected Channels',
      value: loading ? '—' : connectedCount,
      sub: loading ? '' : `${accounts.length} total accounts`,
      icon: Link2,
      color: 'var(--clr-info)',
      colorBg: 'var(--clr-info-bg)',
      path: '/accounts',
    },
    {
      label: 'Scheduled Posts',
      value: loading ? '—' : scheduledPosts.length,
      sub: nextScheduled ? `Next: ${nextScheduled}` : 'No upcoming posts',
      icon: Clock,
      color: 'var(--clr-warning)',
      colorBg: 'var(--clr-warning-bg)',
      path: '/posts?tab=queue',
    },
    {
      label: 'Published Posts',
      value: loading ? '—' : publishedPosts.length,
      sub: publishedPosts.length > 0 ? 'Live across channels' : 'No posts published yet',
      icon: Rocket,
      color: 'var(--clr-success)',
      colorBg: 'var(--clr-success-bg)',
      path: '/posts?tab=queue',
    },
    {
      label: 'Saved Drafts',
      value: loading ? '—' : draftPosts.length,
      sub: draftPosts.length > 0 ? 'Ready for scheduling' : 'No drafts saved',
      icon: FileText,
      color: 'hsl(var(--primary))',
      colorBg: 'hsl(var(--primary) / 0.1)',
      path: '/posts?tab=drafts',
    },
  ]

  return (
    <AppShell pageTitle="Dashboard">
      <div className="db-page">
        {/* ── Greeting ─────────────────────────────── */}
        <div className="db-greeting-row">
          <div>
            <h1 className="db-greeting">
              {getGreeting()}, <span className="gradient-text">{firstName}</span> 👋
            </h1>
            <p className="db-greeting-sub">
              Plan, create, publish and grow your social presence from one place.
            </p>
          </div>
          <div className="db-quick-actions">
            <Button
              variant="primary"
              icon={<SquarePen size={15} />}
              onClick={() => navigate('/posts?tab=create')}
              id="dashboard-create-post"
            >
              Create Post
            </Button>
            <Button
              variant="outline"
              icon={<Megaphone size={15} />}
              onClick={() => navigate('/campaigns')}
              id="dashboard-campaign"
            >
              Campaign
            </Button>
            <Button
              variant="ghost"
              icon={<CalendarDays size={15} />}
              onClick={() => navigate('/posts?tab=calendar')}
              id="dashboard-calendar"
            >
              Calendar
            </Button>
          </div>
        </div>

        {/* ── KPI Cards ────────────────────────────── */}
        <div className="db-kpi-grid">
          {kpis.map((kpi) => {
            const Icon = kpi.icon
            return (
              <GlowCard
                key={kpi.label}
                className="db-kpi-card"
                hover
                onClick={() => kpi.path && navigate(kpi.path)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && kpi.path && navigate(kpi.path)}
                style={{ cursor: 'pointer' }}
                title={`View ${kpi.label}`}
              >
                <div className="db-kpi-top">
                  <span className="db-kpi-label">{kpi.label}</span>
                  <span className="db-kpi-icon" style={{ background: kpi.colorBg, color: kpi.color }}>
                    <Icon size={16} />
                  </span>
                </div>
                <div className="db-kpi-value">{kpi.value}</div>
                <div className="db-kpi-sub">{kpi.sub}</div>
              </GlowCard>
            )
          })}
        </div>

        {/* ── Main Content ─────────────────────────── */}
        <div className="db-lower">
          {/* Left column */}
          <div className="db-left-col">
            {/* Recent Post Activity */}
            <GlowCard className="db-section" hover={false}>
              <div className="section-title-row">
                <div>
                  <h2 className="section-heading">Recent Post Activity</h2>
                  <p className="section-subheading" style={{ margin: 0 }}>Your latest posts across all platforms</p>
                </div>
                <Link to="/posts" className="db-view-link">
                  View all <ArrowRight size={13} />
                </Link>
              </div>

              {loading ? (
                <LoadingState message="Loading recent activity…" size="sm" />
              ) : recentPosts.length === 0 ? (
                <EmptyState
                  icon="📝"
                  title="No posts yet"
                  description="Schedule your first post to see real-time delivery and publishing tracking here."
                  actionLabel="Create your first post"
                  onAction={() => navigate('/posts?tab=create')}
                  size="sm"
                />
              ) : (
                <div className="db-posts-list">
                  {recentPosts.map((post) => {
                    const statusVal = post.status?.toLowerCase()
                    const dateDisplay = post.published_at
                      ? `Published ${new Date(post.published_at).toLocaleDateString()}`
                      : post.scheduled_at
                      ? `Scheduled ${new Date(post.scheduled_at).toLocaleDateString()}`
                      : 'Draft'

                    const platforms = post.social_accounts?.map((sa) => sa.platform) || []

                    return (
                      <div
                        key={post.id}
                        className="db-post-row"
                        onClick={() => navigate('/posts')}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => e.key === 'Enter' && navigate('/posts')}
                      >
                        <div className="db-post-left">
                          <div className="db-post-icon">
                            {statusVal === 'published' ? '✅' : statusVal === 'failed' ? '❌' : '📄'}
                          </div>
                          <div className="db-post-info">
                            <span className="db-post-caption">
                              {post.content
                                ? (post.content.length > 60 ? `${post.content.slice(0, 60)}…` : post.content)
                                : 'Untitled Post'}
                            </span>
                            <span className="db-post-meta">
                              {dateDisplay}
                              {platforms.length > 0 && (
                                <span className="db-post-platforms">
                                  {platforms.slice(0, 3).map((p) => (
                                    <span key={p} className="db-platform-chip" title={p}>
                                      {PLATFORM_META[p]?.icon || '🔗'}
                                    </span>
                                  ))}
                                  {platforms.length > 3 && <span className="db-platform-chip">+{platforms.length - 3}</span>}
                                </span>
                              )}
                            </span>
                          </div>
                        </div>
                        <StatusBadge status={statusVal || 'draft'} showDot />
                      </div>
                    )
                  })}
                </div>
              )}
            </GlowCard>

            {/* Connected Channels */}
            <GlowCard className="db-section" hover={false}>
              <div className="section-title-row">
                <div>
                  <h2 className="section-heading">Connected Social Channels</h2>
                  <p className="section-subheading" style={{ margin: 0 }}>
                    {connectedCount} of {accounts.length} accounts active
                  </p>
                </div>
                <Link to="/accounts" className="db-view-link">
                  Manage <ArrowRight size={13} />
                </Link>
              </div>

              {loading ? (
                <LoadingState message="Loading accounts…" size="sm" />
              ) : accounts.length === 0 ? (
                <EmptyState
                  icon="🔗"
                  title="No accounts connected yet"
                  description="Connect your social platforms to start publishing across channels."
                  actionLabel="Connect your first account"
                  onAction={() => navigate('/accounts')}
                  size="sm"
                />
              ) : (
                <div className="db-accounts-grid">
                  {accounts.map((acc) => {
                    const meta = PLATFORM_META[acc.platform] || { icon: '🔗', color: '#666' }
                    return (
                      <div key={acc.id} className="db-account-chip">
                        <span className="db-account-chip-icon">{meta.icon}</span>
                        <div className="db-account-chip-info">
                          <span className="db-account-chip-name">{acc.account_name}</span>
                          <span className="db-account-chip-handle">
                            {acc.account_username ? `@${acc.account_username}` : acc.platform}
                          </span>
                        </div>
                        <StatusBadge
                          status={acc.status === 'connected' ? 'success' : 'error'}
                          label={acc.status}
                          showDot
                        />
                      </div>
                    )
                  })}
                </div>
              )}
            </GlowCard>
          </div>

          {/* Right column — Profile Card */}
          <div className="db-right-col">
            <GlowCard className="db-profile-card" hover={false}>
              <h2 className="section-heading" style={{ marginBottom: 16 }}>Your Profile</h2>
              <div className="db-profile-inner">
                <div className="db-profile-avatar">{initials}</div>
                <h3 className="db-profile-name">{user?.full_name}</h3>
                <p className="db-profile-email">{user?.email}</p>
                <div className="db-profile-meta">
                  <div className="db-meta-row">
                    <span className="db-meta-label">Role</span>
                    <span className="db-meta-val" style={{ color: 'var(--clr-success)' }}>● {formattedRole}</span>
                  </div>
                  <div className="db-meta-row">
                    <span className="db-meta-label">Member since</span>
                    <span className="db-meta-val">{joinDate}</span>
                  </div>
                  <div className="db-meta-row">
                    <span className="db-meta-label">Status</span>
                    <span className="db-meta-val" style={{ color: 'var(--clr-success)' }}>● Active</span>
                  </div>
                  <div className="db-meta-row">
                    <span className="db-meta-label">Channels</span>
                    <span className="db-meta-val">{connectedCount} connected</span>
                  </div>
                </div>
                <div className="db-profile-actions">
                  <Link to="/profile" className="btn btn-outline btn-full btn-sm">
                    Edit Profile
                  </Link>
                  <Link to="/team" className="btn btn-ghost btn-full btn-sm">
                    Manage Team
                  </Link>
                </div>
              </div>
            </GlowCard>

            {/* Quick Stats */}
            <GlowCard className="db-section" hover={false}>
              <h2 className="section-heading" style={{ marginBottom: 12 }}>
                <TrendingUp size={15} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                Activity Summary
              </h2>
              <div className="db-activity-list">
                <div className="db-activity-row">
                  <span className="db-activity-label">Total Posts</span>
                  <span className="db-activity-val">{loading ? '—' : recentPosts.length}</span>
                </div>
                <div className="db-activity-row">
                  <span className="db-activity-label">Published</span>
                  <span className="db-activity-val text-success">{loading ? '—' : publishedPosts.length}</span>
                </div>
                <div className="db-activity-row">
                  <span className="db-activity-label">Scheduled</span>
                  <span className="db-activity-val" style={{ color: 'var(--clr-warning)' }}>{loading ? '—' : scheduledPosts.length}</span>
                </div>
                <div className="db-activity-row">
                  <span className="db-activity-label">Drafts</span>
                  <span className="db-activity-val text-muted">{loading ? '—' : draftPosts.length}</span>
                </div>
              </div>
            </GlowCard>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
