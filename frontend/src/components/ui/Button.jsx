/**
 * src/components/ui/Button.jsx
 * Reusable button component with variant + size support.
 */

import './Button.css'

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  loading = false,
  disabled = false,
  icon = null,
  onClick,
  type = 'button',
  id,
  ariaLabel,
  form,
  className = '',
}) {
  const classes = [
    'btn',
    `btn-${variant}`,
    `btn-${size}`,
    fullWidth ? 'btn-full' : '',
    loading ? 'loading' : '',
    className,
  ].filter(Boolean).join(' ')

  return (
    <button
      type={type}
      id={id}
      form={form}
      className={classes}
      disabled={disabled || loading}
      onClick={onClick}
      aria-label={ariaLabel}
    >
      {loading ? (
        <>
          <span className="spinner" />
          {children}
        </>
      ) : (
        <>
          {icon && <span className="btn-icon">{icon}</span>}
          {children}
        </>
      )}
    </button>
  )
}
