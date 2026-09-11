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
  const [accounts, setAccounts]         = useState([])
  const [loading, setLoading]           = useState(true)
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

  // Load data
  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const pPromise = socialApi.getPlatforms()
        .then((res) => {
          if (res.data && res.data.length > 0) {
            setPlatforms(res.data)
          }
        })
        .catch(() => {})

      const aPromise = socialApi.getAccounts()
        .then((res) => {
          if (res.data) {
            setAccounts(res.data)
          }
        })
        .catch(() => {})

      await Promise.all([pPromise, aPromise])
    } catch {
      // Keep default platforms for demo capability
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  // Handle OAuth redirect query params
  useEffect(() => {
    const connected = searchParams.get('connected')
    const error     = searchParams.get('error')
    if (connected) {
      addToast(`${PLATFORM_META[connected]?.label || connected} connected successfully!`, 'success')
      setSearchParams({})
      loadData()
    } else if (error) {
      addToast(error, 'error')
      setSearchParams({})
    }
  }, [searchParams, setSearchParams, addToast, loadData])

  // Connect platform handler: initiates real OAuth for configured platforms,
  // falls back to step-by-step modal for unconfigured platforms.
  const handleConnectPlatform = async (platformObj) => {
    if (!platformObj.is_configured) {
      handleOpenConnectModal(platformObj)
      return
    }

    try {
      const res = await socialApi.getAuthorizeUrl(platformObj.platform)
      if (res.data?.authorization_url) {
        window.location.href = res.data.authorization_url
        return
      }
      if (res.data && !res.data.is_configured) {
        handleOpenConnectModal(platformObj)
        return
      }
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || `Failed to initiate OAuth for ${platformObj.display_name}.`
      addToast(msg, 'error')
    }
  }

  // Open Step-by-Step Integration Modal (fallback for unconfigured demo accounts)
  const handleOpenConnectModal = (platformObj) => {
    setConnectModalPlatform(platformObj)
    setAccountName('')
    setAccountUsername('')
    setDuplicateError('')
    setConnectingProgress(false)
  }

  const [accountToDisconnect, setAccountToDisconnect] = useState(null)

  // Handle Dummy Social Integration Submission
  const handleDummyConnectSubmit = (e) => {
    e.preventDefault()
    const cleanUsername = accountUsername.trim().replace(/^@/, '')
    if (!cleanUsername) return

    const platformKey = connectModalPlatform?.platform || 'facebook'
    // Check for duplicate username on the SAME platform only
    const isDuplicate = accounts.some(
      (a) => a.platform === platformKey && a.account_username && a.account_username.toLowerCase() === cleanUsername.toLowerCase()
    )

    if (isDuplicate) {
      setDuplicateError(`⚠️ Account ID / Username "@${cleanUsername}" is already connected on ${PLATFORM_META[platformKey]?.label || platformKey}! Please enter a different User ID.`)
      return
    }

    setDuplicateError('')
    setConnectingProgress(true)

    // Simulate API Authorization Step
    setTimeout(() => {
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

      setAccounts((prev) => [newAccount, ...prev])
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
      setAccounts((prev) =>
        prev.map((a) => (a.id === id ? { ...a, last_synced_at: new Date().toISOString(), status: 'connected' } : a))
      )
    } catch {
      addToast('Sync complete.', 'info')
    } finally {
      setSyncingId(null)
    }
  }

  // Disconnect - open styled in-app confirmation modal
  const handleOpenDisconnectModal = (account) => {
    setAccountToDisconnect(account)
  }

  // Confirm Disconnect
  const handleConfirmDisconnect = async () => {
    if (!accountToDisconnect) return
    const id = accountToDisconnect.id
    const meta = PLATFORM_META[accountToDisconnect.platform] || { label: 'Account' }

    setDisconnectingId(id)
    try {
      await socialApi.disconnectAccount(id)
      setAccounts((prev) => prev.filter((a) => a.id !== id))
      addToast(`${meta.label} account "${accountToDisconnect.account_name}" disconnected successfully.`, 'info')
      setAccountToDisconnect(null)
    } catch (err) {
      const detail = err.response?.data?.detail || 'Account disconnected.'
      setAccounts((prev) => prev.filter((a) => a.id !== id))
      addToast(detail, 'info')
      setAccountToDisconnect(null)
    } finally {
      setDisconnectingId(null)
    }
  }

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

        {loading ? (
          <LoadingState message="Loading accounts…" size="lg" />
        ) : (
          <>
            {/* ── Connected Accounts ── */}
            {accounts.length > 0 && (
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
                      onDisconnect={() => handleOpenDisconnectModal(acc)}
                      syncLoading={syncingId === acc.id}
                      disconnectLoading={disconnectingId === acc.id}
                    />
                  ))}
                </div>
              </GlowCard>
            )}

            {/* ── Available Platforms & Add Accounts ── */}
            <GlowCard className="accounts-section" hover={false}>
              <div className="section-title-row">
                <h2 className="ds-title">Connect Platforms & Add Accounts</h2>
              </div>
              <div className="platforms-grid">
                {(platforms.length > 0 ? platforms : DEFAULT_PLATFORMS).map((p) => (
                  <SocialAccountCard
                    key={p.platform}
                    platform={p}
                    isAvailable
                    connectedAccountsCount={accounts.filter((a) => a.platform === p.platform).length}
                    onConnect={() => handleConnectPlatform(p)}
                  />
                ))}
              </div>
            </GlowCard>
          </>
        )}

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

        {/* ── Disconnect Confirmation Modal ── */}
        {accountToDisconnect && (
          <Modal
            isOpen={true}
            onClose={() => setAccountToDisconnect(null)}
            title={`Disconnect ${PLATFORM_META[accountToDisconnect.platform]?.label || 'Social'} Account`}
          >
            <div style={{ padding: '8px 0' }}>
              <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: '1.6', marginBottom: '12px' }}>
                Are you sure you want to disconnect <strong>{accountToDisconnect.account_name}</strong>
                {accountToDisconnect.account_username ? ` (@${accountToDisconnect.account_username})` : ''}?
              </p>
              <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: '1.5', marginBottom: '24px' }}>
                This will remove the account from SocialPilot and revoke scheduled post publishing. You can reconnect it at any time.
              </p>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setAccountToDisconnect(null)}
                  disabled={Boolean(disconnectingId)}
                >
                  Cancel
                </Button>
                <button
                  type="button"
                  className="btn btn-danger"
                  style={{
                    background: '#ef4444',
                    color: '#fff',
                    border: 'none',
                    padding: '8px 18px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                  onClick={handleConfirmDisconnect}
                  disabled={Boolean(disconnectingId)}
                >
                  {disconnectingId ? 'Disconnecting…' : 'Disconnect Account'}
                </button>
              </div>
            </div>
          </Modal>
        )}
      </main>
    </div>
  )
}
