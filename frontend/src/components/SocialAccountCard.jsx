/**
 * src/components/SocialAccountCard.jsx
 * ------------------------------------
 * Unified card component for social media platform integrations.
 * Supports connected and disconnected accounts with fully responsive vertical layout.
 * Preserves all existing OAuth and account management props and IDs.
 */

import { RefreshCw, Unlink, Plus, Clock } from 'lucide-react'
import './SocialAccountCard.css'

export const PLATFORM_META = {
  facebook:  { label: 'Facebook',     color: '#1877F2', icon: '📘' },
  instagram: { label: 'Instagram',    color: '#E1306C', icon: '📸' },
  linkedin:  { label: 'LinkedIn',     color: '#0A66C2', icon: '💼' },
  x:         { label: 'X (Twitter)',  color: '#38bdf8', icon: '𝕏' },
  youtube:   { label: 'YouTube',      color: '#FF0000', icon: '▶️' },
  pinterest: { label: 'Pinterest',    color: '#E60023', icon: '📌' },
}

export default function SocialAccountCard({
  account,
  platform,
  isAvailable = false,
  onConnect,
  onSync,
  onDisconnect,
  connectLoading = false,
  syncLoading = false,
  disconnectLoading = false,
}) {
  const platformKey = (account?.platform || platform?.platform || 'facebook').toLowerCase()
  const meta = PLATFORM_META[platformKey] || {
    label: platform?.label || platform?.display_name || account?.platform || 'Social Platform',
    color: '#6366f1',
    icon: '🔗',
  }

  // ── Available (Disconnected) Platform Card ──
  if (isAvailable || !account) {
    const p = platform || { platform: platformKey, display_name: meta.label }
    return (
      <div
        className="sp-account-card social-card social-card--available"
        id={`platform-card-${platformKey}`}
      >
        {/* Card Header: Platform brand badge + Disconnected pill */}
        <div className="sp-account-card-top">
          <div className="sp-platform-badge">
            <span className="sp-platform-badge-icon">{meta.icon}</span>
            <span className="sp-platform-badge-name">{meta.label}</span>
          </div>
          <span className="sp-status-badge sp-status-badge--disconnected">
            <span className="sp-status-dot" />
            Disconnected
          </span>
        </div>

        {/* Card Body: Info */}
        <div className="sp-account-card-body">
          <div
            className="sp-account-placeholder-avatar"
            style={{
              background: `${meta.color}15`,
              borderColor: `${meta.color}35`,
              color: meta.color,
            }}
          >
            {meta.icon}
          </div>
          <div className="sp-account-details">
            <h4 className="sp-account-title">{meta.label}</h4>
            <p className="sp-account-subtitle">Not connected yet</p>
          </div>
        </div>

        <p className="sp-account-desc">
          Connect your {meta.label} channel to enable instant and scheduled publishing.
        </p>

        {/* Card Footer: Connect Action */}
        <div className="sp-account-card-footer">
          <button
            id={`connect-${platformKey}-btn`}
            type="button"
            className="sp-btn-connect"
            style={{
              background: meta.color,
              boxShadow: `0 2px 14px ${meta.color}40`,
            }}
            disabled={connectLoading}
            onClick={() => onConnect && onConnect(p)}
          >
            {connectLoading ? (
              <>
                <RefreshCw size={14} className="sp-spin" />
                <span>Connecting…</span>
              </>
            ) : (
              <>
                <Plus size={15} />
                <span>Connect Account</span>
              </>
            )}
          </button>
        </div>
      </div>
    )
  }

  // ── Connected Account Card ──
  const a = account
  const status = a.status || 'connected'
  const statusLabel = status.charAt(0).toUpperCase() + status.slice(1).replace('_', ' ')
  const isOk = status === 'connected'
  const isErr = status === 'token_expired' || status === 'error'

  const formattedDate = a.last_synced_at
    ? new Date(a.last_synced_at).toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : null

  return (
    <div
      className="sp-account-card social-card social-card--connected"
      id={`account-card-${a.id || platformKey}`}
    >
      {/* Card Header: Platform brand badge + Status pill */}
      <div className="sp-account-card-top">
        <div className="sp-platform-badge">
          <span className="sp-platform-badge-icon">{meta.icon}</span>
          <span className="sp-platform-badge-name">{meta.label}</span>
        </div>
        <span
          className={`sp-status-badge ${
            isOk
              ? 'sp-status-badge--success'
              : isErr
              ? 'sp-status-badge--error'
              : 'sp-status-badge--disconnected'
          }`}
        >
          <span className="sp-status-dot" />
          {statusLabel}
        </span>
      </div>

      {/* Card Body: Avatar, Name, Handle */}
      <div className="sp-account-card-body">
        <div className="sp-account-avatar-wrapper" style={{ borderColor: `${meta.color}60` }}>
          {a.profile_picture_url ? (
            <img src={a.profile_picture_url} alt={a.account_name} className="sp-account-avatar-img" />
          ) : (
            <div className="sp-account-avatar-fallback" style={{ background: meta.color }}>
              {a.account_name ? a.account_name.charAt(0).toUpperCase() : meta.icon}
            </div>
          )}
          <span className="sp-account-platform-mini" style={{ background: meta.color }}>
            {meta.icon}
          </span>
        </div>

        <div className="sp-account-details">
          <h4 className="sp-account-title" title={a.account_name || meta.label}>
            {a.account_name || meta.label}
          </h4>
          <p
            className="sp-account-subtitle"
            title={a.account_username ? `@${a.account_username}` : meta.label}
          >
            {a.account_username ? `@${a.account_username}` : meta.label}
          </p>
        </div>
      </div>

      {/* Meta Row: Last synced */}
      <div className="sp-account-sync-meta">
        <Clock size={12} className="sp-sync-clock-icon" />
        <span>{formattedDate ? `Last synced: ${formattedDate}` : 'Recently synced'}</span>
      </div>

      {/* Permissions tags */}
      {a.permissions && a.permissions.length > 0 && (
        <div className="sp-account-permissions">
          {a.permissions
            .filter((p) => p.granted)
            .map((p) => (
              <span key={p.id || p.permission} className="sp-permission-pill">
                {p.permission}
              </span>
            ))}
        </div>
      )}

      {/* Card Footer: Sync & Disconnect buttons */}
      <div className="sp-account-card-footer">
        {onSync && (
          <button
            type="button"
            className="sp-btn-sync"
            onClick={() => onSync(a.id)}
            disabled={syncLoading}
            title="Sync latest account data"
          >
            <RefreshCw size={13} className={syncLoading ? 'sp-spin' : ''} />
            <span>{syncLoading ? 'Syncing…' : 'Sync'}</span>
          </button>
        )}
        <button
          id={`disconnect-${platformKey}-btn`}
          type="button"
          className="sp-btn-disconnect social-card-disconnect"
          onClick={() => onDisconnect && onDisconnect(a)}
          disabled={disconnectLoading}
          title="Disconnect account"
        >
          <Unlink size={13} />
          <span>{disconnectLoading ? 'Disconnecting…' : 'Disconnect'}</span>
        </button>
      </div>
    </div>
  )
}
