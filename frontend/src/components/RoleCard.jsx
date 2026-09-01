/**
 * src/components/RoleCard.jsx
 * Visually attractive role selection card with icon, title, description,
 * selected state, and 3D border glow.
 */

import './RoleCard.css'

export default function RoleCard({
  role,
  title,
  description,
  icon,
  isSelected = false,
  onSelect,
  disabled = false,
}) {
  return (
    <div
      className={`role-card ${isSelected ? 'selected' : ''} ${disabled ? 'disabled' : ''}`}
      onClick={() => !disabled && onSelect(role)}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-pressed={isSelected}
      onKeyDown={(e) => {
        if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault()
          onSelect(role)
        }
      }}
    >
      <div className="role-card-left">
        <span className="role-card-icon">{icon}</span>
        <div className="role-card-text">
          <span className="role-card-title">{title}</span>
          <span className="role-card-desc">{description}</span>
        </div>
      </div>
      <div className={`role-radio ${isSelected ? 'checked' : ''}`} />
    </div>
  )
}
