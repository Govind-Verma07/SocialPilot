/**
 * src/components/ui/Button.jsx
 * Modernized button — Shadcn-style variants, sizes, icon support, loading state.
 * All existing variant names preserved for backward compat.
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
  iconRight = null,
  onClick,
  type = 'button',
  id,
  ariaLabel,
  form,
  className = '',
  title,
  style,
}) {
  const sizeClass = size === 'sm' ? 'btn-sm' : size === 'lg' ? 'btn-lg' : size === 'xl' ? 'btn-xl' : size === 'icon' ? 'btn-icon' : ''

  const classes = [
    'btn',
    `btn-${variant}`,
    sizeClass,
    fullWidth ? 'btn-full' : '',
    loading ? 'btn-loading' : '',
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
      title={title}
      style={style}
    >
      {loading ? (
        <>
          <span className="spinner" />
          {children && <span>{children}</span>}
        </>
      ) : (
        <>
          {icon && <span className="btn-icon-left">{icon}</span>}
          {children}
          {iconRight && <span className="btn-icon-right">{iconRight}</span>}
        </>
      )}
    </button>
  )
}
