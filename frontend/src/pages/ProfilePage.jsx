/**
 * src/pages/ProfilePage.jsx
 * -------------------------
 * User Profile view & edit page.
 * Allows editing full_name; security & RBAC fields (role, email, status) are read-only.
 */

import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import Sidebar from '../components/Sidebar'
import './ProfilePage.css'

export default function ProfilePage() {
  const { user, updateProfile } = useAuth()
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [saving, setSaving] = useState(false)
  const [successMsg, setSuccessMsg] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const [mobileNav, setMobileNav] = useState(false)

  const handleSave = async (e) => {
    e.preventDefault()
    if (!fullName.trim() || fullName.trim().length < 2) {
      setErrorMsg('Full name must be at least 2 characters.')
      return
    }

    setSaving(true)
    setErrorMsg('')
    setSuccessMsg('')

    const result = await updateProfile({ full_name: fullName.trim() })
    setSaving(false)

    if (result.success) {
      setSuccessMsg('Profile updated successfully!')
      setTimeout(() => setSuccessMsg(''), 4000)
    } else {
      setErrorMsg(result.message)
    }
  }

  const initials = user?.full_name
    ? user.full_name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
    : 'U'

  const formattedRole = (user?.role || 'content_creator')
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')

  const joinDate = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
    : '—'

  return (
    <div className="app-layout">
      <div className="orb orb-1" />
      <div className="orb orb-2" />

      <Sidebar mobileOpen={mobileNav} onCloseMobile={() => setMobileNav(false)} />

      <main className="app-main">
        {/* Top Header */}
        <header className="page-header">
          <div className="header-left">
            <button className="mobile-toggle" onClick={() => setMobileNav(true)} aria-label="Open menu">
              ☰
            </button>
            <div>
              <h1 className="page-title">Profile</h1>
              <p className="page-subtitle">Manage your personal account details and public identity.</p>
            </div>
          </div>
        </header>

        <div className="profile-grid">
          {/* Profile Overview Card */}
          <div className="glass-card profile-badge-card">
            <div className="profile-hero-avatar">{initials}</div>
            <h2 className="profile-hero-name">{user?.full_name}</h2>
            <p className="profile-hero-email">{user?.email}</p>

            <div className="role-pill-large">
              <span className="role-dot" />
              <span>{formattedRole}</span>
            </div>

            <div className="profile-quick-stats">
              <div className="stat-row">
                <span className="stat-lbl">Account Status</span>
                <span className="stat-val status-active">
                  {user?.is_active ? '● Active' : '○ Inactive'}
                </span>
              </div>
              <div className="stat-row">
                <span className="stat-lbl">Member Since</span>
                <span className="stat-val">{joinDate}</span>
              </div>
              <div className="stat-row">
                <span className="stat-lbl">User ID</span>
                <span className="stat-val id-snippet" title={user?.id}>
                  {user?.id ? `${user.id.slice(0, 8)}...` : '—'}
                </span>
              </div>
            </div>
          </div>

          {/* Edit Form */}
          <div className="glass-card profile-form-card">
            <h3 className="section-heading">Account Information</h3>
            <p className="section-subheading">Update your display information. Security fields are protected.</p>

            {successMsg && (
              <div className="alert alert-success" role="alert">
                <span>✓</span>
                <span>{successMsg}</span>
              </div>
            )}

            {errorMsg && (
              <div className="alert alert-error" role="alert">
                <span>⚠️</span>
                <span>{errorMsg}</span>
              </div>
            )}

            <form onSubmit={handleSave} className="profile-form">
              <div className="form-group">
                <label className="form-label" htmlFor="profile-fullname">
                  Full Name <span className="label-mutable">(Editable)</span>
                </label>
                <input
                  id="profile-fullname"
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="form-input"
                  placeholder="Your full name"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="profile-email">
                  Email Address <span className="label-locked">🔒 Read-only</span>
                </label>
                <input
                  id="profile-email"
                  type="email"
                  value={user?.email ?? ''}
                  disabled
                  className="form-input disabled"
                />
                <span className="field-hint">Email cannot be changed directly for security reasons.</span>
              </div>

              <div className="form-group">
                <label className="form-label">
                  Assigned RBAC Role <span className="label-locked">🔒 System Assigned</span>
                </label>
                <input
                  type="text"
                  value={formattedRole}
                  disabled
                  className="form-input disabled"
                />
                <span className="field-hint">
                  Your role is determined by workspace membership and administrator authorization.
                </span>
              </div>

              <div className="form-actions">
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={saving || fullName.trim() === (user?.full_name ?? '')}
                >
                  {saving ? 'Saving changes…' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      </main>
    </div>
  )
}
