/**
 * src/pages/PrivacyPolicyPage.jsx
 * -------------------------------
 * Privacy Policy page for SocialPilot.
 * Accessible publicly for OAuth provider verifications (Pinterest, Google, Meta, X, LinkedIn)
 * and direct user reference.
 */

import { Link } from 'react-router-dom'
import './PrivacyPolicyPage.css'

export default function PrivacyPolicyPage() {
  return (
    <div className="policy-page">
      {/* Navigation header */}
      <header className="policy-nav">
        <Link to="/" className="policy-brand">
          <span className="policy-brand-icon">🚀</span>
          <span className="policy-brand-name">SocialPilot</span>
        </Link>
        <div className="policy-nav-actions">
          <Link to="/" className="btn btn-ghost btn-sm">← Back to Home</Link>
          <Link to="/login" className="btn btn-primary btn-sm">Sign In</Link>
        </div>
      </header>

      {/* Policy Content Container */}
      <main className="policy-container">
        <div className="policy-card glow-card">
          <div className="policy-badge">Legal Documentation</div>
          <h1 className="policy-title">Privacy Policy</h1>
          <p className="policy-updated">Last Updated: September 2026</p>

          <div className="policy-content">
            <section className="policy-section">
              <p>
                SocialPilot is a social media management application developed for authorized users.
              </p>
            </section>

            <section className="policy-section">
              <h2>Account Authentication & OAuth Security</h2>
              <p>
                SocialPilot uses OAuth authentication to connect users&apos; social media accounts. SocialPilot does not collect or store users&apos; social media passwords.
              </p>
            </section>

            <section className="policy-section">
              <h2>Platform Integration & Data Access (Pinterest)</h2>
              <p>
                When a user connects Pinterest, SocialPilot may access information authorized by the user through Pinterest OAuth, such as account and content information required for the application&apos;s functionality.
              </p>
            </section>

            <section className="policy-section">
              <h2>Token Encryption & Confidentiality</h2>
              <p>
                OAuth access tokens are securely stored and are not exposed to the frontend.
              </p>
            </section>

            <section className="policy-section">
              <h2>Account Control & Disconnection</h2>
              <p>
                Users can disconnect their Pinterest account from SocialPilot at any time.
              </p>
            </section>

            <section className="policy-section policy-contact-section">
              <h2>Contact Us</h2>
              <p>
                For questions regarding this Privacy Policy, please contact:{' '}
                <a href="mailto:govind12022004@gmail.com" className="policy-email-link">
                  govind12022004@gmail.com
                </a>
              </p>
            </section>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="policy-footer">
        <p>© 2026 SocialPilot. All rights reserved.</p>
        <div className="policy-footer-links">
          <Link to="/" className="policy-footer-link">Home</Link>
          <Link to="/privacy" className="policy-footer-link active">Privacy Policy</Link>
          <Link to="/login" className="policy-footer-link">Dashboard</Link>
        </div>
      </footer>
    </div>
  )
}
