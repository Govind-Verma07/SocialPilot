/**
 * src/pages/RegisterPage.jsx
 * ---------------------------
 * Registration form with full-name, email, password + confirm password.
 * Real-time strength indicator, animated validation feedback.
 */

import { useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import './AuthPages.css'

function EyeIcon({ open }) {
  return open ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
      <line x1="1" y1="1" x2="23" y2="23"/>
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  )
}

function PasswordStrength({ password }) {
  const checks = useMemo(() => ({
    length:  password.length >= 8,
    upper:   /[A-Z]/.test(password),
    digit:   /[0-9]/.test(password),
  }), [password])

  const score = Object.values(checks).filter(Boolean).length
  const labels = ['Weak', 'Fair', 'Strong']
  const colors = ['#ef4444', '#f59e0b', '#10b981']

  if (!password) return null

  return (
    <div className="pw-strength">
      <div className="pw-bars">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="pw-bar"
            style={{
              background: i < score ? colors[score - 1] : 'rgba(255,255,255,0.08)',
              transition: `background 0.3s ${i * 0.05}s`,
            }}
          />
        ))}
      </div>
      <span className="pw-label" style={{ color: score > 0 ? colors[score - 1] : 'transparent' }}>
        {score > 0 ? labels[score - 1] : ''}
      </span>
      <div className="pw-checks">
        {[
          { key: 'length', text: '8+ characters' },
          { key: 'upper',  text: 'Uppercase letter' },
          { key: 'digit',  text: 'Number' },
        ].map(({ key, text }) => (
          <span key={key} className={`pw-check ${checks[key] ? 'met' : ''}`}>
            {checks[key] ? <CheckIcon /> : '○'} {text}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function RegisterPage() {
  const { register, loading } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    fullName: '', email: '', password: '', confirmPassword: '', role: 'content_creator',
  })
  const [showPw, setShowPw]       = useState(false)
  const [showCpw, setShowCpw]     = useState(false)
  const [error, setError]         = useState('')
  const [touched, setTouched]     = useState({})

  const publicRoles = [
    {
      id: 'content_creator',
      title: 'Content Creator',
      desc: 'Solopreneurs, influencers, and creative individuals',
      icon: '🎨',
    },
    {
      id: 'marketing_team',
      title: 'Marketing Team',
      desc: 'Agencies, brand teams, and marketing squads',
      icon: '👥',
    },
    {
      id: 'business_user',
      title: 'Business User',
      desc: 'Founders, SMB owners, and growing businesses',
      icon: '💼',
    },
  ]

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))
    setError('')
  }
  const handleRoleSelect = (roleId) => {
    setForm((prev) => ({ ...prev, role: roleId }))
    setError('')
  }
  const handleBlur = (e) => setTouched((prev) => ({ ...prev, [e.target.name]: true }))

  const validate = () => {
    if (form.fullName.trim().length < 2) return 'Full name must be at least 2 characters.'
    if (!form.email.includes('@'))       return 'Please enter a valid email address.'
    if (form.password.length < 8)        return 'Password must be at least 8 characters.'
    if (!/[A-Z]/.test(form.password))    return 'Password must contain an uppercase letter.'
    if (!/[0-9]/.test(form.password))    return 'Password must contain a number.'
    if (form.password !== form.confirmPassword) return 'Passwords do not match.'
    return null
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const err = validate()
    if (err) { setError(err); return }

    const result = await register({
      fullName: form.fullName.trim(),
      email:    form.email,
      password: form.password,
      role:     form.role,
    })
    if (result.success) {
      navigate('/dashboard')
    } else {
      setError(result.message)
    }
  }

  const nameErr  = touched.fullName && form.fullName.trim().length < 2 ? 'At least 2 characters.' : ''
  const emailErr = touched.email && !form.email.includes('@') ? 'Enter a valid email.' : ''
  const cpwErr   = touched.confirmPassword && form.confirmPassword && form.password !== form.confirmPassword
    ? 'Passwords do not match.' : ''

  return (
    <div className="auth-page">
      <div className="orb orb-1" />
      <div className="orb orb-2" />

      <Link to="/" className="auth-back">← Back to home</Link>

      <div className="auth-container">
        {/* Side panel */}
        <div className="auth-side">
          <div className="auth-side-content">
            <div className="brand-icon-lg">🚀</div>
            <h2 className="auth-side-title">
              Launch your brand on<br />
              <span className="gradient-text">every platform</span>
            </h2>
            <p className="auth-side-desc">
              Join thousands of creators and brands using SocialPilot to grow smarter and faster.
            </p>
            <div className="auth-perks">
              {['Free forever plan', 'No credit card required', 'Connect 6+ platforms', 'AI-powered tools'].map(p => (
                <div key={p} className="perk-item">
                  <span className="perk-check">✓</span>
                  <span>{p}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Form card */}
        <div className="auth-card glass-card">
          <div className="auth-card-header">
            <h1 className="auth-title">Create account</h1>
            <p className="auth-subtitle">Start your 14-day free trial today</p>
          </div>

          {error && (
            <div className="alert alert-error" role="alert">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="auth-form" noValidate>
            <div className="form-group">
              <label className="form-label" htmlFor="reg-fullname">Full name</label>
              <input
                id="reg-fullname"
                name="fullName"
                type="text"
                autoComplete="name"
                value={form.fullName}
                onChange={handleChange}
                onBlur={handleBlur}
                placeholder="Jane Doe"
                className={`form-input${nameErr ? ' input-error' : ''}`}
                required
              />
              {nameErr && <span className="field-error">⚠ {nameErr}</span>}
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="reg-email">Email</label>
              <input
                id="reg-email"
                name="email"
                type="email"
                autoComplete="email"
                value={form.email}
                onChange={handleChange}
                onBlur={handleBlur}
                placeholder="you@example.com"
                className={`form-input${emailErr ? ' input-error' : ''}`}
                required
              />
              {emailErr && <span className="field-error">⚠ {emailErr}</span>}
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="reg-password">Password</label>
              <div className="form-input-wrapper">
                <input
                  id="reg-password"
                  name="password"
                  type={showPw ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={form.password}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="••••••••"
                  className="form-input"
                  required
                />
                <button type="button" className="input-icon" onClick={() => setShowPw(!showPw)}>
                  <EyeIcon open={showPw} />
                </button>
              </div>
              <PasswordStrength password={form.password} />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="reg-confirm">Confirm password</label>
              <div className="form-input-wrapper">
                <input
                  id="reg-confirm"
                  name="confirmPassword"
                  type={showCpw ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={form.confirmPassword}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="••••••••"
                  className={`form-input${cpwErr ? ' input-error' : ''}`}
                  required
                />
                <button type="button" className="input-icon" onClick={() => setShowCpw(!showCpw)}>
                  <EyeIcon open={showCpw} />
                </button>
              </div>
              {cpwErr && <span className="field-error">⚠ {cpwErr}</span>}
            </div>

            <div className="form-group">
              <label className="form-label">What best describes you?</label>
              <div className="role-selector-grid">
                {publicRoles.map((r) => {
                  const isSelected = form.role === r.id
                  return (
                    <div
                      key={r.id}
                      className={`role-option-card ${isSelected ? 'selected' : ''}`}
                      onClick={() => handleRoleSelect(r.id)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleRoleSelect(r.id) }}
                    >
                      <div className="role-option-header">
                        <span className="role-option-icon">{r.icon}</span>
                        <span className="role-option-title">{r.title}</span>
                        <span className={`role-radio ${isSelected ? 'checked' : ''}`} />
                      </div>
                      <p className="role-option-desc">{r.desc}</p>
                    </div>
                  )
                })}
              </div>
            </div>

            <button
              id="register-submit"
              type="submit"
              className="btn btn-primary btn-full btn-lg"
              disabled={loading}
            >
              {loading ? <><span className="spinner" /> Creating account…</> : 'Create account →'}
            </button>

            <p className="auth-terms">
              By creating an account you agree to our{' '}
              <a href="#" onClick={(e) => e.preventDefault()}>Terms of Service</a> and{' '}
              <a href="#" onClick={(e) => e.preventDefault()}>Privacy Policy</a>.
            </p>
          </form>

          <div className="divider">already have an account?</div>

          <p className="auth-switch">
            <Link to="/login" className="auth-link">Sign in →</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
