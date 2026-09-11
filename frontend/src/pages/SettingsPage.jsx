/**
 * src/pages/SettingsPage.jsx
 * User Settings page: preferences, notifications, timezone, and account actions.
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { authApi } from '../api/authApi'
import Sidebar from '../components/Sidebar'
import Navbar from '../components/Navbar'
import Button from '../components/ui/Button'
import GlowCard from '../components/ui/GlowCard'
import LoadingState from '../components/ui/LoadingState'
import ErrorMessage from '../components/ui/ErrorMessage'
import './SettingsPage.css'

const TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Asia/Dubai',
  'Asia/Kolkata',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Australia/Sydney',
]

export default function SettingsPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [mobileNav, setMobileNav] = useState(false)

  const [settings, setSettings] = useState({
    timezone: 'UTC',
    email_notifications: true,
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [successMsg, setSuccessMsg] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    authApi.getSettings()
      .then(({ data }) => {
        setSettings({
          timezone: data.timezone || 'UTC',
          email_notifications: data.email_notifications ?? true,
        })
      })
      .catch((err) => {
        console.error('Failed to load settings', err)
      })
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErrorMsg('')
    setSuccessMsg('')

    try {
      const { data } = await authApi.updateSettings(settings)
      setSettings({
        timezone: data.timezone,
        email_notifications: data.email_notifications,
      })
      setSuccessMsg('Settings saved successfully!')
      setTimeout(() => setSuccessMsg(''), 4000)
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to save settings.')
    } finally {
      setSaving(false)
    }
  }

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  const formattedRole = (user?.role || 'content_creator')
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')

  return (
    <div className="app-layout body-bg">
      <Sidebar mobileOpen={mobileNav} onCloseMobile={() => setMobileNav(false)} />

      <main className="app-main">
        <Navbar
          pageTitle="Settings"
          pageSubtitle="Configure application preferences and notification controls."
          mobileMenuLabel="Open menu"
          onMobileMenu={() => setMobileNav(true)}
        />

        {loading ? (
          <LoadingState message="Loading preferences…" size="lg" />
        ) : (
          <div className="settings-container">
            {/* Preferences Form */}
            <GlowCard className="settings-card" hover={false}>
              <h3 className="section-heading">Preferences</h3>
              <p className="section-subheading">Manage your timezone and alerts.</p>

              {successMsg && (
                <div className="alert alert-success" role="alert">
                  <span>✓</span>
                  <span>{successMsg}</span>
                </div>
              )}

              {errorMsg && <ErrorMessage message={errorMsg} />}

              <form onSubmit={handleSave} className="settings-form">
                <div className="form-group">
                  <label className="form-label" htmlFor="settings-tz">
                    Default Timezone
                  </label>
                  <select
                    id="settings-tz"
                    value={settings.timezone}
                    onChange={(e) => setSettings({ ...settings, timezone: e.target.value })}
                    className="form-input form-select"
                  >
                    {TIMEZONES.map((tz) => (
                      <option key={tz} value={tz}>
                        {tz}
                      </option>
                    ))}
                  </select>
                  <span className="field-hint">
                    Used for all publishing schedules and account sync timestamps.
                  </span>
                </div>

                <div className="setting-toggle-row">
                  <div className="toggle-info">
                    <span className="toggle-label">Email Notifications</span>
                    <span className="toggle-desc">
                      Receive email alerts regarding social account disconnections or sync issues.
                    </span>
                  </div>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={settings.email_notifications}
                      onChange={(e) => setSettings({ ...settings, email_notifications: e.target.checked })}
                    />
                    <span className="slider round" />
                  </label>
                </div>

                <div className="form-actions">
                  <Button type="submit" variant="primary" size="md" loading={saving} disabled={saving}>
                    {saving ? 'Saving…' : 'Save Preferences'}
                  </Button>
                </div>
              </form>
            </GlowCard>

            {/* Account Info & Security */}
            <GlowCard className="settings-card" hover={false}>
              <h3 className="section-heading">Account & Security</h3>
              <p className="section-subheading">Account identity and session controls.</p>

              <div className="account-summary-box">
                <div className="as-item">
                  <span className="as-label">Signed in as</span>
                  <span className="as-value">{user?.email}</span>
                </div>
                <div className="as-item">
                  <span className="as-label">Role</span>
                  <span className="as-value role-tag">{formattedRole}</span>
                </div>
                <div className="as-item">
                  <span className="as-label">Account Status</span>
                  <span className="as-value status-active">● Active</span>
                </div>
              </div>

              <div className="danger-zone">
                <div className="danger-info">
                  <span className="danger-title">Sign out of SocialPilot</span>
                  <span className="danger-desc">End your active session on this browser.</span>
                </div>
                <Button variant="outline" size="md" onClick={handleLogout}>
                  Sign Out
                </Button>
              </div>
            </GlowCard>
          </div>
        )}
      </main>
    </div>
  )
}
