/**
 * src/pages/LoginPage.jsx
 * ------------------------
 * Glassmorphism login card with email/password fields,
 * real-time validation feedback, and smooth animations.
 */

import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
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

export default function LoginPage() {
  const { login, loading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname ?? '/dashboard'

  const [form, setForm]       = useState({ email: '', password: '' })
  const [showPw, setShowPw]   = useState(false)
  const [error, setError]     = useState('')
  const [touched, setTouched] = useState({})

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))
    setError('')
  }
  const handleBlur = (e) => setTouched((prev) => ({ ...prev, [e.target.name]: true }))

  const validate = () => {
    if (!form.email.includes('@')) return 'Please enter a valid email address.'
    if (form.password.length < 8)  return 'Password must be at least 8 characters.'
    return null
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const err = validate()
    if (err) { setError(err); return }

    const result = await login({ email: form.email, password: form.password })
    if (result.success) {
      navigate(from, { replace: true })
    } else {
      setError(result.message)
    }
  }

  const emailErr = touched.email && !form.email.includes('@') ? 'Enter a valid email.' : ''
  const pwErr    = touched.password && form.password.length > 0 && form.password.length < 8
    ? 'At least 8 characters required.' : ''

  return (
    <div className="auth-page">
      <div className="orb orb-1" />
      <div className="orb orb-2" />

      <Link to="/" className="auth-back">
        ← Back to home
      </Link>

      <div className="auth-container">
        {/* Side panel */}
        <div className="auth-side">
          <div className="auth-side-content">
            <div className="brand-icon-lg">🚀</div>
            <h2 className="auth-side-title">
              Welcome back<br />to <span className="gradient-text">SocialPilot</span>
            </h2>
            <p className="auth-side-desc">
              Your social media command centre is ready. Sign in and take control.
            </p>
            <div className="auth-testimonial">
              <div className="testimonial-avatar">JD</div>
              <div>
                <p className="testimonial-text">"SocialPilot tripled our engagement in 60 days."</p>
                <p className="testimonial-author">— Jane Doe, Growth Lead at Acme</p>
              </div>
            </div>
          </div>
        </div>

        {/* Form card */}
        <div className="auth-card glass-card">
          <div className="auth-card-header">
            <h1 className="auth-title">Sign in</h1>
            <p className="auth-subtitle">Enter your credentials to continue</p>
          </div>

          {error && (
            <div className="alert alert-error" role="alert">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="auth-form" noValidate>
            <div className="form-group">
              <label className="form-label" htmlFor="login-email">Email</label>
              <input
                id="login-email"
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
              <label className="form-label" htmlFor="login-password">Password</label>
              <div className="form-input-wrapper">
                <input
                  id="login-password"
                  name="password"
                  type={showPw ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={form.password}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  placeholder="••••••••"
                  className={`form-input${pwErr ? ' input-error' : ''}`}
                  required
                />
                <button
                  type="button"
                  className="input-icon"
                  onClick={() => setShowPw(!showPw)}
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                >
                  <EyeIcon open={showPw} />
                </button>
              </div>
              {pwErr && <span className="field-error">⚠ {pwErr}</span>}
            </div>

            <button
              id="login-submit"
              type="submit"
              className="btn btn-primary btn-full btn-lg"
              disabled={loading}
            >
              {loading ? <><span className="spinner" /> Signing in…</> : 'Sign in →'}
            </button>
          </form>

          <div className="divider">or</div>

          <p className="auth-switch">
            Don't have an account?{' '}
            <Link to="/register" className="auth-link">Create one free →</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
