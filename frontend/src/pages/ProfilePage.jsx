/**
 * src/pages/ProfilePage.jsx
 * User Profile view & edit page.
 * Allows editing full_name; security & RBAC fields (role, email, status) are read-only.
 */

import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import Sidebar from '../components/Sidebar'
import Navbar from '../components/Navbar'
import Input from '../components/ui/Input'
import Button from '../components/ui/Button'
import GlowCard from '../components/ui/GlowCard'
import ErrorMessage from '../components/ui/ErrorMessage'
import './ProfilePage.css'

export default function ProfilePage() {
  const { user, updateProfile } = useAuth()
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [saving, setSaving] = useState(false)
  const [successMsg, setSuccessMsg] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const [mobileNav, setMobileNav] = useState(false)
  const [nameError, setNameError] = useState('')

  const handleSave = async (e) => {
    e.preventDefault()
    if (!fullName.trim() || fullName.trim().length < 2) {
      setNameError('Full name must be at least 2 characters.')
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

  const handleNameChange = (e) => {
    setFullName(e.target.value)
    if (nameError) setNameError('')
    if (errorMsg) setErrorMsg('')
  }

  const initials = user?.full_name
    ? user.full_name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
    : 'U'

  const formattedRole = (user?.role || 'content_creator')
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')

  const joinDate = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
    : '—'

  return (
    <div className="app-layout body-bg">
      <Sidebar mobileOpen={mobileNav} onCloseMobile={() => setMobileNav(false)} />

      <main className="app-main">
        <Navbar
          pageTitle="Profile"
          pageSubtitle="Manage your personal account details and public identity."
          mobileMenuLabel="Open menu"
          onMobileMenu={() => setMobileNav(true)}
        />

        <div className="profile-grid">
          {/* Profile Overview Card */}
          <GlowCard className="profile-badge-card" hover={false}>
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
          </GlowCard>

          {/* Edit Form */}
          <GlowCard className="profile-form-card" hover={false}>
            <h3 className="section-heading">Account Information</h3>
            <p className="section-subheading">Update your display information. Security fields are protected.</p>

            {successMsg && (
              <div className="alert alert-success" role="alert">
                <span>✓</span>
                <span>{successMsg}</span>
              </div>
            )}

            {errorMsg && <ErrorMessage message={errorMsg} />}

            <form onSubmit={handleSave} className="profile-form">
              <Input
                id="profile-fullname"
                name="fullName"
                label="Full Name"
                type="text"
                value={fullName}
                onChange={handleNameChange}
                error={nameError}
                hint="This is your public display name."
                required
                autoComplete="name"
              />

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
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  loading={saving}
                  disabled={saving || fullName.trim() === (user?.full_name ?? '')}
                >
                  {saving ? 'Saving…' : 'Save Changes'}
                </Button>
              </div>
            </form>
          </GlowCard>
        </div>
      </main>
    </div>
  )
}
