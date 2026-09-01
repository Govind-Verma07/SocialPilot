/**
 * src/components/Modal.jsx
 * Reusable modal dialog with backdrop and centered content.
 */

import { useEffect } from 'react'
import './Modal.css'

export default function Modal({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  closeOnBackdrop = true,
  showCloseButton = true,
}) {
  useEffect(() => {
    if (!isOpen) return
    const onEsc = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onEsc)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onEsc)
      document.body.style.overflow = ''
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className="modal-backdrop" onClick={closeOnBackdrop ? onClose : undefined}>
      <div
        className={`modal-card glass-card size-${size}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? 'modal-title' : undefined}
      >
        {showCloseButton && (
          <button
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        )}
        {title && <h3 id="modal-title" className="modal-title">{title}</h3>}
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  )
}
