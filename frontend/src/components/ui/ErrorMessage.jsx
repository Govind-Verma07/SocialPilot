/**
 * src/components/ui/ErrorMessage.jsx
 * Inline error message with icon, respects reduced-motion.
 */

import './ErrorMessage.css'

export default function ErrorMessage({ message, className = '' }) {
  if (!message) return null
  return (
    <div className={`error-message ${className}`} role="alert">
      <span className="error-icon">⚠</span>
      <span className="error-text">{message}</span>
    </div>
  )
}
