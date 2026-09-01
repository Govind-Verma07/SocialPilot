/**
 * src/components/ui/StatusBadge.jsx
 * Small pill badge indicating connection or workflow status.
 */

import './StatusBadge.css'

const VARIANTS = {
  connected:    { bg: 'rgba(16,185,129,0.12)', color: '#10b981', dot: '#10b981' },
  success:      { bg: 'rgba(16,185,129,0.12)', color: '#10b981', dot: '#10b981' },
  error:        { bg: 'rgba(239,68,68,0.12)',     color: '#ef4444', dot: '#ef4444' },
  warning:      { bg: 'rgba(245,158,11,0.12)',    color: '#f59e0b', dot: '#f59e0b' },
  info:         { bg: 'rgba(14,165,233,0.12)',    color: '#06b6d4', dot: '#06b6d4' },
  disconnected: { bg: 'rgba(107,114,128,0.15)',   color: '#9ca3af', dot: '#9ca3af' },
  pending:      { bg: 'rgba(107,114,128,0.12)',   color: '#9ca3af', dot: '#9ca3af' },
}

export default function StatusBadge({ status, label, showDot = true, size = 'sm' }) {
  const v = VARIANTS[status] || VARIANTS.pending
  return (
    <span className={`status-badge status-${status} size-${size}`} style={{ '--sb-bg': v.bg, '--sb-color': v.color, '--sb-dot': v.dot }}>
      {showDot && <span className="status-dot" />}
      {label}
    </span>
  )
}
