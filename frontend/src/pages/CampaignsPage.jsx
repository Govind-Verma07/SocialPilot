/**
 * src/pages/CampaignsPage.jsx
 * ----------------------------
 * Campaign Management & Performance Tracking Module.
 * Features Target Social Accounts list with "Select All" option,
 * Campaign Objectives with "Other (Custom)" option, and standard Date & Time selection.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import GlowCard from '../components/ui/GlowCard'
import Button from '../components/ui/Button'
import StatusBadge from '../components/ui/StatusBadge'
import EmptyState from '../components/ui/EmptyState'
import './CampaignsPage.css'

const ALL_PLATFORMS = [
  { id: 'facebook', label: 'Facebook Pages', icon: '📘' },
  { id: 'instagram', label: 'Instagram Business', icon: '📸' },
  { id: 'linkedin', label: 'LinkedIn Company', icon: '💼' },
  { id: 'x', label: 'X (Twitter)', icon: '𝕏' },
  { id: 'youtube', label: 'YouTube Channel', icon: '▶️' },
  { id: 'pinterest', label: 'Pinterest Board', icon: '📌' },
]

const INITIAL_CAMPAIGNS = [
  {
    id: 'cmp-1',
    name: 'Q3 Product Awareness & Growth',
    platform: 'Multi-Platform (FB, IG, LinkedIn)',
    startDate: '2026-09-01',
    endDate: '2026-09-30',
    budget: '$2,500',
    objective: 'Brand Awareness & Engagement',
    status: 'active',
    reach: '45.2K',
    conversions: '1,240',
    roi: '+240%',
  },
  {
    id: 'cmp-2',
    name: 'Fall Influencer & Creator Showcase',
    platform: 'Instagram & YouTube',
    startDate: '2026-09-10',
    endDate: '2026-10-15',
    budget: '$4,000',
    objective: 'Lead Generation & Conversions',
    status: 'scheduled',
    reach: '—',
    conversions: '—',
    roi: 'Pending',
  },
  {
    id: 'cmp-3',
    name: 'SMB Founder Masterclass Webinar',
    platform: 'LinkedIn & X (Twitter)',
    startDate: '2026-08-15',
    endDate: '2026-08-30',
    budget: '$1,200',
    objective: 'Webinar Registrations',
    status: 'completed',
    reach: '28.9K',
    conversions: '890',
    roi: '+185%',
  },
]

export default function CampaignsPage() {
  const navigate = useNavigate()
  const [campaigns, setCampaigns] = useState(INITIAL_CAMPAIGNS)
  const [showCreateModal, setShowCreateModal] = useState(false)

  const handleDeleteCampaign = (campaignId) => {
    setCampaigns((prev) => prev.filter((c) => c.id !== campaignId))
  }

  // Selected Social Media Accounts (default: all)
  const [selectedPlatforms, setSelectedPlatforms] = useState(ALL_PLATFORMS.map((p) => p.id))
  
  // Custom Platform / Objective "Other" state
  const [objectiveOption, setObjectiveOption] = useState('Brand Awareness')
  const [customObjective, setCustomObjective] = useState('')
  const [platformOption, setPlatformOption] = useState('multi') // 'multi' or 'other'
  const [customPlatform, setCustomPlatform] = useState('')

  // New Campaign Form State
  const [form, setForm] = useState({
    name: '',
    startDate: '2026-09-01',
    endDate: '2026-09-30',
    budget: '$1,000',
  })

  // Select All Social Media Accounts Handler
  const isAllSelected = selectedPlatforms.length === ALL_PLATFORMS.length

  const handleToggleSelectAll = () => {
    if (isAllSelected) {
      setSelectedPlatforms([])
    } else {
      setSelectedPlatforms(ALL_PLATFORMS.map((p) => p.id))
    }
  }

  const handleTogglePlatform = (id) => {
    setSelectedPlatforms((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    )
  }

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleCreateCampaign = (e) => {
    e.preventDefault()
    if (!form.name.trim()) return

    // Resolve objective text
    const finalObjective =
      objectiveOption === 'Other'
        ? customObjective.trim() || 'Custom Objective'
        : objectiveOption

    // Resolve platform text
    let finalPlatform = ''
    if (platformOption === 'Other') {
      finalPlatform = customPlatform.trim() || 'Custom Channels'
    } else if (selectedPlatforms.length === ALL_PLATFORMS.length) {
      finalPlatform = 'All 6 Social Platforms'
    } else if (selectedPlatforms.length === 0) {
      finalPlatform = 'Custom Platform Selection'
    } else {
      finalPlatform = selectedPlatforms
        .map((id) => ALL_PLATFORMS.find((p) => p.id === id)?.label.split(' ')[0])
        .join(', ')
    }

    const newCampaign = {
      id: `cmp-${Date.now()}`,
      name: form.name.trim(),
      platform: finalPlatform,
      startDate: form.startDate,
      endDate: form.endDate,
      budget: form.budget.startsWith('$') ? form.budget : `$${form.budget}`,
      objective: finalObjective,
      status: 'active',
      reach: '0',
      conversions: '0',
      roi: '0%',
    }

    setCampaigns([newCampaign, ...campaigns])
    setForm({ name: '', startDate: '2026-09-01', endDate: '2026-09-30', budget: '$1,000' })
    setObjectiveOption('Brand Awareness')
    setCustomObjective('')
    setPlatformOption('multi')
    setCustomPlatform('')
    setShowCreateModal(false)
  }

  return (
    <AppShell pageTitle="Campaigns" pageSubtitle="Create, track, and monitor social campaign objectives and performance">
        {/* Top Header Row */}
        <div className="campaigns-top-bar">
          <div>
            <h2 className="section-heading">Active & Scheduled Campaigns</h2>
            <p className="section-subheading" style={{ marginBottom: 0 }}>
              Group content into targeted campaigns across all connected social channels.
            </p>
          </div>
          <Button variant="primary" onClick={() => setShowCreateModal(!showCreateModal)}>
            {showCreateModal ? '✕ Cancel' : '+ Create Campaign'}
          </Button>
        </div>

        {/* Create Campaign Form Card */}
        {showCreateModal && (
          <GlowCard style={{ padding: '28px' }} hover>
            <h3 className="section-heading">Launch New Campaign</h3>
            <form onSubmit={handleCreateCampaign} style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginTop: '16px' }}>
              {/* Campaign Name */}
              <div className="form-group">
                <label className="form-label">Campaign Name</label>
                <input
                  type="text"
                  name="name"
                  className="form-input"
                  placeholder="e.g. Q4 Black Friday Promo"
                  value={form.name}
                  onChange={handleChange}
                  required
                />
              </div>

              {/* Social Media Account Selection List with SELECT ALL */}
              <div className="form-group">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <label className="form-label">Select Social Media Accounts / Channels</label>
                  <button
                    type="button"
                    onClick={handleToggleSelectAll}
                    style={{
                      background: 'rgba(124, 58, 237, 0.15)',
                      border: '1px solid rgba(124, 58, 237, 0.4)',
                      color: '#c084fc',
                      padding: '4px 12px',
                      borderRadius: '8px',
                      fontSize: '12px',
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    {isAllSelected ? '✓ Unselect All' : '☐ Select All (All 6 Platforms)'}
                  </button>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
                  {ALL_PLATFORMS.map((p) => {
                    const isChecked = selectedPlatforms.includes(p.id)
                    return (
                      <div
                        key={p.id}
                        onClick={() => handleTogglePlatform(p.id)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          padding: '10px 14px',
                          borderRadius: '10px',
                          background: isChecked ? 'rgba(124, 58, 237, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                          border: isChecked ? '1px solid #a855f7' : '1px solid rgba(255, 255, 255, 0.08)',
                          color: isChecked ? '#ffffff' : '#94a3b8',
                          cursor: 'pointer',
                          fontSize: '13px',
                          fontWeight: 600,
                          transition: 'all 0.2s',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => {}} // handled by parent onClick
                          style={{ accentColor: '#a855f7', width: '16px', height: '16px' }}
                        />
                        <span>{p.icon}</span>
                        <span>{p.label}</span>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Target Platform Option (Preset or Other) */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label className="form-label">Platform Grouping / Option</label>
                  <select
                    className="form-input form-select"
                    value={platformOption}
                    onChange={(e) => setPlatformOption(e.target.value)}
                  >
                    <option value="multi">Selected Social Media Accounts ({selectedPlatforms.length})</option>
                    <option value="Other">Other (Write Custom Channels...)</option>
                  </select>

                  {platformOption === 'Other' && (
                    <input
                      type="text"
                      className="form-input"
                      style={{ marginTop: '8px' }}
                      placeholder="Write custom channels (e.g. TikTok, WhatsApp, Threads)..."
                      value={customPlatform}
                      onChange={(e) => setCustomPlatform(e.target.value)}
                      required
                    />
                  )}
                </div>

                {/* Campaign Objective with "Other" option */}
                <div className="form-group">
                  <label className="form-label">Campaign Objective</label>
                  <select
                    className="form-input form-select"
                    value={objectiveOption}
                    onChange={(e) => setObjectiveOption(e.target.value)}
                  >
                    <option value="Brand Awareness">Brand Awareness</option>
                    <option value="Lead Generation & Signups">Lead Generation & Signups</option>
                    <option value="Website Traffic & Sales">Website Traffic & Sales</option>
                    <option value="Audience Engagement">Audience Engagement</option>
                    <option value="Other">Other (Write Custom Objective...)</option>
                  </select>

                  {objectiveOption === 'Other' && (
                    <input
                      type="text"
                      className="form-input"
                      style={{ marginTop: '8px' }}
                      placeholder="Write your custom objective (e.g. Mobile App Installs)..."
                      value={customObjective}
                      onChange={(e) => setCustomObjective(e.target.value)}
                      required
                    />
                  )}
                </div>
              </div>

              {/* Standard Date Selection */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label className="form-label">Start Date 📅</label>
                  <input
                    type="date"
                    name="startDate"
                    className="form-input"
                    value={form.startDate}
                    onChange={handleChange}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">End Date 📅</label>
                  <input
                    type="date"
                    name="endDate"
                    className="form-input"
                    value={form.endDate}
                    onChange={handleChange}
                    required
                  />
                </div>
              </div>

              {/* Campaign Budget */}
              <div className="form-group">
                <label className="form-label">Campaign Budget ($ USD)</label>
                <input
                  type="text"
                  name="budget"
                  className="form-input"
                  placeholder="$2,500"
                  value={form.budget}
                  onChange={handleChange}
                  required
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '8px' }}>
                <Button type="button" variant="ghost" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary">
                  Save & Launch Campaign 🚀
                </Button>
              </div>
            </form>
          </GlowCard>
        )}

        {/* Campaigns Grid List */}
        {campaigns.length === 0 ? (
          <EmptyState
            icon="🎯"
            title="No campaigns created"
            description="Organize your posts into campaigns to track ROI, budget, and performance."
            actionLabel="Create First Campaign"
            onAction={() => setShowCreateModal(true)}
            size="md"
          />
        ) : (
          <div className="campaigns-grid">
            {campaigns.map((cmp) => (
              <GlowCard key={cmp.id} className="campaign-card" hover>
                <div className="campaign-card-header">
                  <div>
                    <div className="campaign-title">{cmp.name}</div>
                    <span className="campaign-platform-badge">{cmp.platform}</span>
                  </div>
                  <StatusBadge
                    status={cmp.status === 'active' ? 'success' : cmp.status === 'completed' ? 'info' : 'warning'}
                    label={cmp.status}
                    showDot
                  />
                </div>

                <div className="campaign-details-list">
                  <div className="campaign-detail-row">
                    <span className="campaign-detail-lbl">Objective</span>
                    <span className="campaign-detail-val">{cmp.objective}</span>
                  </div>
                  <div className="campaign-detail-row">
                    <span className="campaign-detail-lbl">Duration</span>
                    <span className="campaign-detail-val">{cmp.startDate} → {cmp.endDate}</span>
                  </div>
                  <div className="campaign-detail-row">
                    <span className="campaign-detail-lbl">Budget</span>
                    <span className="campaign-detail-val" style={{ color: '#10b981' }}>{cmp.budget}</span>
                  </div>
                </div>

                {/* Metrics */}
                <div className="campaign-metrics-row">
                  <div className="campaign-metric-box">
                    <span className="metric-num">{cmp.reach}</span>
                    <span className="metric-txt">Reach</span>
                  </div>
                  <div className="campaign-metric-box">
                    <span className="metric-num">{cmp.conversions}</span>
                    <span className="metric-txt">Conversions</span>
                  </div>
                  <div className="campaign-metric-box">
                    <span className="metric-num" style={{ color: '#c084fc' }}>{cmp.roi}</span>
                    <span className="metric-txt">ROI</span>
                  </div>
                </div>

                {/* Campaign Actions */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '12px', borderTop: '1px solid rgba(255, 255, 255, 0.06)', marginTop: '4px' }}>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => navigate('/posts?tab=create')}
                    title="Schedule a post for this campaign"
                  >
                    + Schedule Post
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteCampaign(cmp.id)}
                    style={{ color: '#ef4444', padding: '4px 8px' }}
                    title="Delete this campaign"
                  >
                    🗑️ Delete
                  </Button>
                </div>
              </GlowCard>
            ))}
          </div>
        )}
    </AppShell>
  )
}
