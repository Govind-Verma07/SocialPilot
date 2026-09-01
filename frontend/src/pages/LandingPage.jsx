/**
 * src/pages/LandingPage.jsx
 * Premium landing page with animated hero, feature grid, and CTAs.
 */

import { useEffect, useRef } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import logoImg from '../assets/logo.png'
import './LandingPage.css'

const features = [
  { icon: '📅', title: 'Smart Scheduling', desc: 'Queue posts across all platforms. Our AI picks the best time to maximise reach.' },
  { icon: '📊', title: 'Deep Analytics', desc: 'Track engagement, growth, and ROI with beautiful real-time dashboards.' },
  { icon: '🤖', title: 'AI Content Studio', desc: 'Generate captions, hashtags and visuals in seconds with built-in AI.' },
  { icon: '🔗', title: 'Multi-Platform', desc: 'Manage Instagram, X, LinkedIn, TikTok and more from one unified hub.' },
  { icon: '🎯', title: 'Campaign Manager', desc: 'Plan end-to-end campaigns with calendar view, teams, and approvals.' },
  { icon: '🔔', title: 'Smart Alerts', desc: 'Get notified when posts go viral or when engagement spikes unexpectedly.' },
]

const platforms = [
  { name: 'Instagram', color: '#E1306C' },
  { name: 'X / Twitter', color: '#1DA1F2' },
  { name: 'LinkedIn',   color: '#0A66C2' },
  { name: 'TikTok',     color: '#69C9D0' },
  { name: 'Facebook',   color: '#1877F2' },
  { name: 'YouTube',    color: '#FF0000' },
]

export default function LandingPage() {
  const { isAuthenticated } = useAuth()
  const heroRef = useRef(null)

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  useEffect(() => {
    const el = heroRef.current
    if (!el) return
    const handle = (e) => {
      const { innerWidth: w, innerHeight: h } = window
      const x = (e.clientX / w - 0.5) * 20
      const y = (e.clientY / h - 0.5) * 20
      el.style.setProperty('--px', `${x}px`)
      el.style.setProperty('--py', `${y}px`)
    }
    window.addEventListener('mousemove', handle)
    return () => window.removeEventListener('mousemove', handle)
  }, [])

  return (
    <div className="landing body-bg">
      {/* ── Navbar ── */}
      <nav className="landing-nav">
        <div className="nav-brand">
          <span className="brand-icon">🚀</span>
          <span className="brand-name">SocialPilot</span>
        </div>
        <div className="nav-links">
          <Link to="/login"    className="btn btn-ghost btn-sm">Sign in</Link>
          <Link to="/register" className="btn btn-primary btn-sm">Get started free</Link>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="hero-section" ref={heroRef}>
        <div className="hero-badge">✨ The all-in-one social media command centre</div>

        <h1 className="hero-title">
          Manage. Schedule. Grow.
        </h1>

        <p className="hero-subtitle">
          Pilot your brand's social presence across every platform — all from one beautifully
          designed workspace powered by AI.
        </p>

        <div className="hero-cta">
          <Link to="/register" className="btn btn-primary btn-lg">
            Start for free →
          </Link>
          <Link to="/login" className="btn btn-ghost btn-lg">
            Sign in
          </Link>
        </div>

        {/* Floating platform pills */}
        <div className="platform-orbit">
          {platforms.map((p) => (
            <span key={p.name} className="platform-pill" style={{ '--color': p.color }}>
              {p.name}
            </span>
          ))}
        </div>

        {/* Hero mock card */}
        <div className="hero-card glow-card">
          <div className="mock-topbar">
            <div className="mock-dot red" />
            <div className="mock-dot yellow" />
            <div className="mock-dot green" />
            <span className="mock-title">SocialPilot Dashboard</span>
          </div>
          <div className="mock-body">
            <div className="mock-stat">
              <span className="mock-number gradient-text">1.2M</span>
              <span className="mock-label">Total Reach</span>
            </div>
            <div className="mock-stat">
              <span className="mock-number gradient-text">94K</span>
              <span className="mock-label">Engagements</span>
            </div>
            <div className="mock-stat">
              <span className="mock-number gradient-text">+38%</span>
              <span className="mock-label">Growth</span>
            </div>
          </div>
          <div className="mock-bar-chart">
            {[60, 80, 45, 90, 70, 95, 75].map((h, i) => (
              <div key={i} className="mock-bar" style={{ '--h': `${h}%`, '--i': i }} />
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="features-section">
        <div className="section-header">
          <p className="section-eyebrow">Everything you need</p>
          <h2 className="section-title">Built for <span className="gradient-text">modern brands</span></h2>
          <p className="section-desc">
            From solo creators to enterprise teams — SocialPilot scales with you.
          </p>
        </div>

        <div className="features-grid">
          {features.map((f) => (
            <div key={f.title} className="feature-card glow-card">
              <div className="feature-icon">{f.icon}</div>
              <h3 className="feature-title">{f.title}</h3>
              <p className="feature-desc">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA Strip ── */}
      <section className="cta-section">
        <div className="cta-card glow-card">
          <h2 className="cta-title">Ready to take off?</h2>
          <p className="cta-subtitle">Join thousands of brands already piloting smarter.</p>
          <Link to="/register" className="btn btn-primary btn-lg">
            Create your free account →
          </Link>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="landing-footer">
        <div className="nav-brand">
          <span className="brand-icon">🚀</span>
          <span className="brand-name">SocialPilot</span>
        </div>
        <p className="footer-copy">© 2026 SocialPilot. All rights reserved.</p>
      </footer>
    </div>
  )
}
