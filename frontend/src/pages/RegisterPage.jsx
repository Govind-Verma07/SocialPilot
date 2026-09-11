/**
 * src/pages/RegisterPage.jsx
 * ---------------------------
 * Registration form with 3 role options (Content Creator, Marketing Team, Business User),
 * input field icons, password strength meter, green success alert, and delayed redirect to /login.
 */

import { useState, useMemo, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import logoImg from '../assets/logo.png'
import './AuthPages.css'

function EyeIcon({ open }) {
  return open ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function UserIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  )
}

function MailIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
      <polyline points="22,6 12,13 2,6" />
    </svg>
  )
}

function LockIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  )
}

function PasswordStrength({ password }) {
  const checks = useMemo(() => ({
    length: password.length >= 8,
    upper: /[A-Z]/.test(password),
    digit: /[0-9]/.test(password),
  }), [password])

  const score = Object.values(checks).filter(Boolean).length
  const labels = ['Weak', 'Fair', 'Strong']
  const colors = ['#ef4444', '#f59e0b', '#10b981']

  if (!password) return null

  return (
    <div className="pw-strength" style={{ marginTop: '6px' }}>
      <div className="pw-bars" style={{ display: 'flex', gap: '4px' }}>
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="pw-bar"
            style={{
              flex: 1,
              height: '3px',
              borderRadius: '2px',
              background: i < score ? colors[score - 1] : 'rgba(255,255,255,0.1)',
              transition: `background 0.3s ${i * 0.05}s`,
            }}
          />
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
        <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: score > 0 ? colors[score - 1] : 'transparent' }}>
          {score > 0 ? labels[score - 1] : ''}
        </span>
        <div style={{ display: 'flex', gap: '8px' }}>
          {[
            { key: 'length', text: '8+ chars' },
            { key: 'upper', text: 'Uppercase' },
            { key: 'digit', text: 'Number' },
          ].map(({ key, text }) => (
            <span key={key} style={{ fontSize: '11px', color: checks[key] ? '#10b981' : '#64748b' }}>
              {checks[key] ? '✓' : '○'} {text}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function RegisterPage() {
  const { isAuthenticated, register, loading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard', { replace: true })
    }
  }, [isAuthenticated, navigate])

  const [form, setForm] = useState({
    fullName: '', email: '', password: '', confirmPassword: '', role: 'content_creator',
  })
  const [showPw, setShowPw] = useState(false)
  const [showCpw, setShowCpw] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [touched, setTouched] = useState({})

  const publicRoles = [
    {
      id: 'content_creator',
      title: 'Content Creator',
      desc: 'Perfect for individual creators, influencers and personal brands.',
      icon: '🪶',
    },
    {
      id: 'marketing_team',
      title: 'Marketing Team',
      desc: 'Ideal for teams and agencies managing multiple accounts.',
      icon: '👥',
    },
    {
      id: 'business_user',
      title: 'Business User',
      desc: 'Designed for founders, SMB owners, and growing businesses.',
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
    if (!form.email.includes('@')) return 'Please enter a valid email address.'
    if (form.password.length < 8) return 'Password must be at least 8 characters.'
    if (!/[A-Z]/.test(form.password)) return 'Password must contain an uppercase letter.'
    if (!/[0-9]/.test(form.password)) return 'Password must contain a number.'
    if (form.password !== form.confirmPassword) return 'Passwords do not match.'
    return null
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const err = validate()
    if (err) { setError(err); return }

    setError('')
    const result = await register({
      fullName: form.fullName.trim(),
      email: form.email,
      password: form.password,
      role: form.role,
    })
    if (result.success) {
      setSuccess('Account registered successfully! Redirecting to login page...')
      setTimeout(() => {
        navigate('/login', { state: { registeredEmail: form.email, registeredSuccess: true } })
      }, 2000)
    } else {
      setError(result.message)
    }
  }

  const nameErr = touched.fullName && form.fullName.trim().length < 2 ? 'At least 2 characters.' : ''
  const emailErr = touched.email && !form.email.includes('@') ? 'Enter a valid email.' : ''
  const cpwErr = touched.confirmPassword && form.confirmPassword && form.password !== form.confirmPassword
    ? 'Passwords do not match.' : ''

  return (
    <div className="auth-page">
      {/* Navigation Header */}
      <header className="auth-nav-header">
        <Link to="/" className="auth-brand-logo">
          <div className="brand-icon-orb">
            <img src={logoImg} alt="Logo" style={{ width: '24px', height: '24px', objectFit: 'contain' }} />
          </div>
          <div className="brand-logo-text">
            <span className="brand-title">SocialPilot</span>
            <span className="brand-tagline">Manage. Schedule. Grow.</span>
          </div>
        </Link>

        <div className="auth-nav-links">
          <Link to="/" className="auth-nav-link">Features</Link>
          <Link to="/" className="auth-nav-link">Pricing</Link>
          <Link to="/" className="auth-nav-link">Resources ▾</Link>
          <Link to="/" className="auth-nav-link">About Us</Link>
        </div>

        <div className="auth-header-badges">
          <span className="auth-header-badge">🧊 3D Animated UI</span>
          <span className="auth-header-badge">✨ Dark & Stylish</span>
          <span className="auth-header-badge">👤 User Friendly</span>
          <span className="auth-header-badge">🛡️ Secure & Fast</span>
        </div>
      </header>

      {/* Hero Title Section */}
      <section className="auth-hero-section">
        <h1 className="auth-hero-title">SocialPilot</h1>
        <p className="auth-hero-subtitle">Smart Social Media Management</p>
        <div className="auth-hero-line" />
      </section>

      {/* Register Panel */}
      <main className="auth-main-container auth-single-center">
        <div className="neon-card">
          <div className="neon-card-header">
            <h2 className="neon-card-title">Create Your Account</h2>
            <p className="neon-card-subtitle">Join SocialPilot and start your journey</p>
          </div>

          {/* Success Banner */}
          {success && (
            <div className="alert-neon-success" role="alert">
              <span>✅</span>
              <span>{success}</span>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="alert-neon-error" role="alert">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="neon-form" noValidate>
            {/* Role Selection Label */}
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#94a3b8', marginBottom: '-4px' }}>
              Select Your Role
            </div>

            {/* 3 Role Selection Cards */}
            <div className="roles-grid-3">
              {publicRoles.map((r) => {
                const isSelected = form.role === r.id
                return (
                  <div
                    key={r.id}
                    className={`role-card-neon ${isSelected ? 'selected' : ''}`}
                    onClick={() => handleRoleSelect(r.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleRoleSelect(r.id) }}
                  >
                    <div className="role-check-badge">
                      <CheckIcon />
                    </div>
                    <div className="role-icon-box">{r.icon}</div>
                    <div className="role-card-title">{r.title}</div>
                    <div className="role-card-desc">{r.desc}</div>
                  </div>
                )
              })}
            </div>

            {/* Full Name */}
            <div className="input-field-group">
              <span className="input-icon-left"><UserIcon /></span>
              <input
                id="reg-fullname"
                name="fullName"
                type="text"
                autoComplete="name"
                value={form.fullName}
                onChange={handleChange}
                onBlur={handleBlur}
                placeholder="Full Name"
                className={`neon-input${nameErr ? ' input-error' : ''}`}
                required
              />
              {nameErr && <span className="field-error" style={{ fontSize: '12px', color: '#ef4444', marginTop: '4px', display: 'block' }}>⚠ {nameErr}</span>}
            </div>

            {/* Email */}
            <div className="input-field-group">
              <span className="input-icon-left"><MailIcon /></span>
              <input
                id="reg-email"
                name="email"
                type="email"
                autoComplete="email"
                value={form.email}
                onChange={handleChange}
                onBlur={handleBlur}
                placeholder="Email Address"
                className={`neon-input${emailErr ? ' input-error' : ''}`}
                required
              />
              {emailErr && <span className="field-error" style={{ fontSize: '12px', color: '#ef4444', marginTop: '4px', display: 'block' }}>⚠ {emailErr}</span>}
            </div>

            {/* Password */}
            <div className="input-field-group">
              <span className="input-icon-left"><LockIcon /></span>
              <input
                id="reg-password"
                name="password"
                type={showPw ? 'text' : 'password'}
                autoComplete="new-password"
                value={form.password}
                onChange={handleChange}
                onBlur={handleBlur}
                placeholder="Password"
                className="neon-input"
                required
              />
              <button type="button" className="input-icon-right" onClick={() => setShowPw(!showPw)}>
                <EyeIcon open={showPw} />
              </button>
              <PasswordStrength password={form.password} />
            </div>

            {/* Confirm Password */}
            <div className="input-field-group">
              <span className="input-icon-left"><LockIcon /></span>
              <input
                id="reg-confirm"
                name="confirmPassword"
                type={showCpw ? 'text' : 'password'}
                autoComplete="new-password"
                value={form.confirmPassword}
                onChange={handleChange}
                onBlur={handleBlur}
                placeholder="Confirm Password"
                className={`neon-input${cpwErr ? ' input-error' : ''}`}
                required
              />
              <button type="button" className="input-icon-right" onClick={() => setShowCpw(!showCpw)}>
                <EyeIcon open={showCpw} />
              </button>
              {cpwErr && <span className="field-error" style={{ fontSize: '12px', color: '#ef4444', marginTop: '4px', display: 'block' }}>⚠ {cpwErr}</span>}
            </div>

            {/* Submit button */}
            <button
              id="register-submit"
              type="submit"
              className="btn-neon-primary"
              disabled={loading || !!success}
            >
              {loading ? 'Creating Account…' : 'Create Account →'}
            </button>
          </form>

          <div className="neon-card-footer">
            Already have an account? <Link to="/login" className="neon-link">Login</Link>
          </div>
        </div>
      </main>
    </div>
  )
}