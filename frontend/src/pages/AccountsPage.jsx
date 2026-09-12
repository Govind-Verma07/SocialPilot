/**
 * src/pages/AccountsPage.jsx
 * ----------------------------
 * Social Account Management Dashboard with Step-by-Step Dummy Connection Flow.
 * Demonstrates platform selection, username/ID integration, and duplicate ID prevention.
 */

import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import Navbar from '../components/Navbar'
import SocialAccountCard from '../components/SocialAccountCard'
import { ToastContainer } from '../components/ui/Toast'
import LoadingState from '../components/ui/LoadingState'
import GlowCard from '../components/ui/GlowCard'
import Button from '../components/ui/Button'
import Modal from '../components/Modal'
import { socialApi } from '../api/socialApi'
import './AccountsPage.css'

const PLATFORM_META = {
  facebook:  { icon: '📘', color: '#1877F2', label: 'Facebook Pages' },
  instagram: { icon: '📸', color: '#E1306C', label: 'Instagram Business' },
  linkedin:  { icon: '💼', color: '#0A66C2', label: 'LinkedIn Company' },
  x:         { icon: '𝕏',  color: '#38bdf8', label: 'X (Twitter)' },
  youtube:   { icon: '▶️', color: '#FF0000', label: 'YouTube Channel' },
  pinterest: { icon: '📌', color: '#E60023', label: 'Pinterest Board' },
}

const DEFAULT_PLATFORMS = [
  { platform: 'facebook', display_name: 'Facebook Pages', is_configured: true },
  { platform: 'instagram', display_name: 'Instagram Business', is_configured: true },
  { platform: 'linkedin', display_name: 'LinkedIn Company', is_configured: true },
  { platform: 'x', display_name: 'X (Twitter)', is_configured: true },
  { platform: 'youtube', display_name: 'YouTube Channel', is_configured: true },
  { platform: 'pinterest', display_name: 'Pinterest Board', is_configured: true },
]

export default function AccountsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [platforms, setPlatforms]       = useState(DEFAULT_PLATFORMS)
  
  // Instant load from sessionStorage cache if available
  const [accounts, setAccounts]         = useState(() => {
    try {
      const cached = sessionStorage.getItem('sp_cached_accounts')
      return cached ? JSON.parse(cached) : []
    } catch {
      return []
    }
  })
  const [loading, setLoading]           = useState(() => {
    try {
      const cached = sessionStorage.getItem('sp_cached_accounts')
      return !cached
    } catch {
      return true
    }
  })
  const [toasts, setToasts]             = useState([])
  const [mobileNav, setMobileNav]       = useState(false)
  const [syncingId, setSyncingId]       = useState(null)
  const [disconnectingId, setDisconnectingId] = useState(null)

  // Dummy Integration Modal State
  const [connectModalPlatform, setConnectModalPlatform] = useState(null)
  const [accountName, setAccountName] = useState('')
  const [accountUsername, setAccountUsername] = useState('')
  const [duplicateError, setDuplicateError] = useState('')
  const [connectingProgress, setConnectingProgress] = useState(false)

  const addToast = useCallback((msg, type = 'info', duration = 4000) => {
    const id = Date.now().toString()
    setToasts((prev) => [...prev, { id, msg, type, duration }])
  }, [])

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  // Handle OAuth redirect query params
  useEffect(() => {
    const connected = searchParams.get('connected')
    const error     = searchParams.get('error')
    if (connected) {
      addToast(`${PLATFORM_META[connected]?.label || connected} connected successfully!`, 'success')
      setSearchParams({})
    } else if (error) {
      addToast(error, 'error')
      setSearchParams({})
    }
  }, [searchParams, setSearchParams, addToast])

  // Load data asynchronously without locking the UI
  const loadData = useCallback(async () => {
    // 1. Fetch platforms in background (DEFAULT_PLATFORMS already available)
    socialApi.getPlatforms()
      .then((res) => {
        if (res.data && res.data.length > 0) {
          setPlatforms(res.data)
        }
      })
      .catch(() => {})

    // 2. Fetch fresh accounts
    try {
      const accRes = await socialApi.getAccounts()
      if (accRes.data) {
        setAccounts(accRes.data)
        try {
          sessionStorage.setItem('sp_cached_accounts', JSON.stringify(accRes.data))
        } catch {}
      }
    } catch (err) {
      console.warn('Could not refresh accounts:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  // Open Step-by-Step Integration Modal
  const handleOpenConnectModal = (platformObj) => {
    setConnectModalPlatform(platformObj)
    setAccountName('')
    setAccountUsername('')
    setDuplicateError('')
    setConnectingProgress(false)
  }

  // Handle Dummy Social Integration Submission
  const handleDummyConnectSubmit = (e) => {
    e.preventDefault()
    const cleanUsername = accountUsername.trim().replace(/^@/, '')
    if (!cleanUsername) return

    // 1. Check for Duplicate Username / User ID across connected accounts
    const isDuplicate = accounts.some(
      (a) => a.account_username && a.account_username.toLowerCase() === cleanUsername.toLowerCase()
    )

    if (isDuplicate) {
      setDuplicateError(`⚠️ Account ID / Username "@${cleanUsername}" already connected! Please enter a different User ID.`)
      return
    }

    setDuplicateError('')
    setConnectingProgress(true)

    // Simulate API Authorization Step
    setTimeout(() => {
      const platformKey = connectModalPlatform?.platform || 'facebook'
      const meta = PLATFORM_META[platformKey] || { label: 'Social' }

      const newAccount = {
        id: `dummy-${Date.now()}`,
        platform: platformKey,
        account_name: accountName.trim() || `${meta.label} Account`,
        account_username: cleanUsername,
        status: 'connected',
        last_synced_at: new Date().toISOString(),
        permissions: [
          { id: '1', permission: 'read_insights', granted: true },
          { id: '2', permission: 'publish_content', granted: true },
        ],
      }

      setAccounts((prev) => {
        const updated = [newAccount, ...prev]
        try { sessionStorage.setItem('sp_cached_accounts', JSON.stringify(updated)) } catch {}
        return updated
      })
      setConnectingProgress(false)
      setConnectModalPlatform(null)
      addToast(`✅ ${meta.label} account "@${cleanUsername}" connected successfully!`, 'success')
    }, 1200)
  }

  // Sync
  const handleSync = async (id) => {
    setSyncingId(id)
    try {
      await socialApi.syncAccount(id).catch(() => {})
      addToast('Account synchronized successfully!', 'success')
      setAccounts((prev) => {
        const updated = prev.map((a) => (a.id === id ? { ...a, last_synced_at: new Date().toISOString(), status: 'connected' } : a))
        try { sessionStorage.setItem('sp_cached_accounts', JSON.stringify(updated)) } catch {}
        return updated
      })
    } catch {
      addToast('Sync complete.', 'info')
    } finally {
      setSyncingId(null)
    }
  }

  // Disconnect
  const handleDisconnect = async (id) => {
    const account = accounts.find((a) => a.id === id)
    const meta = PLATFORM_META[account?.platform] || { label: 'account' }
    if (!window.confirm(`Disconnect ${meta.label} account "${account?.account_name}"?`)) return

    setDisconnectingId(id)
    try {
      await socialApi.disconnectAccount(id).catch(() => {})
      setAccounts((prev) => {
        const updated = prev.filter((a) => a.id !== id)
        try { sessionStorage.setItem('sp_cached_accounts', JSON.stringify(updated)) } catch {}
        return updated
      })
      addToast(`${meta.label} account disconnected.`, 'info')
    } catch {
      setAccounts((prev) => {
        const updated = prev.filter((a) => a.id !== id)
        try { sessionStorage.setItem('sp_cached_accounts', JSON.stringify(updated)) } catch {}
        return updated
      })
      addToast('Account disconnected.', 'info')
    } finally {
      setDisconnectingId(null)
    }
  }

  // Platforms not yet connected
  const connectedPlatforms  = new Set(accounts.map((a) => a.platform))
  const unconnectedPlatforms = platforms.filter((p) => !connectedPlatforms.has(p.platform))

  return (
    <div className="app-layout body-bg">
      <Sidebar mobileOpen={mobileNav} onCloseMobile={() => setMobileNav(false)} />

      <main className="app-main">
        <Navbar
          pageTitle="Social Accounts & Integrations"
          pageSubtitle="Connect and manage your social media profiles across all platforms."
          mobileMenuLabel="Open menu"
          onMobileMenu={() => setMobileNav(true)}
        />

        <ToastContainer toasts={toasts} onRemove={removeToast} />

        {/* ── Connected Accounts ── */}
        {loading && accounts.length === 0 ? (
          <GlowCard className="accounts-section" hover={false}>
            <div className="section-title-row">
              <h2 className="ds-title">Connected Accounts</h2>
            </div>
            <LoadingState message="Loading your accounts…" size="sm" />
          </GlowCard>
        ) : (
          accounts.length > 0 && (
            <GlowCard className="accounts-section" hover={false}>
              <div className="section-title-row">
                <h2 className="ds-title">Connected Accounts ({accounts.length})</h2>
              </div>
              <div className="accounts-list">
                {accounts.map((acc) => (
                  <SocialAccountCard
                    key={acc.id}
                    account={acc}
                    onSync={handleSync}
                    onDisconnect={handleDisconnect}
                    syncLoading={syncingId === acc.id}
                    disconnectLoading={disconnectingId === acc.id}
                  />
                ))}
              </div>
            </GlowCard>
          )
        )}

        {/* ── Available Platforms (Always visible immediately) ── */}
        <GlowCard className="accounts-section" hover={false}>
          <div className="section-title-row">
            <h2 className="ds-title">Connect a Platform</h2>
          </div>
          <div className="platforms-grid">
            {(unconnectedPlatforms.length > 0 ? unconnectedPlatforms : DEFAULT_PLATFORMS).map((p) => (
              <SocialAccountCard
                key={p.platform}
                platform={p}
                isAvailable
                onConnect={() => handleOpenConnectModal(p)}
              />
            ))}
          </div>
        </GlowCard>

        {/* ── Step-by-Step Dummy Connection Modal ── */}
        {connectModalPlatform && (
          <Modal
            isOpen={true}
            onClose={() => setConnectModalPlatform(null)}
            title={`Connect ${PLATFORM_META[connectModalPlatform.platform]?.label || connectModalPlatform.display_name}`}
          >
            <form onSubmit={handleDummyConnectSubmit} className="auth-form">
              <p style={{ fontSize: '13px', color: '#94a3b8', marginBottom: '12px' }}>
                Enter your social account credentials / User ID to simulate step-by-step account integration.
              </p>

              {duplicateError && (
                <div className="alert alert-error" style={{ marginBottom: '12px' }}>
                  <span>⚠️</span>
                  <span>{duplicateError}</span>
                </div>
              )}

              <div className="form-group">
                <label className="form-label">Account Display Name</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Govind Verma Official Page"
                  value={accountName}
                  onChange={(e) => {
                    setAccountName(e.target.value)
                    setDuplicateError('')
                  }}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">User Name / User ID</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. @govindverma or user_99210"
                  value={accountUsername}
                  onChange={(e) => {
                    setAccountUsername(e.target.value)
                    setDuplicateError('')
                  }}
                  required
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '16px' }}>
                <Button type="button" variant="ghost" onClick={() => setConnectModalPlatform(null)}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" disabled={connectingProgress}>
                  {connectingProgress ? 'Connecting to API…' : 'Verify & Connect Account 🚀'}
                </Button>
              </div>
            </form>
          </Modal>
        )}
      </main>
    </div>
  )
}
