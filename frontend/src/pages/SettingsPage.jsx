/**
 * src/pages/SettingsPage.jsx
 * User Settings page: preferences, notifications, timezone, and account actions.
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { authApi } from '../api/authApi'
import api from '../api/authApi'
import AppShell from '../components/AppShell'
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

  const [settings, setSettings] = useState({
    timezone: 'UTC',
    email_notifications: true,
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [successMsg, setSuccessMsg] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  // Tunnel status state
  const [tunnelChecking, setTunnelChecking] = useState(false)
  const [tunnelResult, setTunnelResult] = useState(null)

  const checkTunnel = async () => {
    setTunnelChecking(true)
    setTunnelResult(null)
    try {
      const { data } = await api.get('/media/check-tunnel')
      setTunnelResult(data)
    } catch (err) {
      setTunnelResult({
        reachable: false,
        error: err.response?.data?.detail || err.message || 'Unknown error',
        recommendation: 'Check that the backend is running and you are logged in.',
      })
    } finally {
      setTunnelChecking(false)
    }
  }

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
    <AppShell pageTitle="Settings" pageSubtitle="Configure your preferences and notification controls">

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

            {/* Tunnel Status Diagnostic */}
            <GlowCard className="settings-card" hover={false}>
              <h3 className="section-heading">📡 Media Tunnel Status</h3>
              <p className="section-subheading">
                Verify that your PUBLIC_BASE_URL tunnel is reachable by external platforms
                (Instagram, Pinterest). If the tunnel is down, media posts will fail with
                "Could not fetch media from URI" errors.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <Button
                  variant="outline"
                  size="md"
                  onClick={checkTunnel}
                  loading={tunnelChecking}
                  disabled={tunnelChecking}
                  id="check-tunnel-btn"
                >
                  {tunnelChecking ? 'Checking…' : '🔍 Check Tunnel Connectivity'}
                </Button>

                {tunnelResult && (
                  <div
                    style={{
                      background: tunnelResult.reachable
                        ? 'rgba(16,185,129,0.08)'
                        : 'rgba(239,68,68,0.08)',
                      border: `1px solid ${
                        tunnelResult.reachable ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'
                      }`,
                      borderRadius: '12px',
                      padding: '1rem 1.25rem',
                      fontSize: '0.85rem',
                      lineHeight: '1.6',
                    }}
                  >
                    <div style={{ fontWeight: 700, marginBottom: '0.5rem', fontSize: '0.95rem' }}>
                      {tunnelResult.reachable
                        ? '✅ Tunnel is reachable — Instagram can fetch media'
                        : '❌ Tunnel is NOT reachable — Instagram will fail'}
                    </div>

                    {tunnelResult.configured_base_url && (
                      <div style={{ marginBottom: '0.5rem' }}>
                        <span style={{ opacity: 0.6 }}>Configured URL: </span>
                        <code style={{ fontSize: '0.8rem', wordBreak: 'break-all' }}>
                          {tunnelResult.configured_base_url}
                        </code>
                      </div>
                    )}

                    {tunnelResult.error && (
                      <div
                        style={{
                          color: '#ef4444',
                          background: 'rgba(239,68,68,0.08)',
                          borderRadius: '8px',
                          padding: '0.6rem 0.75rem',
                          marginBottom: '0.75rem',
                          fontFamily: 'monospace',
                          fontSize: '0.8rem',
                        }}
                      >
                        {tunnelResult.error}
                      </div>
                    )}

                    {tunnelResult.recommendation && (
                      <div>
                        <div style={{ fontWeight: 600, marginBottom: '0.4rem', opacity: 0.8 }}>
                          💡 How to fix:
                        </div>
                        <pre
                          style={{
                            background: 'rgba(0,0,0,0.2)',
                            borderRadius: '8px',
                            padding: '0.75rem',
                            overflowX: 'auto',
                            whiteSpace: 'pre-wrap',
                            fontSize: '0.78rem',
                            margin: 0,
                          }}
                        >
                          {tunnelResult.recommendation}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
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
    </AppShell>
  )
}
