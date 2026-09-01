/**
 * src/components/ui/EmptyState.jsx
 * Centered empty state with icon, title, and optional CTA.
 */

import './EmptyState.css'

export default function EmptyState({
  icon = '📭',
  title = 'Nothing here yet',
  description = 'There is no data to display at the moment.',
  actionLabel,
  onAction,
  size = 'md',
}) {
  return (
    <div className={`empty-state size-${size}`}>
      <span className="empty-icon">{icon}</span>
      <h3 className="empty-title">{title}</h3>
      <p className="empty-desc">{description}</p>
      {actionLabel && onAction && (
        <button className="btn btn-primary btn-sm" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  )
}
