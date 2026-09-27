/**
 * src/pages/SettingsPage.jsx
 * --------------------------
 * User Settings page: Timezone, Notification Preferences Matrix (In-App & Real Email),
 * SMTP Test Email Verification, Tunnel Diagnostic, and Account Security.
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { authApi } from '../api/authApi'
import notificationsApi from '../api/notificationsApi'
import api from '../api/authApi'
import AppShell from '../components/AppShell'
import Button from '../components/ui/Button'
import GlowCard from '../components/ui/GlowCard'
import LoadingState from '../components/ui/LoadingState'
import ErrorMessage from '../components/ui/ErrorMessage'
import {
  Bell, Mail, Send, CheckCircle2, AlertCircle, Shield,
  Radio, CheckCheck, Megaphone, Calendar, Clock,
} from 'lucide-react'
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

const NOTIF_CATEGORIES = [
  {
    key: 'post_published',
    label: 'Post Published',
    desc: 'When your scheduled post is successfully published to a social network.',
    icon: CheckCircle2,
    color: '#10b981',
  },
  {
    key: 'post_failed',
    label: 'Post Publishing Failed',
    desc: 'When an automated publishing attempt encounters a permanent failure.',
    icon: AlertCircle,
    color: '#ef4444',
  },
  {
    key: 'scheduled_reminder',
    label: 'Scheduled Post Reminder',
    desc: 'Advance notification ~30 minutes before your post is scheduled to publish.',
    icon: Clock,
    color: '#f59e0b',
  },
  {
    key: 'campaign_event',
    label: 'Campaign Updates',
    desc: 'When a campaign is created, milestones update, or deliverables complete.',
    icon: Megaphone,
    color: '#8b5cf6',
  },
  {
    key: 'account_issue',
    label: 'Social Account Issues',
    desc: 'When token expiration, connection loss, or permission issues occur.',
    icon: Shield,
    color: '#f97316',
  },
  {
    key: 'system_alert',
    label: 'System & Maintenance Alerts',
    desc: 'Important service updates and operational notifications.',
    icon: Bell,
    color: '#6366f1',
  },
]

export default function SettingsPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [settings, setSettings] = useState({
    timezone: 'UTC',
    email_notifications: true,
  })

  // Notification Preferences Matrix
  const [notifPrefs, setNotifPrefs] = useState({
    post_published: { in_app: true, email: true },
    post_failed: { in_app: true, email: true },
    post_scheduled: { in_app: true, email: true },
    scheduled_reminder: { in_app: true, email: true },
    campaign_event: { in_app: true, email: true },
    account_issue: { in_app: true, email: true },
    system_alert: { in_app: true, email: true },
  })

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [successMsg, setSuccessMsg] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  // Test Email state
  const [testEmailSending, setTestEmailSending] = useState(false)
  const [testEmailResult, setTestEmailResult] = useState(null)

  // Tunnel status state
  const [tunnelChecking, setTunnelChecking] = useState(false)
  const [tunnelResult, setTunnelResult] = useState(null)

  useEffect(() => {
    Promise.all([
      authApi.getSettings(),
      notificationsApi.getPreferences().catch(() => ({ data: null })),
    ])
      .then(([settingsRes, prefsRes]) => {
        if (settingsRes?.data) {
          setSettings({
            timezone: settingsRes.data.timezone || 'UTC',
            email_notifications: settingsRes.data.email_notifications ?? true,
          })
        }
        if (prefsRes?.data?.preferences) {
          setNotifPrefs((prev) => ({
            ...prev,
            ...prefsRes.data.preferences,
          }))
          if (prefsRes.data.email_notifications !== undefined) {
            setSettings((s) => ({ ...s, email_notifications: prefsRes.data.email_notifications }))
          }
        }
      })
      .catch((err) => {
        console.error('Failed to load settings', err)
      })
      .finally(() => setLoading(false))
  }, [])

  const handleTogglePreference = (categoryKey, channel) => {
    setNotifPrefs((prev) => ({
      ...prev,
      [categoryKey]: {
        ...prev[categoryKey],
        [channel]: !prev[categoryKey]?.[channel],
      },
    }))
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErrorMsg('')
    setSuccessMsg('')

    try {
      // 1. Update general user settings
      const { data: updatedSettings } = await authApi.updateSettings(settings)
      setSettings({
        timezone: updatedSettings.timezone,
        email_notifications: updatedSettings.email_notifications,
      })

      // 2. Update granular notification preferences
      await notificationsApi.updatePreferences({
        email_notifications: settings.email_notifications,
        preferences: notifPrefs,
      })

      setSuccessMsg('Settings and notification preferences saved successfully!')
      setTimeout(() => setSuccessMsg(''), 4000)
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to save settings.')
    } finally {
      setSaving(false)
    }
  }

  const handleSendTestEmail = async () => {
    setTestEmailSending(true)
    setTestEmailResult(null)
    try {
      const { data } = await notificationsApi.sendTestEmail()
      setTestEmailResult(data)
    } catch (err) {
      setTestEmailResult({
        success: false,
        message: err.response?.data?.detail || err.message || 'Failed to send test email',
        recipient: user?.email,
        smtp_host: 'Error during connection',
      })
    } finally {
      setTestEmailSending(false)
    }
  }

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

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  const formattedRole = (user?.role || 'content_creator')
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')

  return (
    <AppShell pageTitle="Settings" pageSubtitle="Preferences, Real Email controls, and notification triggers">
      {loading ? (
        <LoadingState message="Loading preferences…" size="lg" />
      ) : (
        <div className="settings-container">
          {successMsg && (
            <div className="alert alert-success" role="alert">
              <span>✓</span>
              <span>{successMsg}</span>
            </div>
          )}

          {errorMsg && <ErrorMessage message={errorMsg} />}

          {/* Form wrapper */}
          <form onSubmit={handleSave} className="settings-form">
            {/* General Preferences */}
            <GlowCard className="settings-card" hover={false}>
              <h3 className="section-heading">General Preferences</h3>
              <p className="section-subheading">Manage your timezone and workspace defaults.</p>

              <div className="form-group" style={{ marginTop: '16px' }}>
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
                  Used for all publishing schedules, recurring time rules, and reminder events.
                </span>
              </div>
            </GlowCard>

            {/* Notification Channels & Granular Matrix */}
            <GlowCard className="settings-card" hover={false}>
              <div className="notif-card-header">
                <div>
                  <h3 className="section-heading">🔔 Notification Channels & Preferences</h3>
                  <p className="section-subheading">
                    Control which events trigger in-app bell notifications and real-time emails to <strong>{user?.email}</strong>.
                  </p>
                </div>
              </div>

              {/* Master Email Switch */}
              <div className="setting-toggle-row master-toggle">
                <div className="toggle-info">
                  <span className="toggle-label" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Mail size={16} color="#6366f1" />
                    <span>Master Email Notifications Switch</span>
                  </span>
                  <span className="toggle-desc">
                    Enable or disable all outgoing email notifications across your account.
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

              {/* Granular Preference Matrix Table */}
              <div className="notif-matrix-wrapper">
                <div className="notif-matrix-header">
                  <span className="matrix-col-event">Event Category</span>
                  <span className="matrix-col-channel">In-App 🔔</span>
                  <span className="matrix-col-channel">Email 📧</span>
                </div>

                <div className="notif-matrix-body">
                  {NOTIF_CATEGORIES.map((cat) => {
                    const Icon = cat.icon
                    const pref = notifPrefs[cat.key] || { in_app: true, email: true }
                    return (
                      <div key={cat.key} className="notif-matrix-row">
                        <div className="notif-matrix-event-info">
                          <div className="event-icon-badge" style={{ background: `${cat.color}15`, color: cat.color }}>
                            <Icon size={16} />
                          </div>
                          <div>
                            <div className="event-name">{cat.label}</div>
                            <div className="event-desc">{cat.desc}</div>
                          </div>
                        </div>

                        <div className="notif-matrix-col">
                          <label className="checkbox-custom">
                            <input
                              type="checkbox"
                              checked={pref.in_app ?? true}
                              onChange={() => handleTogglePreference(cat.key, 'in_app')}
                            />
                            <span className="checkbox-mark" />
                          </label>
                        </div>

                        <div className="notif-matrix-col">
                          <label className="checkbox-custom">
                            <input
                              type="checkbox"
                              checked={(pref.email ?? true) && settings.email_notifications}
                              disabled={!settings.email_notifications}
                              onChange={() => handleTogglePreference(cat.key, 'email')}
                            />
                            <span className="checkbox-mark" />
                          </label>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              <div className="form-actions" style={{ marginTop: '24px' }}>
                <Button type="submit" variant="primary" size="md" loading={saving} disabled={saving}>
                  {saving ? 'Saving Preferences…' : 'Save Notification Preferences'}
                </Button>
              </div>
            </GlowCard>
          </form>

          {/* Test Email Verification */}
          <GlowCard className="settings-card" hover={false}>
            <h3 className="section-heading">📧 SMTP Real Email Verification</h3>
            <p className="section-subheading">
              Verify your SMTP server / Gmail App Password connection by sending a real test email to <strong>{user?.email}</strong>.
            </p>

            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <Button
                  variant="outline"
                  size="md"
                  onClick={handleSendTestEmail}
                  loading={testEmailSending}
                  disabled={testEmailSending}
                  id="send-test-email-btn"
                >
                  <Send size={14} style={{ marginRight: '6px' }} />
                  {testEmailSending ? 'Sending Test Email…' : 'Send Test Email Now'}
                </Button>
              </div>

              {testEmailResult && (
                <div
                  className={`test-email-result-box ${testEmailResult.success ? 'success' : 'failed'}`}
                >
                  <div className="test-email-result-header">
                    {testEmailResult.success ? (
                      <span style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
                        <CheckCircle2 size={16} /> SMTP Delivery Successful!
                      </span>
                    ) : (
                      <span style={{ color: '#ef4444', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
                        <AlertCircle size={16} /> SMTP Delivery Failed
                      </span>
                    )}
                  </div>
                  <p className="test-email-result-msg">{testEmailResult.message}</p>
                  <div className="test-email-meta">
                    <span><strong>Recipient:</strong> {testEmailResult.recipient}</span>
                    <span><strong>SMTP Host:</strong> {testEmailResult.smtp_host}</span>
                  </div>
                </div>
              )}
            </div>
          </GlowCard>

          {/* Tunnel Status Diagnostic */}
          <GlowCard className="settings-card" hover={false}>
            <h3 className="section-heading">📡 Media Tunnel Status</h3>
            <p className="section-subheading">
              Verify that your PUBLIC_BASE_URL tunnel is reachable by external platforms (Instagram, Pinterest).
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '16px' }}>
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
                    background: tunnelResult.reachable ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
                    border: `1px solid ${tunnelResult.reachable ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
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
