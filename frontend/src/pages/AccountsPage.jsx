/**
 * src/pages/AccountsPage.jsx
 * ----------------------------
 * Social Media Accounts & Integrations Dashboard (Milestone 2).
 * Displays all 6 supported social platforms (Facebook, Instagram, LinkedIn,
 * X/Twitter, YouTube, Pinterest) with real OAuth connection and account management.
 */

import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import SocialAccountCard, { PLATFORM_META } from '../components/SocialAccountCard'
import { ToastContainer } from '../components/ui/Toast'
import LoadingState from '../components/ui/LoadingState'
import GlowCard from '../components/ui/GlowCard'
import Button from '../components/ui/Button'
import Modal from '../components/Modal'
import { socialApi } from '../api/socialApi'
import './AccountsPage.css'

const SIX_PLATFORMS = [
  { platform: 'facebook',  label: 'Facebook',     icon: '📘', color: '#1877F2' },
  { platform: 'instagram', label: 'Instagram',    icon: '📸', color: '#E1306C' },
  { platform: 'linkedin',  label: 'LinkedIn',     icon: '💼', color: '#0A66C2' },
  { platform: 'x',         label: 'X (Twitter)',  icon: '𝕏',  color: '#38bdf8' },
  { platform: 'youtube',   label: 'YouTube',      icon: '▶️', color: '#FF0000' },
  { platform: 'pinterest', label: 'Pinterest',    icon: '📌', color: '#E60023' },
]

export default function AccountsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [accounts, setAccounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [toasts, setToasts] = useState([])
  const [connectingPlatform, setConnectingPlatform] = useState(null)
  const [syncingId, setSyncingId] = useState(null)
  const [disconnectingId, setDisconnectingId] = useState(null)
  const [accountToDisconnect, setAccountToDisconnect] = useState(null)

  const addToast = useCallback((msg, type = 'info', duration = 4500) => {
    const id = Date.now().toString()
    setToasts((prev) => [...prev, { id, msg, type, duration }])
  }, [])

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  // Load connected accounts from backend API
  const loadData = useCallback(async () => {
    try {
      const accRes = await socialApi.getAccounts()
      if (accRes.data) {
        setAccounts(Array.isArray(accRes.data) ? accRes.data : [])
      }
    } catch (err) {
      console.error('Failed to load accounts:', err)
      addToast('Failed to load connected social accounts.', 'error')
    } finally {
      setLoading(false)
    }
  }, [addToast])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Handle OAuth redirect return params (?connected=facebook&status=success or ?error=...)
  useEffect(() => {
    const connected = searchParams.get('connected')
    const error = searchParams.get('error')
    if (connected) {
      const label = PLATFORM_META[connected.toLowerCase()]?.label || connected
      addToast(`🎉 ${label} account connected successfully!`, 'success')
      setSearchParams({})
      loadData()
    } else if (error) {
      addToast(`⚠️ ${error}`, 'error')
      setSearchParams({})
      loadData()
    }
  }, [searchParams, setSearchParams, addToast, loadData])

  // Start real OAuth flow for the selected platform
  const handleConnect = async (platformObj) => {
    const platformKey = platformObj.platform || platformObj
    const meta = PLATFORM_META[platformKey] || { label: platformKey }
    setConnectingPlatform(platformKey)

    try {
      const res = await socialApi.getAuthorizeUrl(platformKey)
      const data = res.data

      if (data?.authorization_url) {
        // Redirect browser to provider OAuth consent page
        window.location.href = data.authorization_url
        return
      }

      if (data && !data.is_configured) {
        addToast(
          `⏳ ${data.message || `OAuth credentials for ${meta.label} are not yet configured in backend.`}`,
          'warning'
        )
        return
      }

      addToast(`Could not obtain OAuth authorization URL for ${meta.label}.`, 'error')
    } catch (err) {
      console.error('OAuth authorization error:', err)
      const detail = err.response?.data?.detail || `Failed to initiate OAuth flow for ${meta.label}.`
      addToast(detail, 'error')
    } finally {
      setConnectingPlatform(null)
    }
  }

  // Open confirmation modal to disconnect account
  const handleOpenDisconnectModal = (account) => {
    setAccountToDisconnect(account)
  }

  // Execute disconnect using backend DELETE /social/accounts/{id} API
  const handleConfirmDisconnect = async () => {
    if (!accountToDisconnect) return
    const id = accountToDisconnect.id
    const meta = PLATFORM_META[accountToDisconnect.platform?.toLowerCase()] || { label: 'Social' }

    setDisconnectingId(id)
    try {
      await socialApi.disconnectAccount(id)
      setAccounts((prev) => prev.filter((a) => a.id !== id))
      addToast(`${meta.label} account "${accountToDisconnect.account_name}" disconnected successfully.`, 'info')
      setAccountToDisconnect(null)
    } catch (err) {
      const detail = err.response?.data?.detail || 'Failed to disconnect account.'
      addToast(detail, 'error')
    } finally {
      setDisconnectingId(null)
    }
  }

  // Sync account using backend POST /social/accounts/{id}/sync API
  const handleSync = async (id) => {
    setSyncingId(id)
    try {
      const res = await socialApi.syncAccount(id)
      const d = res.data
      addToast(d.message || 'Account synchronized successfully!', 'success')
      setAccounts((prev) =>
        prev.map((a) =>
          a.id === id
            ? { ...a, last_synced_at: new Date().toISOString(), status: 'connected' }
            : a
        )
      )
    } catch (err) {
      const detail = err.response?.data?.detail || 'Sync failed.'
      addToast(detail, 'error')
    } finally {
      setSyncingId(null)
    }
  }

  const connectedCount = accounts.length

  return (
    <AppShell pageTitle="Social Accounts" pageSubtitle="Connect and manage your channels across all 6 major networks">

        <ToastContainer toasts={toasts} onRemove={removeToast} />

        {loading ? (
          <LoadingState message="Loading social media accounts…" size="lg" />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* ── 6 Platform Cards Section ── */}
            <GlowCard className="accounts-section" hover={false}>
              <div className="section-title-row">
                <div>
                  <h2 className="ds-title">Social Media Platforms ({SIX_PLATFORMS.length})</h2>
                  <p style={{ color: '#94a3b8', fontSize: '13px', marginTop: '4px' }}>
                    Connect your authentic accounts via OAuth to enable one-click publishing and scheduled delivery.
                  </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span
                    style={{
                      background: connectedCount > 0 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(148, 163, 184, 0.15)',
                      color: connectedCount > 0 ? '#34d399' : '#94a3b8',
                      border: `1px solid ${connectedCount > 0 ? 'rgba(16, 185, 129, 0.3)' : 'rgba(148, 163, 184, 0.3)'}`,
                      padding: '4px 12px',
                      borderRadius: '9999px',
                      fontSize: '12px',
                      fontWeight: 600,
                    }}
                  >
                    ● {connectedCount} connected
                  </span>
                </div>
              </div>

              <div className="platforms-grid">
                {SIX_PLATFORMS.map((platform) => {
                  const platformAccounts = accounts.filter(
                    (a) => a.platform?.toLowerCase() === platform.platform.toLowerCase()
                  )

                  // If not connected, render Disconnected platform card with "Connect Account" button
                  if (platformAccounts.length === 0) {
                    return (
                      <SocialAccountCard
                        key={platform.platform}
                        platform={platform}
                        isAvailable={true}
                        onConnect={() => handleConnect(platform)}
                        connectLoading={connectingPlatform === platform.platform}
                      />
                    )
                  }

                  // If connected, render each connected account for this platform
                  return platformAccounts.map((account) => (
                    <SocialAccountCard
                      key={account.id}
                      platform={platform}
                      account={account}
                      isAvailable={false}
                      onSync={handleSync}
                      onDisconnect={handleOpenDisconnectModal}
                      syncLoading={syncingId === account.id}
                      disconnectLoading={disconnectingId === account.id}
                    />
                  ))
                })}
              </div>
            </GlowCard>
          </div>
        )}

        {/* ── Disconnect Confirmation Modal ── */}
        {accountToDisconnect && (
          <Modal
            isOpen={true}
            onClose={() => setAccountToDisconnect(null)}
            title={`Disconnect ${PLATFORM_META[accountToDisconnect.platform?.toLowerCase()]?.label || 'Social'} Account`}
          >
            <div style={{ padding: '8px 0' }}>
              <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: '1.6', marginBottom: '12px' }}>
                Are you sure you want to disconnect{' '}
                <strong>{accountToDisconnect.account_name}</strong>
                {accountToDisconnect.account_username ? ` (@${accountToDisconnect.account_username})` : ''}?
              </p>
              <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: '1.5', marginBottom: '24px' }}>
                This will remove the account from SocialPilot and revoke scheduled post publishing. You can reconnect it via OAuth at any time.
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
    </AppShell>
  )
}
