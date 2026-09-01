/**
 * src/components/ui/GlowCard.jsx
 * A card with subtle 3D border, neon edge highlight, and glassmorphism background.
 */

import './GlowCard.css'

export default function GlowCard({ children, className = '', padding = '24px', hover = true, onClick }) {
  return (
    <div
      className={`glow-card glass-card ${hover ? 'hover-lift' : ''} ${className}`}
      style={{ '--card-padding': padding }}
      onClick={onClick}
    >
      {children}
    </div>
  )
}
