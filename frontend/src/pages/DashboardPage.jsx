/**
 * src/pages/DashboardPage.jsx
 * ----------------------------
 * Milestone 1 Dashboard Overview.
 * Shows user profile, active social integrations status, quick stats,
 * and workspace navigation.
 */

import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Sidebar from '../components/Sidebar'
import { socialApi } from '../api/socialApi'
import './DashboardPage.css'

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
    ? user.full_name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
    : 'U'

  const formattedRole = (user?.role || 'content_creator')
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')

  const joinDate = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    : '—'

  const connectedCount = accounts.filter(a => a.status === 'connected').length
  const platformList = accounts.map(a => a.platform).join(', ') || 'None connected'

  const stats = [
    {
      label: 'Connected Channels',
      value: loading ? '…' : connectedCount.toString(),
      icon: '🔗',
      delta: platformList,
      up: connectedCount > 0 ? true : null,
    },
    {
      label: 'Assigned Role',
      value: formattedRole,
      icon: '🛡️',
      delta: 'RBAC Active',
      up: true,
    },
    {
      label: 'Workspace Security',
      value: 'AES-256',
      icon: '🔐',
      delta: 'Tokens Encrypted',
      up: true,
    },
    {
      label: 'Metadata Store',
      value: 'Hybrid',
      icon: '⚡',
      delta: 'PostgreSQL + MongoDB',
      up: true,
    },
  ]

  return (
    <div className="dashboard">
      <div className="orb orb-1" />
      <div className="orb orb-2" />

      {/* Shared Responsive Sidebar */}
      <Sidebar mobileOpen={mobileNav} onCloseMobile={() => setMobileNav(false)} />

      {/* Main Content */}
      <main className="dashboard-main">
        {/* Header */}
        <div className="dashboard-header">
          <div>
            <h1 className="dashboard-greeting">
              Good {getGreeting()},{' '}
              <span className="gradient-text">{user?.full_name?.split(' ')[0] ?? 'there'}</span> 👋
            </h1>
            <p className="dashboard-subtitle">
              Welcome to your SocialPilot management workspace.
            </p>
          </div>
          <div className="header-actions">
            <Link to="/accounts" className="btn btn-primary">
              + Connect Social Account
            </Link>
          </div>
        </div>

        {/* Stats grid */}
        <div className="stats-grid">
          {stats.map((s) => (
            <div key={s.label} className="stat-card glass-card">
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
            </div>
          ))}
        </div>

        {/* Two-column lower section */}
        <div className="dashboard-lower">
          {/* Social Accounts Quick Overview */}
          <div className="dashboard-section glass-card">
            <div className="section-title-row">
              <h2 className="ds-title">Connected Social Channels</h2>
              <Link to="/accounts" className="btn btn-ghost btn-sm">
                Manage all →
              </Link>
            </div>

            {loading ? (
              <p style={{ color: '#94a3b8', padding: '16px 0' }}>Loading social accounts…</p>
            ) : accounts.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '32px 16px', color: '#94a3b8' }}>
                <p style={{ fontSize: '1.2rem', marginBottom: '8px' }}>No accounts connected yet.</p>
                <p style={{ fontSize: '0.875rem', color: '#64748b', marginBottom: '16px' }}>
                  Connect your Facebook, Instagram, LinkedIn, X, YouTube, or Pinterest accounts to get started.
                </p>
                <button
                  onClick={() => navigate('/accounts')}
                  className="btn btn-outline"
                >
                  Connect Your First Account
                </button>
              </div>
            ) : (
              <div className="posts-list">
                {accounts.map((acc) => (
                  <div key={acc.id} className="post-item" style={{ alignItems: 'center', display: 'flex', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ fontSize: '1.5rem' }}>
                        {acc.platform === 'facebook' ? '📘' :
                         acc.platform === 'instagram' ? '📸' :
                         acc.platform === 'linkedin' ? '💼' :
                         acc.platform === 'x' ? '𝕏' :
                         acc.platform === 'youtube' ? '▶️' :
                         acc.platform === 'pinterest' ? '📌' : '🔗'}
                      </span>
                      <div>
                        <div style={{ fontWeight: 600, color: '#f1f5f9' }}>{acc.account_name}</div>
                        <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                          {acc.account_username ? `@${acc.account_username}` : acc.platform}
                        </div>
                      </div>
                    </div>
                    <div>
                      <span
                        className="post-status"
                        style={{
                          background: acc.status === 'connected' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                          color: acc.status === 'connected' ? '#10b981' : '#ef4444',
                          border: `1px solid ${acc.status === 'connected' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                        }}
                      >
                        {acc.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Profile Card */}
          <div className="dashboard-section glass-card">
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
              <Link to="/team" className="btn btn-outline btn-full" style={{ marginTop: '16px', display: 'block', textAlign: 'center' }}>
                Manage Team Members 👥
              </Link>
            </div>
          </div>
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
