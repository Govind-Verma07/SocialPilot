/**
 * src/components/ui/EmptyState.jsx
 * Modernized empty state — clean icon container, professional typography.
 * All existing props preserved.
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
    <div className={`sp-empty-state ${size === 'sm' ? 'sp-empty-sm' : ''}`}>
      <div className="sp-empty-icon-wrap">
        <span className="sp-empty-icon">{icon}</span>
      </div>
      <h3 className="sp-empty-title">{title}</h3>
      <p className="sp-empty-desc">{description}</p>
      {actionLabel && onAction && (
        <button className="btn btn-primary btn-sm" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  )
}
