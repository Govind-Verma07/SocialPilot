/**
 * src/components/SocialAccountCard.jsx
 * Unified card for both connected social accounts and available platforms.
 * Preserves all existing OAuth, sync, and disconnect behavior.
 */

import './SocialAccountCard.css'

const PLATFORM_META = {
  facebook:  { label: 'Facebook',  color: '#1877F2', icon: '📘' },
  instagram: { label: 'Instagram', color: '#E1306C', icon: '📸' },
  linkedin:  { label: 'LinkedIn',  color: '#0A66C2', icon: '💼' },
  x:         { label: 'X (Twitter)', color: '#000000', icon: '𝕏' },
  youtube:   { label: 'YouTube',   color: '#FF0000', icon: '▶️' },
  pinterest: { label: 'Pinterest', color: '#E60023', icon: '📌' },
}

export default function SocialAccountCard({
  account,
  platform,
  isAvailable = false,
  connectedAccountsCount = 0,
  onConnect,
  onSync,
  onDisconnect,
  syncLoading = false,
  disconnectLoading = false,
}) {
  const meta = PLATFORM_META[account?.platform || platform?.platform] || {
    label: platform?.display_name || account?.platform || 'Linked',
    color: '#6366f1',
    icon: '🔗',
  }

  if (isAvailable) {
    const p = platform
    const count = connectedAccountsCount || 0
    return (
      <div className="social-card social-card--available">
        <div className="social-card-left">
          <span className="social-card-platform-icon" style={{ color: meta.color }}>{meta.icon}</span>
          <div className="social-card-info">
            <span className="social-card-name">{meta.label}</span>
            {count > 0 ? (
              <span className="social-card-connected-count" style={{ color: '#10b981', fontSize: '11px', fontWeight: 600 }}>
                ● {count} account{count > 1 ? 's' : ''} connected
              </span>
            ) : !p.is_configured ? (
              <span className="social-card-warning">⏳ Awaiting platform credentials</span>
            ) : null}
          </div>
        </div>
        <button
          id={`connect-${p.platform}-btn`}
          className="btn btn-primary btn-sm"
          style={{
            background: meta.color,
            color: '#fff',
            cursor: 'pointer',
            border: 'none',
            boxShadow: `0 0 14px ${meta.color}55`,
          }}
          onClick={() => onConnect(p)}
        >
          {count > 0 ? '+ Add Another Account' : '+ Connect Account'}
        </button>
      </div>
    )
  }

  // Connected account card
  const a = account
  const status = a.status || 'connected'
  const statusLabel = status.charAt(0).toUpperCase() + status.slice(1).replace('_', ' ')
  const statusVariant = status === 'connected' ? 'success'
    : status === 'token_expired' || status === 'error' ? 'error'
    : 'disconnected'

  return (
    <div className="social-card social-card--connected">
      <div className="social-card-left">
        <div className="social-card-avatar" style={{ borderColor: `${meta.color}44` }}>
          {a.profile_picture_url
            ? <img src={a.profile_picture_url} alt={a.account_name} className="social-card-avatar-img" />
            : meta.icon}
        </div>
        <div className="social-card-info">
          <div className="social-card-header-row">
            <span className="social-card-name">{a.account_name}</span>
            <span className="social-card-status" style={{
              background: statusVariant === 'success' ? 'rgba(16,185,129,0.12)'
                : statusVariant === 'error' ? 'rgba(239,68,68,0.12)'
                : 'rgba(107,114,128,0.15)',
              color: statusVariant === 'success' ? '#10b981'
                : statusVariant === 'error' ? '#ef4444'
                : '#9ca3af',
              borderColor: statusVariant === 'success' ? 'rgba(16,185,129,0.3)'
                : statusVariant === 'error' ? 'rgba(239,68,68,0.3)'
                : 'rgba(107,114,128,0.3)',
            }}>
              <span className="social-card-status-dot" />
              {statusLabel}
            </span>
          </div>
          <span className="social-card-username">
            {a.account_username ? `@${a.account_username} · ${meta.label}` : meta.label}
          </span>
          {a.last_synced_at && (
            <span className="social-card-synced">
              Last synced: {new Date(a.last_synced_at).toLocaleString()}
            </span>
          )}
          {a.permissions?.length > 0 && (
            <div className="social-card-permissions">
              {a.permissions.filter((p) => p.granted).map((p) => (
                <span key={p.id} className="social-card-permission">{p.permission}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="social-card-actions">
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => onSync(a.id)}
          disabled={syncLoading}
          title="Sync account"
        >
          {syncLoading ? '⟳' : '↻ Sync'}
        </button>
        <button
          className="btn btn-ghost btn-sm social-card-disconnect"
          onClick={() => onDisconnect(a.id)}
          disabled={disconnectLoading}
          title="Disconnect"
        >
          ✕ Disconnect
        </button>
      </div>
    </div>
  )
}
