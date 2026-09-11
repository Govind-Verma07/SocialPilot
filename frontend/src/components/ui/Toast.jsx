/**
 * src/components/ui/Toast.jsx
 * Lightweight toast / notification component.
 */

import { useEffect } from 'react'
import './Toast.css'

const ICONS = {
  success: '✓',
  error:   '⚠',
  warning: '!',
  info:    'ⓘ',
}

export default function Toast({ message, type = 'info', duration = 4000, onClose }) {
  useEffect(() => {
    if (duration > 0 && onClose) {
      const t = setTimeout(onClose, duration)
      return () => clearTimeout(t)
    }
  }, [duration, onClose])

  return (
    <div className={`toast toast-${type}`} role="alert">
      <span className="toast-icon">{ICONS[type] || ICONS.info}</span>
      <span className="toast-msg">{message}</span>
    </div>
  )
}

export function ToastContainer({ toasts, onRemove }) {
  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <Toast
          key={t.id}
          message={t.msg}
          type={t.type}
          duration={t.duration ?? 4000}
          onClose={() => onRemove(t.id)}
        />
      ))}
    </div>
  )
}
