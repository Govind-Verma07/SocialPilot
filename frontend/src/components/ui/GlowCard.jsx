/**
 * src/components/ui/GlowCard.jsx
 * Modernized card — clean Shadcn-style surface with optional hover lift.
 * Drop-in replacement: accepts all existing props.
 */

import './GlowCard.css'

export default function GlowCard({
  children,
  className = '',
  padding,
  hover = true,
  onClick,
  style,
}) {
  return (
    <div
      className={`sp-card ${hover ? 'sp-card-hover' : ''} ${className}`}
      style={{ ...(padding ? { padding } : {}), ...style }}
      onClick={onClick}
    >
      {children}
    </div>
  )
}
