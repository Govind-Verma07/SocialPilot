/**
 * src/pages/AccountsPage.jsx
 * --------------------------
 * Social account management dashboard.
 * - Lists all connected accounts with status badges
 * - Per-platform connect buttons (opens OAuth flow or shows "Awaiting credentials" notice)
 * - Sync and Disconnect per account
 * - Handles OAuth redirect ?connected= / ?error= query params
 */

import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import { socialApi } from '../api/socialApi'

// ── Platform meta ─────────────────────────────────────────────────────────────
const PLATFORM_META = {
  facebook:  { icon: '📘', color: '#1877F2', label: 'Facebook' },
  instagram: { icon: '📸', color: '#E1306C', label: 'Instagram' },
  linkedin:  { icon: '💼', color: '#0A66C2', label: 'LinkedIn' },
  x:         { icon: '𝕏',  color: '#000000', label: 'X (Twitter)' },
  youtube:   { icon: '▶️', color: '#FF0000', label: 'YouTube' },
  pinterest: { icon: '📌', color: '#E60023', label: 'Pinterest' },
}

const STATUS_BADGE = {
  connected:     { label: 'Connected',     bg: '#16a34a22', color: '#16a34a', dot: '#16a34a' },
  token_expired: { label: 'Token Expired', bg: '#dc262622', color: '#dc2626', dot: '#dc2626' },
  error:         { label: 'Error',         bg: '#dc262622', color: '#dc2626', dot: '#dc2626' },
  disconnected:  { label: 'Disconnected',  bg: '#6b728022', color: '#6b7280', dot: '#6b7280' },
}

// ── Platform card for unconnected platforms ───────────────────────────────────
function PlatformCard({ platform, onConnect }) {
  const meta = PLATFORM_META[platform.platform] || { icon: '🔗', color: '#6366f1', label: platform.display_name }
  return (
    <div style={{
      background: 'rgba(255,255,255,0.04)',
      border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 16,
      padding: '20px 24px',
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      transition: 'all 0.2s',
    }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = meta.color + '88'; e.currentTarget.style.background = meta.color + '0a' }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)'; e.currentTarget.style.background = 'rgba(255,255,255,0.04)' }}
    >
      <span style={{ fontSize: 32 }}>{meta.icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, fontSize: 15, color: '#f1f5f9' }}>{meta.label}</div>
        {!platform.is_configured && (
          <div style={{ fontSize: 12, color: '#f59e0b', marginTop: 2 }}>
            ⏳ Awaiting platform credentials
          </div>
        )}
      </div>
      <button
        onClick={() => onConnect(platform)}
        disabled={!platform.is_configured}
        style={{
          background: platform.is_configured ? meta.color : '#374151',
          color: '#fff',
          border: 'none',
          borderRadius: 8,
          padding: '8px 18px',
          fontWeight: 600,
          fontSize: 13,
          cursor: platform.is_configured ? 'pointer' : 'not-allowed',
          opacity: platform.is_configured ? 1 : 0.5,
          transition: 'all 0.2s',
        }}
      >
        {platform.is_configured ? 'Connect' : 'Coming Soon'}
      </button>
    </div>
  )
}

// ── Connected account card ────────────────────────────────────────────────────
function AccountCard({ account, onSync, onDisconnect }) {
  const meta = PLATFORM_META[account.platform] || { icon: '🔗', color: '#6366f1', label: account.platform }
  const badge = STATUS_BADGE[account.status] || STATUS_BADGE.disconnected
  const [syncing, setSyncing] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)

  const handleSync = async () => {
    setSyncing(true)
    try { await onSync(account.id) } finally { setSyncing(false) }
  }

  const handleDisconnect = async () => {
    if (!window.confirm(`Disconnect ${meta.label} account "${account.account_name}"?`)) return
    setDisconnecting(true)
    try { await onDisconnect(account.id) } finally { setDisconnecting(false) }
  }

  return (
    <div style={{
      background: 'rgba(255,255,255,0.05)',
      border: `1px solid ${meta.color}33`,
      borderRadius: 16,
      padding: '20px 24px',
      display: 'flex',
      alignItems: 'center',
      gap: 16,
    }}>
      {/* Avatar / icon */}
      <div style={{
        width: 48, height: 48, borderRadius: '50%',
        background: meta.color + '22',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 24, flexShrink: 0,
        border: `2px solid ${meta.color}44`,
      }}>
        {account.profile_picture_url
          ? <img src={account.profile_picture_url} alt="" style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }} />
          : meta.icon}
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 700, fontSize: 15, color: '#f1f5f9', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {account.account_name}
          </span>
          {/* Status badge */}
          <span style={{
            background: badge.bg, color: badge.color,
            borderRadius: 20, padding: '2px 10px', fontSize: 11, fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: badge.dot, display: 'inline-block' }} />
            {badge.label}
          </span>
        </div>
        <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>
          {account.account_username && `@${account.account_username} · `}{meta.label}
        </div>
        {account.last_synced_at && (
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
            Last synced: {new Date(account.last_synced_at).toLocaleString()}
          </div>
        )}
        {/* Permissions */}
        {account.permissions?.length > 0 && (
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 6 }}>
            {account.permissions.filter(p => p.granted).map(p => (
              <span key={p.id} style={{
                background: 'rgba(99,102,241,0.15)', color: '#a5b4fc',
                borderRadius: 4, padding: '2px 6px', fontSize: 10, fontWeight: 500,
              }}>
                {p.permission}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
        <button
          onClick={handleSync}
          disabled={syncing}
          title="Sync account"
          style={{
            background: 'rgba(99,102,241,0.15)', color: '#a5b4fc',
            border: '1px solid rgba(99,102,241,0.3)',
            borderRadius: 8, padding: '7px 14px', fontSize: 13, fontWeight: 600,
            cursor: syncing ? 'not-allowed' : 'pointer', opacity: syncing ? 0.6 : 1,
            transition: 'all 0.2s',
          }}
        >
          {syncing ? '⟳' : '↻ Sync'}
        </button>
        <button
          onClick={handleDisconnect}
          disabled={disconnecting}
          title="Disconnect"
          style={{
            background: 'rgba(239,68,68,0.1)', color: '#f87171',
            border: '1px solid rgba(239,68,68,0.2)',
            borderRadius: 8, padding: '7px 14px', fontSize: 13, fontWeight: 600,
            cursor: disconnecting ? 'not-allowed' : 'pointer', opacity: disconnecting ? 0.6 : 1,
            transition: 'all 0.2s',
          }}
        >
          ✕ Disconnect
        </button>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function AccountsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [platforms, setPlatforms]       = useState([])
  const [accounts, setAccounts]         = useState([])
  const [loading, setLoading]           = useState(true)
  const [toast, setToast]               = useState(null)

  // Show a dismissible toast
  const showToast = useCallback((msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }, [])

  // Handle OAuth redirect query params (?connected=facebook&status=success or ?error=...)
  useEffect(() => {
    const connected = searchParams.get('connected')
    const error     = searchParams.get('error')
    if (connected) {
      showToast(`✅ ${PLATFORM_META[connected]?.label || connected} connected successfully!`, 'success')
      setSearchParams({})
    } else if (error) {
      showToast(`❌ ${error}`, 'error')
      setSearchParams({})
    }
  }, [searchParams, setSearchParams, showToast])

  // Load data
  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [platRes, accRes] = await Promise.all([
        socialApi.getPlatforms(),
        socialApi.getAccounts(),
      ])
      setPlatforms(platRes.data)
      setAccounts(accRes.data)
    } catch (err) {
      showToast('Failed to load account data.', 'error')
    } finally {
      setLoading(false)
    }
  }, [showToast])

  useEffect(() => { loadData() }, [loadData])

  // Connect: get auth URL then redirect
  const handleConnect = async (platform) => {
    if (!platform.is_configured) return
    try {
      const res = await socialApi.getAuthorizeUrl(platform.platform)
      const data = res.data
      if (!data.is_configured || !data.authorization_url) {
        showToast(`⏳ ${data.message || 'Platform credentials not configured.'}`, 'info')
        return
      }
      window.location.href = data.authorization_url
    } catch {
      showToast('Failed to start OAuth flow.', 'error')
    }
  }

  // Sync
  const handleSync = async (id) => {
    try {
      const res = await socialApi.syncAccount(id)
      const d = res.data
      if (d.status === 'success') {
        showToast(`✅ ${d.message}`, 'success')
      } else {
        showToast(`⚠️ ${d.message}`, 'warning')
      }
      await loadData()
    } catch {
      showToast('Sync failed.', 'error')
    }
  }

  // Disconnect
  const handleDisconnect = async (id) => {
    try {
      const res = await socialApi.disconnectAccount(id)
      showToast(`✅ ${res.data.message}`, 'success')
      await loadData()
    } catch {
      showToast('Failed to disconnect account.', 'error')
    }
  }

  // Platforms not yet connected
  const connectedPlatforms  = new Set(accounts.map(a => a.platform))
  const unconnectedPlatforms = platforms.filter(p => !connectedPlatforms.has(p.platform))

  const toastColors = {
    success: { bg: '#16a34a22', border: '#16a34a44', color: '#4ade80' },
    error:   { bg: '#dc262622', border: '#dc262644', color: '#f87171' },
    info:    { bg: '#0ea5e922', border: '#0ea5e944', color: '#38bdf8' },
    warning: { bg: '#f59e0b22', border: '#f59e0b44', color: '#fbbf24' },
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#0b0f1a', fontFamily: "'Inter', sans-serif", color: '#e2e8f0' }}>
      <Sidebar />

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', top: 24, right: 24, zIndex: 9999,
          background: toastColors[toast.type]?.bg || toastColors.info.bg,
          border: `1px solid ${toastColors[toast.type]?.border || toastColors.info.border}`,
          color: toastColors[toast.type]?.color || toastColors.info.color,
          borderRadius: 12, padding: '12px 20px', fontWeight: 600, fontSize: 14,
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          animation: 'fadeIn 0.2s ease',
        }}>
          {toast.msg}
        </div>
      )}

      <main style={{ flex: 1, padding: '40px 48px', overflowY: 'auto' }}>
        {/* Header */}
        <div style={{ marginBottom: 36 }}>
          <h1 style={{ fontSize: 28, fontWeight: 800, background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', margin: 0 }}>
            Social Accounts
          </h1>
          <p style={{ color: '#94a3b8', marginTop: 6, fontSize: 15 }}>
            Connect and manage your social media profiles across all platforms.
          </p>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 80, color: '#6366f1', fontSize: 18 }}>
            Loading accounts…
          </div>
        ) : (
          <>
            {/* ── Connected Accounts ──────────────────────────── */}
            {accounts.length > 0 && (
              <section style={{ marginBottom: 48 }}>
                <h2 style={{ fontSize: 16, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 16 }}>
                  Connected Accounts ({accounts.length})
                </h2>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {accounts.map(acc => (
                    <AccountCard
                      key={acc.id}
                      account={acc}
                      onSync={handleSync}
                      onDisconnect={handleDisconnect}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* ── Available Platforms ─────────────────────────── */}
            {unconnectedPlatforms.length > 0 && (
              <section>
                <h2 style={{ fontSize: 16, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 16 }}>
                  Connect a Platform
                </h2>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
                  {unconnectedPlatforms.map(p => (
                    <PlatformCard key={p.platform} platform={p} onConnect={handleConnect} />
                  ))}
                </div>
              </section>
            )}

            {/* Empty state */}
            {accounts.length === 0 && unconnectedPlatforms.length === 0 && (
              <div style={{ textAlign: 'center', padding: 80, color: '#6b7280' }}>
                No platforms available. Check your backend configuration.
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}
