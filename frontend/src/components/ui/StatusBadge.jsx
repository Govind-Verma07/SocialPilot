/**
 * src/components/ui/StatusBadge.jsx
 * Clean Shadcn-style pill badges for post/account statuses.
 * All existing status values preserved.
 */

import './StatusBadge.css'

const VARIANTS = {
  connected:    'success',
  success:      'success',
  published:    'success',
  error:        'error',
  failed:       'error',
  warning:      'warning',
  scheduled:    'warning',
  processing:   'info',
  info:         'info',
  disconnected: 'muted',
  pending:      'muted',
  draft:        'muted',
  skipped:      'muted',
}

const LABELS = {
  connected:    'Connected',
  success:      'Success',
  published:    'Published',
  error:        'Error',
  failed:       'Failed',
  warning:      'Warning',
  scheduled:    'Scheduled',
  processing:   'Processing',
  info:         'Info',
  disconnected: 'Disconnected',
  pending:      'Pending',
  draft:        'Draft',
  skipped:      'Skipped',
}

export default function StatusBadge({ status, label, showDot = true, size = 'sm' }) {
  const variant = VARIANTS[status?.toLowerCase()] || 'muted'
  const displayLabel = label || LABELS[status?.toLowerCase()] || status || 'Unknown'

  return (
    <span className={`sp-status-badge sp-status-${variant} ${size === 'md' ? 'sp-status-md' : ''}`}>
      {showDot && <span className="sp-status-dot" />}
      {displayLabel}
    </span>
  )
}
