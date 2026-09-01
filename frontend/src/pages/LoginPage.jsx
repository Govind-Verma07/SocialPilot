/**
 * src/pages/LoginPage.jsx
 * -----------------------
 * Cyberpunk neon styled Login form with User/Admin toggle, email & password icons,
 * Google login button, and success message handling when redirected from registration.
 */

import { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { authApi } from '../api/authApi'
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

function UserCircleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  )
}

function ShieldIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  )
}

export default function LoginPage() {
  const { isAuthenticated, login, loginWithToken, loading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard', { replace: true })
    }
  }, [isAuthenticated, navigate])

  const initialEmail = location.state?.registeredEmail || ''
  const isRedirectedSuccess = location.state?.registeredSuccess || false

  const [loginMode, setLoginMode] = useState('user') // 'user' or 'admin'
  const [form, setForm]         = useState({ email: initialEmail, password: '', rememberMe: false })
  const [showPw, setShowPw]     = useState(false)
  const [error, setError]       = useState('')
  const [successMsg, setSuccessMsg] = useState(isRedirectedSuccess ? 'Registration completed successfully! Please login to continue.' : '')
  const [touched, setTouched]   = useState({})
  const [googleLoading, setGoogleLoading] = useState(false)

  // ── Process Google OAuth callback token / error on mount ───────────────────
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('google_token')
    const errorParam = params.get('error')
    const email = params.get('email')
    const fullName = params.get('full_name')
    const role = params.get('role')

    if (errorParam) {
      setError(decodeURIComponent(errorParam))
      window.history.replaceState({}, document.title, window.location.pathname)
    } else if (token) {
      const userData = {
        email: email || '',
        full_name: fullName || 'Google User',
        role: role || 'content_creator',
      }
      loginWithToken(token, userData)
      window.history.replaceState({}, document.title, window.location.pathname)
      navigate('/dashboard')
    }
  }, [loginWithToken, navigate])

  const handleChange = (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm((prev) => ({ ...prev, [e.target.name]: value }))
    setError('')
    setSuccessMsg('')
  }

  const handleBlur = (e) => setTouched((prev) => ({ ...prev, [e.target.name]: true }))

  const emailErr = touched.email && !form.email.includes('@') ? 'Enter a valid email address.' : ''

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.email.includes('@')) { setError('Please enter a valid email address.'); return }
    if (!form.password)            { setError('Please enter your password.'); return }

    const result = await login({ email: form.email, password: form.password })
    if (result.success) {
      navigate('/dashboard')
    } else {
      setError(result.message)
    }
  }

  // ── Trigger Google OAuth redirect ──────────────────────────────────────────
  const handleGoogleLogin = async () => {
    setError('')
    setSuccessMsg('')
    setGoogleLoading(true)
    try {
      const res = await authApi.getGoogleAuthUrl()
      const data = res.data
      if (data.is_configured && data.authorization_url) {
        window.location.href = data.authorization_url
      } else {
        setError(data.message || 'Google OAuth credentials are not configured in backend .env.')
      }
    } catch {
      setError('Failed to initiate Google OAuth login. Please check backend connection.')
    } finally {
      setGoogleLoading(false)
    }
  }

  return (
    <div className="auth-page">
      {/* Top Header Navigation */}
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

      {/* Login Form Panel */}
      <main className="auth-main-container auth-single-center">
        <div className="neon-card">
          <div className="neon-card-header">
            <h2 className="neon-card-title">Welcome Back!</h2>
            <p className="neon-card-subtitle">Login to continue to your account</p>
          </div>

          {/* Success Banner if coming from Registration */}
          {successMsg && (
            <div className="alert-neon-success" role="alert">
              <span>✅</span>
              <span>{successMsg}</span>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="alert-neon-error" role="alert">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          {/* User / Admin Login Mode Toggle */}
          <div className="role-toggle-container">
            <button
              type="button"
              className={`role-toggle-btn ${loginMode === 'user' ? 'active' : ''}`}
              onClick={() => setLoginMode('user')}
            >
              <UserCircleIcon /> User
            </button>
            <button
              type="button"
              className={`role-toggle-btn ${loginMode === 'admin' ? 'active' : ''}`}
              onClick={() => setLoginMode('admin')}
            >
              <ShieldIcon /> Admin
            </button>
          </div>

          <form onSubmit={handleSubmit} className="neon-form" noValidate>
            {/* Email Field */}
            <div className="input-field-group">
              <span className="input-icon-left"><MailIcon /></span>
              <input
                id="login-email"
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

            {/* Password Field */}
            <div className="input-field-group">
              <span className="input-icon-left"><LockIcon /></span>
              <input
                id="login-password"
                name="password"
                type={showPw ? 'text' : 'password'}
                autoComplete="current-password"
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
            </div>

            {/* Remember Me & Forgot Password */}
            <div className="form-options-row">
              <label className="remember-checkbox">
                <input
                  type="checkbox"
                  name="rememberMe"
                  checked={form.rememberMe}
                  onChange={handleChange}
                />
                <span>Remember me</span>
              </label>
              <a href="#" className="forgot-link" onClick={(e) => e.preventDefault()}>
                Forgot Password?
              </a>
            </div>

            {/* Submit Button */}
            <button
              id="login-submit"
              type="submit"
              className="btn-neon-primary"
              disabled={loading}
            >
              {loading ? 'Signing in…' : 'Login →'}
            </button>

            <div className="neon-divider">OR</div>

            {/* Google SSO Button */}
            <button
              type="button"
              className="btn-google-login"
              onClick={handleGoogleLogin}
              disabled={googleLoading || loading}
            >
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
              </svg>
              <span>{googleLoading ? 'Connecting to Google…' : 'Login with Google'}</span>
            </button>
          </form>

          <div className="neon-card-footer">
            Don't have an account? <Link to="/register" className="neon-link">Register</Link>
          </div>
        </div>
      </main>
    </div>
  )
}
