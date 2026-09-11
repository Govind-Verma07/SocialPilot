/**
 * src/pages/DashboardPage.jsx
 * Milestone 1 Dashboard Overview.
 * Shows user profile, active social integrations status, quick stats,
 * and workspace navigation.
 */

import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Sidebar from '../components/Sidebar'
import Navbar from '../components/Navbar'
import Button from '../components/ui/Button'
import GlowCard from '../components/ui/GlowCard'
import StatusBadge from '../components/ui/StatusBadge'
import LoadingState from '../components/ui/LoadingState'
import EmptyState from '../components/ui/EmptyState'
import { socialApi } from '../api/socialApi'
import './DashboardPage.css'

const PLATFORM_ICONS = {
  facebook:  '📘',
  instagram: '📸',
  linkedin:  '💼',
  x:         '𝕏',
  youtube:   '▶️',
  pinterest: '📌',
}

export default function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [accounts, setAccounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [mobileNav, setMobileNav] = useState(false)

  useEffect(() => {
    async function loadAccounts() {
      try {
        const res = await socialApi.getAccounts()
        setAccounts(res.data)
      } catch (err) {
        console.error('Failed to load accounts for dashboard overview:', err)
      } finally {
        setLoading(false)
      }
    }
    loadAccounts()
  }, [])

  const initials = user?.full_name
    ? user.full_name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
    : 'U'

  const formattedRole = (user?.role || 'content_creator')
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')

  const joinDate = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    : '—'

  const connectedCount = accounts.filter((a) => a.status === 'connected').length
  const platformList = accounts.map((a) => a.platform).join(', ') || 'None connected'

  const stats = [
    {
      label: 'Connected Channels',
      value: loading ? '…' : connectedCount.toString(),
      icon: '🔗',
      delta: platformList,
      up: connectedCount > 0 ? true : null,
    },
    {
      label: 'Scheduled Posts Queue',
      value: '3 Pending',
      icon: '📝',
      delta: 'Next post in 2h',
      up: true,
    },
    {
      label: 'Active Campaigns',
      value: '2 Active',
      icon: '🎯',
      delta: '+240% Target ROI',
      up: true,
    },
    {
      label: 'Total Impressions & Reach',
      value: '184.5K',
      icon: '📊',
      delta: '▲ +18.4% this month',
      up: true,
    },
  ]

  const greeting = getGreeting()

  return (
    <div className="dashboard body-bg">
      <Sidebar mobileOpen={mobileNav} onCloseMobile={() => setMobileNav(false)} />

      <main className="dashboard-main">
        <Navbar
          pageTitle="Dashboard Overview"
          pageSubtitle="Centralized Social Media Scheduler & Campaign Management Platform"
          mobileMenuLabel="Open menu"
          onMobileMenu={() => setMobileNav(true)}
        />

        {/* Greeting */}
        <div className="dashboard-greeting-section">
          <h1 className="dashboard-greeting">
            Good {greeting},{' '}
            <span className="gradient-text">{user?.full_name?.split(' ')[0] ?? 'there'}</span> 👋
          </h1>
          <p className="dashboard-subtitle">
            Welcome to your SocialPilot multi-platform publishing and campaign workspace.
          </p>
        </div>

        {/* Quick action bar */}
        <div className="dashboard-quick-action" style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <Button variant="primary" onClick={() => navigate('/posts')}>
            + Compose & Schedule Post 📝
          </Button>
          <Button variant="outline" onClick={() => navigate('/campaigns')}>
            + Launch New Campaign 🎯
          </Button>
          <Button variant="ghost" onClick={() => navigate('/accounts')}>
            + Connect Social Channel 🔗
          </Button>
        </div>

        {/* Stats grid */}
        <div className="stats-grid">
          {stats.map((s) => (
            <GlowCard key={s.label} className="stat-card" hover>
              <div className="stat-top">
                <span className="stat-icon">{s.icon}</span>
                <span
                  className={`stat-delta ${
                    s.up === true ? 'up' : s.up === false ? 'down' : 'neutral'
                  }`}
                >
                  {s.delta}
                </span>
              </div>
              <div className="stat-value">{s.value}</div>
              <div className="stat-label">{s.label}</div>
            </GlowCard>
          ))}
        </div>

        {/* Lower section */}
        <div className="dashboard-lower">
          {/* Social Accounts Quick Overview */}
          <GlowCard className="dashboard-section" hover>
            <div className="section-title-row">
              <h2 className="ds-title">Connected Social Channels</h2>
              <Link to="/accounts" className="btn btn-ghost btn-sm">
                Manage all →
              </Link>
            </div>

            {loading ? (
              <LoadingState message="Loading social accounts…" size="sm" />
            ) : accounts.length === 0 ? (
              <EmptyState
                icon="🔗"
                title="No accounts connected yet."
                description="Connect your Facebook, Instagram, LinkedIn, X, YouTube, or Pinterest accounts to get started."
                actionLabel="Connect Your First Account"
                onAction={() => navigate('/accounts')}
                size="md"
              />
            ) : (
              <div className="posts-list">
                {accounts.map((acc) => {
                  const Icon = PLATFORM_ICONS[acc.platform] || '🔗'
                  return (
                    <div key={acc.id} className="account-quick-row">
                      <div className="account-quick-left">
                        <span className="account-quick-icon">{Icon}</span>
                        <div className="account-quick-info">
                          <span className="account-quick-name">{acc.account_name}</span>
                          <span className="account-quick-username">
                            {acc.account_username ? `@${acc.account_username}` : acc.platform}
                          </span>
                        </div>
                      </div>
                      <StatusBadge status={acc.status === 'connected' ? 'success' : 'error'} label={acc.status} showDot />
                    </div>
                  )
                })}
              </div>
            )}
          </GlowCard>

          {/* Profile Card */}
          <GlowCard className="dashboard-section profile-card" hover>
            <div className="section-title-row">
              <h2 className="ds-title">Your Profile</h2>
              <Link to="/profile" className="btn btn-ghost btn-sm">
                Edit profile →
              </Link>
            </div>
            <div className="profile-card-content">
              <div className="profile-avatar-lg">{initials}</div>
              <h3 className="profile-name">{user?.full_name}</h3>
              <p className="profile-email">{user?.email}</p>
              <div className="profile-meta">
                <div className="profile-meta-item">
                  <span className="meta-label">Role</span>
                  <span className="meta-value status-active">● {formattedRole}</span>
                </div>
                <div className="profile-meta-item">
                  <span className="meta-label">Member since</span>
                  <span className="meta-value">{joinDate}</span>
                </div>
                <div className="profile-meta-item">
                  <span className="meta-label">Account status</span>
                  <span className="meta-value status-active">● Active</span>
                </div>
              </div>
              <Link
                to="/team"
                className="btn btn-outline btn-full"
                style={{ marginTop: '16px', display: 'block', textAlign: 'center' }}
              >
                Manage Team Members 👥
              </Link>
            </div>
          </GlowCard>
        </div>
      </main>
    </div>
  )
}

function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'morning'
  if (h < 17) return 'afternoon'
  return 'evening'
}
