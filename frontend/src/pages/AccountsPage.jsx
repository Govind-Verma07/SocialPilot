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
import { Plus, RefreshCw, Unlink } from 'lucide-react'
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

              <div className="platforms-dynamic-grid">
                {SIX_PLATFORMS.map((platform) => {
                  const platformAccounts = accounts.filter(
                    (a) => a.platform?.toLowerCase() === platform.platform.toLowerCase()
                  )
                  const count = platformAccounts.length
                  const isConnected = count > 0
                  const isConnecting = connectingPlatform === platform.platform

                  return (
                    <div
                      key={platform.platform}
                      className={`platform-panel ${isConnected ? 'has-accounts' : 'no-accounts'}`}
                      id={`platform-group-${platform.platform}`}
                      style={{ '--platform-color': platform.color }}
                    >
                      {/* Panel Header */}
                      <div className="platform-panel-header">
                        <div className="platform-panel-brand">
                          <span
                            className="platform-panel-icon"
                            style={{
                              background: `${platform.color}15`,
                              borderColor: `${platform.color}35`,
                            }}
                          >
                            {platform.icon}
                          </span>
                          <div>
                            <h3 className="platform-panel-name">{platform.label}</h3>
                            <span className={`platform-panel-badge ${isConnected ? 'connected' : 'empty'}`}>
                              {isConnected ? `● ${count} ${count === 1 ? 'account' : 'accounts'}` : '○ Not connected'}
                            </span>
                          </div>
                        </div>

                        <button
                          type="button"
                          id={`connect-${platform.platform}-btn`}
                          className={`btn-panel-action ${isConnected ? 'btn-panel-add' : 'btn-panel-connect'}`}
                          style={!isConnected ? { background: platform.color } : {}}
                          onClick={() => handleConnect(platform)}
                          disabled={isConnecting}
                          title={isConnected ? `Connect another ${platform.label} account` : `Connect ${platform.label}`}
                        >
                          {isConnecting ? (
                            <>
                              <RefreshCw size={13} className="sp-spin" />
                              <span>Connecting…</span>
                            </>
                          ) : (
                            <>
                              <Plus size={14} />
                              <span>{isConnected ? '+ Add' : 'Connect'}</span>
                            </>
                          )}
                        </button>
                      </div>

                      {/* Panel Content / Accounts */}
                      <div className="platform-panel-content">
                        {isConnected ? (
                          <div className="platform-panel-accounts-list">
                            {platformAccounts.map((account) => {
                              const status = account.status || 'connected'
                              const isOk = status === 'connected'
                              const isSyncing = syncingId === account.id
                              const isDisconnecting = disconnectingId === account.id
                              const formattedDate = account.last_synced_at
                                ? new Date(account.last_synced_at).toLocaleDateString(undefined, {
                                    month: 'short',
                                    day: 'numeric',
                                    hour: '2-digit',
                                    minute: '2-digit',
                                  })
                                : null

                              return (
                                <div
                                  key={account.id}
                                  className="platform-account-row"
                                  id={`account-card-${account.id}`}
                                >
                                  <div className="account-row-info">
                                    <div
                                      className="account-row-avatar-wrap"
                                      style={{ borderColor: `${platform.color}55` }}
                                    >
                                      {account.profile_picture_url ? (
                                        <img
                                          src={account.profile_picture_url}
                                          alt={account.account_name}
                                          className="account-row-avatar"
                                        />
                                      ) : (
                                        <div
                                          className="account-row-avatar-fallback"
                                          style={{ background: platform.color }}
                                        >
                                          {(account.account_name || platform.label).charAt(0).toUpperCase()}
                                        </div>
                                      )}
                                      <span className={`account-status-dot ${isOk ? 'ok' : 'err'}`} />
                                    </div>

                                    <div className="account-row-text">
                                      <div className="account-row-name-row">
                                        <span className="account-row-name" title={account.account_name}>
                                          {account.account_name || platform.label}
                                        </span>
                                        <span className={`account-status-pill ${isOk ? 'ok' : 'err'}`}>
                                          {isOk ? 'Connected' : status}
                                        </span>
                                      </div>
                                      <span
                                        className="account-row-handle"
                                        title={account.account_username || account.platform_account_id}
                                      >
                                        {account.account_username
                                          ? `@${account.account_username}`
                                          : account.platform_account_id
                                          ? `ID: ${account.platform_account_id}`
                                          : platform.label}
                                      </span>
                                      {formattedDate && (
                                        <span className="account-row-sync-time">
                                          Synced: {formattedDate}
                                        </span>
                                      )}
                                    </div>
                                  </div>

                                  <div className="account-row-actions">
                                    <button
                                      type="button"
                                      className="btn-account-sync"
                                      onClick={() => handleSync(account.id)}
                                      disabled={isSyncing}
                                      title="Sync account"
                                    >
                                      <RefreshCw size={13} className={isSyncing ? 'sp-spin' : ''} />
                                    </button>
                                    <button
                                      type="button"
                                      id={`disconnect-${platform.platform}-${account.id}-btn`}
                                      data-account-id={account.id}
                                      className="btn-account-disconnect social-card-disconnect"
                                      onClick={() => handleOpenDisconnectModal(account)}
                                      disabled={isDisconnecting}
                                      title="Disconnect account"
                                    >
                                      <Unlink size={13} />
                                    </button>
                                  </div>
                                </div>
                              )
                            })}
                          </div>
                        ) : (
                          <div className="platform-panel-empty">
                            <p>No account connected yet. Link via OAuth to enable one-click publishing.</p>
                            <button
                              type="button"
                              className="btn-panel-connect-cta"
                              style={{ background: platform.color }}
                              onClick={() => handleConnect(platform)}
                              disabled={isConnecting}
                            >
                              <Plus size={13} />
                              <span>Connect {platform.label}</span>
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  )
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
