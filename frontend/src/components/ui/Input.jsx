/**
 * src/components/ui/Input.jsx
 * Reusable text input with label, error state, and hint.
 */

import './Input.css'

export default function Input({
  id,
  name,
  label,
  type = 'text',
  value,
  onChange,
  onBlur,
  placeholder,
  error = '',
  hint = '',
  required = false,
  autoComplete,
  autoFocus,
  disabled = false,
  maxLength,
  className = '',
}) {
  const inputClasses = [
    'form-input',
    error ? 'input-error' : '',
    disabled ? 'disabled' : '',
    className,
  ].filter(Boolean).join(' ')

  return (
    <div className="form-group">
      {label && (
        <label className="form-label" htmlFor={id}>
          {label} {required && <span className="label-required">*</span>}
        </label>
      )}
      <input
        id={id}
        name={name}
        type={type}
        value={value}
        onChange={onChange}
        onBlur={onBlur}
        placeholder={placeholder}
        className={inputClasses}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        disabled={disabled}
        maxLength={maxLength}
        required={required}
        aria-invalid={!!error}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
      />
      {error && (
        <span id={`${id}-error`} className="field-error">
          {error}
        </span>
      )}
      {hint && !error && (
        <span id={`${id}-hint`} className="field-hint">
          {hint}
        </span>
      )}
    </div>
  )
}
