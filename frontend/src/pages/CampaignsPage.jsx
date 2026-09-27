/**
 * src/pages/CampaignsPage.jsx
 * ----------------------------
 * Milestone 3: Production-Ready Campaign Management & Tracking Module.
 * Fully integrated with backend API for authenticated CRUD, post association,
 * real execution progress, financial tracking, and transparent ROI calculation.
 */

import { useState, useEffect, useCallback } from 'react'
import AppShell from '../components/AppShell'
import GlowCard from '../components/ui/GlowCard'
import Button from '../components/ui/Button'
import StatusBadge from '../components/ui/StatusBadge'
import EmptyState from '../components/ui/EmptyState'
import campaignsApi from '../api/campaignsApi'
import postsApi from '../api/postsApi'
import './CampaignsPage.css'

const PLATFORMS = [
  { id: 'all', label: 'All Platforms', icon: '🌐' },
  { id: 'multi', label: 'Multi-Platform', icon: '✨' },
  { id: 'facebook', label: 'Facebook', icon: '📘' },
  { id: 'instagram', label: 'Instagram', icon: '📸' },
  { id: 'linkedin', label: 'LinkedIn', icon: '💼' },
  { id: 'x', label: 'X (Twitter)', icon: '𝕏' },
  { id: 'youtube', label: 'YouTube', icon: '▶️' },
  { id: 'pinterest', label: 'Pinterest', icon: '📌' },
]

const OBJECTIVES = [
  'Brand Awareness',
  'Lead Generation',
  'Product Launch',
  'Website Traffic',
  'Conversions & Sales',
  'Community Engagement',
  'Event / Webinar Registration',
  'Other (Custom)',
]

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [successNotice, setSuccessNotice] = useState('')

  // Filters
  const [statusFilter, setStatusFilter] = useState('')
  const [platformFilter, setPlatformFilter] = useState('all')
  const [searchTerm, setSearchTerm] = useState('')

  // Modals state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [showDetailsModal, setShowDetailsModal] = useState(false)
  const [showAttachPostsModal, setShowAttachPostsModal] = useState(false)

  // Active / Selected Campaign
  const [selectedCampaign, setSelectedCampaign] = useState(null)
  const [campaignPosts, setCampaignPosts] = useState([])
  const [loadingPosts, setLoadingPosts] = useState(false)

  // Posts available to attach
  const [availablePosts, setAvailablePosts] = useState([])
  const [selectedPostIdsToAttach, setSelectedPostIdsToAttach] = useState([])
  const [submittingAction, setSubmittingAction] = useState(false)

  // Form State for Create / Edit
  const [form, setForm] = useState({
    name: '',
    description: '',
    platform: 'multi',
    objective: 'Brand Awareness',
    customObjective: '',
    start_date: '',
    end_date: '',
    budget: '',
    revenue: '',
    conversions: 0,
    status: 'active',
  })

  // Flash banner helper
  const showNotice = (msg) => {
    setSuccessNotice(msg)
    setTimeout(() => setSuccessNotice(''), 4000)
  }

  // Load Campaigns
  const fetchCampaigns = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const params = {}
      if (statusFilter) params.status = statusFilter
      if (platformFilter && platformFilter !== 'all') params.platform = platformFilter
      if (searchTerm.trim()) params.search = searchTerm.trim()

      const res = await campaignsApi.getCampaigns(params)
      setCampaigns(res.data.items || [])
    } catch (err) {
      console.error('Failed to fetch campaigns:', err)
      setError(err.response?.data?.detail || 'Failed to load campaigns.')
    } finally {
      setLoading(false)
    }
  }, [statusFilter, platformFilter, searchTerm])

  useEffect(() => {
    fetchCampaigns()
  }, [fetchCampaigns])

  // Open Details Modal & Load Campaign Posts
  const handleOpenDetails = async (camp) => {
    setSelectedCampaign(camp)
    setShowDetailsModal(true)
    try {
      setLoadingPosts(true)
      const res = await campaignsApi.getCampaignPosts(camp.id)
      setCampaignPosts(res.data.items || [])
    } catch (err) {
      console.error('Failed to load campaign posts:', err)
    } finally {
      setLoadingPosts(false)
    }
  }

  // Open Create Modal
  const handleOpenCreate = () => {
    const today = new Date().toISOString().slice(0, 16)
    const nextMonth = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().slice(0, 16)
    setForm({
      name: '',
      description: '',
      platform: 'multi',
      objective: 'Brand Awareness',
      customObjective: '',
      start_date: today,
      end_date: nextMonth,
      budget: '1000',
      revenue: '',
      conversions: 0,
      status: 'active',
    })
    setShowCreateModal(true)
  }

  // Open Edit Modal
  const handleOpenEdit = (camp) => {
    setSelectedCampaign(camp)
    const isCustomObj = !OBJECTIVES.includes(camp.objective) && camp.objective !== ''
    setForm({
      name: camp.name || '',
      description: camp.description || '',
      platform: camp.platform || 'multi',
      objective: isCustomObj ? 'Other (Custom)' : (camp.objective || 'Brand Awareness'),
      customObjective: isCustomObj ? camp.objective : '',
      start_date: camp.start_date ? new Date(camp.start_date).toISOString().slice(0, 16) : '',
      end_date: camp.end_date ? new Date(camp.end_date).toISOString().slice(0, 16) : '',
      budget: camp.budget !== undefined && camp.budget !== null ? String(camp.budget) : '0',
      revenue: camp.revenue !== undefined && camp.revenue !== null ? String(camp.revenue) : '',
      conversions: camp.conversions || 0,
      status: camp.status || 'active',
    })
    setShowEditModal(true)
  }

  // Submit Create
  const handleCreateSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) return

    try {
      setSubmittingAction(true)
      const effObjective = form.objective === 'Other (Custom)' ? (form.customObjective.trim() || 'Custom Goal') : form.objective
      const payload = {
        name: form.name.trim(),
        description: form.description.trim() || null,
        platform: form.platform,
        objective: effObjective,
        start_date: form.start_date ? new Date(form.start_date).toISOString() : null,
        end_date: form.end_date ? new Date(form.end_date).toISOString() : null,
        budget: parseFloat(form.budget) || 0.0,
        revenue: form.revenue !== '' ? parseFloat(form.revenue) : null,
        conversions: parseInt(form.conversions, 10) || 0,
        status: form.status,
      }
      await campaignsApi.createCampaign(payload)
      setShowCreateModal(false)
      showNotice(`🎉 Campaign "${form.name}" created successfully!`)
      fetchCampaigns()
    } catch (err) {
      console.error('Error creating campaign:', err)
      alert(err.response?.data?.detail || 'Failed to create campaign.')
    } finally {
      setSubmittingAction(false)
    }
  }

  // Submit Edit
  const handleEditSubmit = async (e) => {
    e.preventDefault()
    if (!selectedCampaign || !form.name.trim()) return

    try {
      setSubmittingAction(true)
      const effObjective = form.objective === 'Other (Custom)' ? (form.customObjective.trim() || 'Custom Goal') : form.objective
      const payload = {
        name: form.name.trim(),
        description: form.description.trim() || null,
        platform: form.platform,
        objective: effObjective,
        start_date: form.start_date ? new Date(form.start_date).toISOString() : null,
        end_date: form.end_date ? new Date(form.end_date).toISOString() : null,
        budget: parseFloat(form.budget) || 0.0,
        revenue: form.revenue !== '' ? parseFloat(form.revenue) : null,
        conversions: parseInt(form.conversions, 10) || 0,
        status: form.status,
      }
      await campaignsApi.updateCampaign(selectedCampaign.id, payload)
      setShowEditModal(false)
      showNotice(`✅ Campaign "${form.name}" updated successfully!`)
      fetchCampaigns()
      if (showDetailsModal && selectedCampaign) {
        const updated = await campaignsApi.getCampaign(selectedCampaign.id)
        setSelectedCampaign(updated.data)
      }
    } catch (err) {
      console.error('Error updating campaign:', err)
      alert(err.response?.data?.detail || 'Failed to update campaign.')
    } finally {
      setSubmittingAction(false)
    }
  }

  // Submit Delete
  const handleDeleteSubmit = async () => {
    if (!selectedCampaign) return
    try {
      setSubmittingAction(true)
      await campaignsApi.deleteCampaign(selectedCampaign.id)
      setShowDeleteModal(false)
      setShowDetailsModal(false)
      showNotice(`🗑️ Campaign "${selectedCampaign.name}" deleted.`)
      fetchCampaigns()
    } catch (err) {
      console.error('Error deleting campaign:', err)
      alert(err.response?.data?.detail || 'Failed to delete campaign.')
    } finally {
      setSubmittingAction(false)
    }
  }

  // Detach Post
  const handleDetachPost = async (postId) => {
    if (!selectedCampaign) return
    try {
      await campaignsApi.detachPost(selectedCampaign.id, postId)
      setCampaignPosts((prev) => prev.filter((p) => p.id !== postId))
      showNotice('Post detached from campaign.')
      const updated = await campaignsApi.getCampaign(selectedCampaign.id)
      setSelectedCampaign(updated.data)
      fetchCampaigns()
    } catch (err) {
      console.error('Error detaching post:', err)
      alert(err.response?.data?.detail || 'Failed to detach post.')
    }
  }

  // Open Attach Posts Modal
  const handleOpenAttachPosts = async () => {
    try {
      setSelectedPostIdsToAttach([])
      setShowAttachPostsModal(true)
      const res = await postsApi.getPosts({ limit: 100 })
      const allUserPosts = res.data.items || []
      // Filter posts that are not already in this campaign
      const attachedIds = new Set(campaignPosts.map((p) => p.id))
      const available = allUserPosts.filter((p) => !attachedIds.has(p.id))
      setAvailablePosts(available)
    } catch (err) {
      console.error('Error fetching available posts:', err)
    }
  }

  // Submit Attach Posts
  const handleAttachPostsSubmit = async () => {
    if (!selectedCampaign || selectedPostIdsToAttach.length === 0) return
    try {
      setSubmittingAction(true)
      await campaignsApi.attachPosts(selectedCampaign.id, selectedPostIdsToAttach)
      setShowAttachPostsModal(false)
      showNotice(`Attached ${selectedPostIdsToAttach.length} post(s) to campaign!`)
      // Refresh campaign posts and campaign details
      const postsRes = await campaignsApi.getCampaignPosts(selectedCampaign.id)
      setCampaignPosts(postsRes.data.items || [])
      const updatedCamp = await campaignsApi.getCampaign(selectedCampaign.id)
      setSelectedCampaign(updatedCamp.data)
      fetchCampaigns()
    } catch (err) {
      console.error('Error attaching posts:', err)
      alert(err.response?.data?.detail || 'Failed to attach posts.')
    } finally {
      setSubmittingAction(false)
    }
  }

  // Calculate Overview Totals
  const totalCampaigns = campaigns.length
  const activeCampaigns = campaigns.filter((c) => c.status === 'active').length
  const totalBudget = campaigns.reduce((sum, c) => sum + (c.budget || 0), 0)
  const totalRevenue = campaigns.reduce((sum, c) => sum + (c.revenue || 0), 0)
  const totalConversions = campaigns.reduce((sum, c) => sum + (c.conversions || 0), 0)

  return (
    <AppShell
      pageTitle="Campaign Management"
      pageSubtitle="Plan, execute, and measure multi-channel social media marketing campaigns"
    >
      <div className="campaigns-page-container">
        {/* Top KPI Header Cards */}
        <div className="campaigns-kpi-grid">
          <GlowCard className="campaign-kpi-card" hover>
            <div className="kpi-label">Total Campaigns</div>
            <div className="kpi-value">{totalCampaigns}</div>
            <div className="kpi-subtext">{activeCampaigns} active currently</div>
          </GlowCard>

          <GlowCard className="campaign-kpi-card" hover>
            <div className="kpi-label">Total Allocated Budget</div>
            <div className="kpi-value">${totalBudget.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
            <div className="kpi-subtext">Across all marketing initiatives</div>
          </GlowCard>

          <GlowCard className="campaign-kpi-card" hover>
            <div className="kpi-label">Tracked Revenue</div>
            <div className="kpi-value" style={{ color: totalRevenue > 0 ? '#10b981' : '#94a3b8' }}>
              {totalRevenue > 0 ? `$${totalRevenue.toLocaleString()}` : '—'}
            </div>
            <div className="kpi-subtext">
              {totalRevenue > 0 ? `${totalConversions} goal conversions` : 'Revenue tracking optional'}
            </div>
          </GlowCard>

          <GlowCard className="campaign-kpi-card" hover>
            <div className="kpi-label">Tracked Conversions</div>
            <div className="kpi-value" style={{ color: '#c084fc' }}>{totalConversions}</div>
            <div className="kpi-subtext">Goals & lead acquisitions</div>
          </GlowCard>
        </div>

        {/* Action & Filter Toolbar */}
        <div className="campaigns-toolbar">
          <div className="toolbar-left">
            {/* Search Input */}
            <div className="search-box">
              <span className="search-icon">🔍</span>
              <input
                type="text"
                placeholder="Search campaigns..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="campaign-search-input"
              />
              {searchTerm && (
                <button className="clear-search-btn" onClick={() => setSearchTerm('')}>
                  ✕
                </button>
              )}
            </div>

            {/* Platform Filter */}
            <select
              className="campaign-filter-select"
              value={platformFilter}
              onChange={(e) => setPlatformFilter(e.target.value)}
            >
              {PLATFORMS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.icon} {p.label}
                </option>
              ))}
            </select>

            {/* Status Pills */}
            <div className="status-pills">
              {['', 'active', 'scheduled', 'completed', 'draft', 'paused'].map((st) => (
                <button
                  key={st || 'all'}
                  className={`status-pill-btn ${statusFilter === st ? 'active' : ''}`}
                  onClick={() => setStatusFilter(st)}
                >
                  {st ? st.charAt(0).toUpperCase() + st.slice(1) : 'All Statuses'}
                </button>
              ))}
            </div>
          </div>

          <div className="toolbar-right">
            <Button variant="primary" onClick={handleOpenCreate} id="btn-create-campaign">
              ✨ Create Campaign
            </Button>
          </div>
        </div>

        {/* Flash Success Notification */}
        {successNotice && (
          <div className="alert alert-success" style={{ marginBottom: '16px', animation: 'fadeIn 0.2s ease' }}>
            <span>{successNotice}</span>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="alert alert-danger" style={{ marginBottom: '16px' }}>
            <span>{error}</span>
          </div>
        )}

        {/* Campaigns Grid */}
        {loading ? (
          <div className="campaigns-loading-state">
            <div className="spinner" />
            <p>Loading campaigns & execution metrics...</p>
          </div>
        ) : campaigns.length === 0 ? (
          <EmptyState
            icon="🎯"
            title="No campaigns found"
            description={searchTerm || statusFilter || platformFilter !== 'all' ? "Try clearing your search or status filters." : "Create your first marketing campaign to organize posts, track budgets, and calculate real ROI."}
            action={
              <Button variant="primary" onClick={handleOpenCreate}>
                ✨ Create First Campaign
              </Button>
            }
          />
        ) : (
          <div className="campaigns-grid">
            {campaigns.map((camp) => {
              const stats = camp.tracking || camp.tracking_stats || {}
              const totalPosts = stats.total_posts || 0
              const publishedPosts = stats.published_posts || 0
              const scheduledPosts = stats.scheduled_posts || 0
              const progress = stats.progress_percentage || 0
              const roiAvailable = stats.roi_available || (camp.revenue !== null && camp.revenue !== undefined)
              const roiVal = stats.roi_percentage

              return (
                <GlowCard key={camp.id} className="campaign-card" hover>
                  <div className="campaign-card-header">
                    <div className="campaign-title-block">
                      <div className="campaign-platform-pill">
                        {PLATFORMS.find((p) => p.id === camp.platform)?.icon || '🌐'} {camp.platform || 'Multi'}
                      </div>
                      <h3 className="campaign-name">{camp.name}</h3>
                      {camp.objective && (
                        <span className="campaign-objective-tag">🎯 {camp.objective}</span>
                      )}
                    </div>
                    <StatusBadge status={camp.status} />
                  </div>

                  {camp.description && (
                    <p className="campaign-desc">{camp.description}</p>
                  )}

                  {/* Timeframe */}
                  <div className="campaign-timeframe">
                    <span>🗓️ {camp.start_date ? new Date(camp.start_date).toLocaleDateString() : 'Start TBD'}</span>
                    <span className="timeframe-arrow">→</span>
                    <span>{camp.end_date ? new Date(camp.end_date).toLocaleDateString() : 'Ongoing'}</span>
                  </div>

                  {/* Financial & Performance Row */}
                  <div className="campaign-metrics-row">
                    <div className="c-metric">
                      <span className="c-label">Budget</span>
                      <span className="c-val">${(camp.budget || 0).toLocaleString()}</span>
                    </div>
                    <div className="c-metric">
                      <span className="c-label">Revenue</span>
                      <span className="c-val" style={{ color: camp.revenue ? '#10b981' : '#94a3b8' }}>
                        {camp.revenue !== null && camp.revenue !== undefined ? `$${Number(camp.revenue).toLocaleString()}` : '—'}
                      </span>
                    </div>
                    <div className="c-metric">
                      <span className="c-label">ROI</span>
                      <span className="c-val" style={{ color: roiAvailable ? (roiVal >= 0 ? '#10b981' : '#ef4444') : '#94a3b8' }}>
                        {roiAvailable ? `${roiVal >= 0 ? '+' : ''}${roiVal}%` : 'Not Tracked'}
                      </span>
                    </div>
                  </div>

                  {/* Execution Progress Bar */}
                  <div className="campaign-progress-section">
                    <div className="progress-label-row">
                      <span>Execution ({publishedPosts}/{totalPosts} posts published)</span>
                      <span>{progress}%</span>
                    </div>
                    <div className="progress-bar-track">
                      <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
                    </div>
                    <div className="progress-sub-counts">
                      <span>⏳ {scheduledPosts} scheduled</span>
                      <span>📝 {stats.draft_posts || 0} drafts</span>
                      <span>❤️ {stats.real_engagement || 0} engagements</span>
                    </div>
                  </div>

                  {/* Card Actions Footer */}
                  <div className="campaign-card-footer">
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => handleOpenDetails(camp)}
                      className="details-btn"
                    >
                      👁️ Details & Posts ({totalPosts})
                    </Button>
                    <div className="quick-actions">
                      <button
                        className="icon-action-btn"
                        title="Edit Campaign"
                        onClick={() => handleOpenEdit(camp)}
                      >
                        ✏️
                      </button>
                      <button
                        className="icon-action-btn delete"
                        title="Delete Campaign"
                        onClick={() => {
                          setSelectedCampaign(camp)
                          setShowDeleteModal(true)
                        }}
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                </GlowCard>
              )
            })}
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* 1. CREATE CAMPAIGN MODAL */}
      {/* ========================================================================= */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content campaign-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>✨ Create New Campaign</h3>
              <button className="modal-close" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label>Campaign Title <span className="req">*</span></label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Q4 Black Friday Launch"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>Description & Notes</label>
                  <textarea
                    rows={2}
                    placeholder="Brief overview of target audience, themes, or goals..."
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                    className="form-input"
                  />
                </div>

                <div className="form-row">
                  <div className="form-group half">
                    <label>Target Platform</label>
                    <select
                      value={form.platform}
                      onChange={(e) => setForm({ ...form, platform: e.target.value })}
                      className="form-input"
                    >
                      {PLATFORMS.filter((p) => p.id !== 'all').map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.icon} {p.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group half">
                    <label>Status</label>
                    <select
                      value={form.status}
                      onChange={(e) => setForm({ ...form, status: e.target.value })}
                      className="form-input"
                    >
                      <option value="active">Active</option>
                      <option value="scheduled">Scheduled</option>
                      <option value="draft">Draft</option>
                      <option value="paused">Paused</option>
                      <option value="completed">Completed</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label>Campaign Objective</label>
                  <select
                    value={form.objective}
                    onChange={(e) => setForm({ ...form, objective: e.target.value })}
                    className="form-input"
                  >
                    {OBJECTIVES.map((obj) => (
                      <option key={obj} value={obj}>{obj}</option>
                    ))}
                  </select>
                </div>

                {form.objective === 'Other (Custom)' && (
                  <div className="form-group">
                    <label>Custom Objective Description <span className="req">*</span></label>
                    <input
                      type="text"
                      required
                      placeholder="Specify your custom campaign objective..."
                      value={form.customObjective}
                      onChange={(e) => setForm({ ...form, customObjective: e.target.value })}
                      className="form-input"
                    />
                  </div>
                )}

                <div className="form-row">
                  <div className="form-group half">
                    <label>Kickoff Date & Time</label>
                    <input
                      type="datetime-local"
                      value={form.start_date}
                      onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                      className="form-input"
                    />
                  </div>

                  <div className="form-group half">
                    <label>Conclusion Date & Time</label>
                    <input
                      type="datetime-local"
                      value={form.end_date}
                      onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                      className="form-input"
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group third">
                    <label>Budget (USD $)</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      placeholder="1000"
                      value={form.budget}
                      onChange={(e) => setForm({ ...form, budget: e.target.value })}
                      className="form-input"
                    />
                  </div>

                  <div className="form-group third">
                    <label>Revenue (Optional $)</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      placeholder="Optional"
                      value={form.revenue}
                      onChange={(e) => setForm({ ...form, revenue: e.target.value })}
                      className="form-input"
                    />
                  </div>

                  <div className="form-group third">
                    <label>Conversions Goal</label>
                    <input
                      type="number"
                      min="0"
                      placeholder="0"
                      value={form.conversions}
                      onChange={(e) => setForm({ ...form, conversions: e.target.value })}
                      className="form-input"
                    />
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <Button variant="outline" type="button" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </Button>
                <Button variant="primary" type="submit" disabled={submittingAction}>
                  {submittingAction ? 'Creating...' : 'Create Campaign'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 2. EDIT CAMPAIGN MODAL */}
      {/* ========================================================================= */}
      {showEditModal && (
        <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="modal-content campaign-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>✏️ Edit Campaign</h3>
              <button className="modal-close" onClick={() => setShowEditModal(false)}>✕</button>
            </div>
            <form onSubmit={handleEditSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label>Campaign Title <span className="req">*</span></label>
                  <input
                    type="text"
                    required
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>Description</label>
                  <textarea
                    rows={2}
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                    className="form-input"
                  />
                </div>

                <div className="form-row">
                  <div className="form-group half">
                    <label>Target Platform</label>
                    <select
                      value={form.platform}
                      onChange={(e) => setForm({ ...form, platform: e.target.value })}
                      className="form-input"
                    >
                      {PLATFORMS.filter((p) => p.id !== 'all').map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.icon} {p.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group half">
                    <label>Status</label>
                    <select
                      value={form.status}
                      onChange={(e) => setForm({ ...form, status: e.target.value })}
                      className="form-input"
                    >
                      <option value="active">Active</option>
                      <option value="scheduled">Scheduled</option>
                      <option value="draft">Draft</option>
                      <option value="paused">Paused</option>
                      <option value="completed">Completed</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label>Campaign Objective</label>
                  <select
                    value={form.objective}
                    onChange={(e) => setForm({ ...form, objective: e.target.value })}
                    className="form-input"
                  >
                    {OBJECTIVES.map((obj) => (
                      <option key={obj} value={obj}>{obj}</option>
                    ))}
                  </select>
                </div>

                {form.objective === 'Other (Custom)' && (
                  <div className="form-group">
                    <label>Custom Objective Description</label>
                    <input
                      type="text"
                      value={form.customObjective}
                      onChange={(e) => setForm({ ...form, customObjective: e.target.value })}
                      className="form-input"
                    />
                  </div>
                )}

                <div className="form-row">
                  <div className="form-group half">
                    <label>Kickoff Date & Time</label>
                    <input
                      type="datetime-local"
                      value={form.start_date}
                      onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                      className="form-input"
                    />
                  </div>

                  <div className="form-group half">
                    <label>Conclusion Date & Time</label>
                    <input
                      type="datetime-local"
                      value={form.end_date}
                      onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                      className="form-input"
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group third">
                    <label>Budget ($)</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={form.budget}
                      onChange={(e) => setForm({ ...form, budget: e.target.value })}
                      className="form-input"
                    />
                  </div>

                  <div className="form-group third">
                    <label>Revenue ($)</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      placeholder="Optional"
                      value={form.revenue}
                      onChange={(e) => setForm({ ...form, revenue: e.target.value })}
                      className="form-input"
                    />
                  </div>

                  <div className="form-group third">
                    <label>Conversions</label>
                    <input
                      type="number"
                      min="0"
                      value={form.conversions}
                      onChange={(e) => setForm({ ...form, conversions: e.target.value })}
                      className="form-input"
                    />
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <Button variant="outline" type="button" onClick={() => setShowEditModal(false)}>
                  Cancel
                </Button>
                <Button variant="primary" type="submit" disabled={submittingAction}>
                  {submittingAction ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 3. CAMPAIGN DETAILS & POSTS MODAL / DRAWER */}
      {/* ========================================================================= */}
      {showDetailsModal && selectedCampaign && (
        <div className="modal-overlay" onClick={() => setShowDetailsModal(false)}>
          <div className="modal-content campaign-details-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="details-header-title">
                <div className="campaign-platform-pill">
                  {PLATFORMS.find((p) => p.id === selectedCampaign.platform)?.icon || '🌐'} {selectedCampaign.platform || 'Multi'}
                </div>
                <h3>{selectedCampaign.name}</h3>
                <StatusBadge status={selectedCampaign.status} />
              </div>
              <button className="modal-close" onClick={() => setShowDetailsModal(false)}>✕</button>
            </div>

            <div className="modal-body">
              {/* Campaign Key Numbers Grid */}
              <div className="details-stats-bar">
                <div className="stat-item">
                  <div className="s-label">Budget</div>
                  <div className="s-val">${(selectedCampaign.budget || 0).toLocaleString()}</div>
                </div>
                <div className="stat-item">
                  <div className="s-label">Revenue</div>
                  <div className="s-val" style={{ color: selectedCampaign.revenue ? '#10b981' : '#94a3b8' }}>
                    {selectedCampaign.revenue !== null && selectedCampaign.revenue !== undefined ? `$${Number(selectedCampaign.revenue).toLocaleString()}` : 'Not Tracked'}
                  </div>
                </div>
                <div className="stat-item">
                  <div className="s-label">Conversions</div>
                  <div className="s-val">{selectedCampaign.conversions || 0}</div>
                </div>
                <div className="stat-item">
                  <div className="s-label">Calculated ROI</div>
                  <div className="s-val" style={{ color: (selectedCampaign.tracking?.roi_available || selectedCampaign.revenue !== null) ? '#10b981' : '#94a3b8' }}>
                    {selectedCampaign.tracking?.roi_percentage !== null && selectedCampaign.tracking?.roi_percentage !== undefined
                      ? `${selectedCampaign.tracking.roi_percentage >= 0 ? '+' : ''}${selectedCampaign.tracking.roi_percentage}%`
                      : (selectedCampaign.revenue ? 'Calculated' : 'Revenue Needed')}
                  </div>
                </div>
              </div>

              {/* Attached Posts Header & Action */}
              <div className="attached-posts-header">
                <div>
                  <h4 style={{ margin: '0 0 4px 0', fontSize: '15px', color: '#f1f5f9' }}>
                    Campaign Posts ({campaignPosts.length})
                  </h4>
                  <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                    All scheduled, published, and draft posts attached to this campaign.
                  </p>
                </div>
                <Button variant="primary" size="sm" onClick={handleOpenAttachPosts}>
                  ➕ Attach Existing Posts
                </Button>
              </div>

              {/* Posts List */}
              {loadingPosts ? (
                <div className="posts-loading-box">
                  <div className="spinner" />
                  <span>Loading campaign posts...</span>
                </div>
              ) : campaignPosts.length === 0 ? (
                <div className="no-posts-box">
                  <p>No posts currently attached to this campaign.</p>
                  <Button variant="outline" size="sm" onClick={handleOpenAttachPosts}>
                    Attach Posts Now
                  </Button>
                </div>
              ) : (
                <div className="campaign-posts-list">
                  {campaignPosts.map((p) => {
                    const postStatus = p.status || 'draft'
                    const pType = p.post_type || 'text'
                    const accounts = p.social_accounts || []

                    return (
                      <div key={p.id} className="campaign-post-item">
                        <div className="post-item-left">
                          <span className="post-type-icon">
                            {pType === 'image' ? '🖼️' : pType === 'video' ? '🎬' : pType === 'carousel' ? '🎠' : '📝'}
                          </span>
                          <div className="post-item-info">
                            <p className="post-item-content">{p.content || '(No text content)'}</p>
                            <div className="post-item-meta">
                              <StatusBadge status={postStatus} />
                              <span>Type: {pType}</span>
                              {accounts.length > 0 && (
                                <span>Accounts: {accounts.map((a) => a.account_name || a.platform).join(', ')}</span>
                              )}
                              {p.scheduled_at && (
                                <span>🗓️ Scheduled: {new Date(p.scheduled_at).toLocaleString()}</span>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="post-item-right">
                          <button
                            className="detach-post-btn"
                            title="Remove post from campaign"
                            onClick={() => handleDetachPost(p.id)}
                          >
                            Detach ✕
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            <div className="modal-footer">
              <Button variant="outline" onClick={() => setShowDetailsModal(false)}>
                Close
              </Button>
              <Button variant="primary" onClick={() => handleOpenEdit(selectedCampaign)}>
                ✏️ Edit Campaign Settings
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 4. ATTACH POSTS MODAL */}
      {/* ========================================================================= */}
      {showAttachPostsModal && (
        <div className="modal-overlay" onClick={() => setShowAttachPostsModal(false)}>
          <div className="modal-content attach-posts-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>➕ Attach Posts to Campaign</h3>
              <button className="modal-close" onClick={() => setShowAttachPostsModal(false)}>✕</button>
            </div>

            <div className="modal-body">
              <p style={{ fontSize: '13px', color: '#94a3b8', marginBottom: '14px' }}>
                Select posts to associate with <strong>{selectedCampaign?.name}</strong>:
              </p>

              {availablePosts.length === 0 ? (
                <div className="no-available-posts">
                  <p>All your existing posts are already attached to this campaign, or you haven't created any posts yet.</p>
                </div>
              ) : (
                <div className="attach-posts-selector-list">
                  {availablePosts.map((p) => {
                    const isChecked = selectedPostIdsToAttach.includes(p.id)
                    return (
                      <label key={p.id} className={`attach-post-row ${isChecked ? 'selected' : ''}`}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => {
                            if (isChecked) {
                              setSelectedPostIdsToAttach((prev) => prev.filter((id) => id !== p.id))
                            } else {
                              setSelectedPostIdsToAttach((prev) => [...prev, p.id])
                            }
                          }}
                        />
                        <div className="attach-post-preview">
                          <span className="post-text">{p.content || '(No text content)'}</span>
                          <span className="post-sub">Status: {p.status} | Type: {p.post_type}</span>
                        </div>
                      </label>
                    )
                  })}
                </div>
              )}
            </div>

            <div className="modal-footer">
              <Button variant="outline" onClick={() => setShowAttachPostsModal(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                disabled={submittingAction || selectedPostIdsToAttach.length === 0}
                onClick={handleAttachPostsSubmit}
              >
                {submittingAction ? 'Attaching...' : `Attach Selected (${selectedPostIdsToAttach.length})`}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 5. DELETE CONFIRMATION MODAL */}
      {/* ========================================================================= */}
      {showDeleteModal && selectedCampaign && (
        <div className="modal-overlay" onClick={() => setShowDeleteModal(false)}>
          <div className="modal-content delete-confirm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>⚠️ Delete Campaign</h3>
              <button className="modal-close" onClick={() => setShowDeleteModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <p>
                Are you sure you want to delete <strong>{selectedCampaign.name}</strong>?
              </p>
              <p style={{ fontSize: '13px', color: '#94a3b8' }}>
                Your posts and performance metrics will be preserved, but will no longer be linked to this campaign.
              </p>
            </div>
            <div className="modal-footer">
              <Button variant="outline" onClick={() => setShowDeleteModal(false)}>
                Cancel
              </Button>
              <Button variant="danger" disabled={submittingAction} onClick={handleDeleteSubmit}>
                {submittingAction ? 'Deleting...' : 'Confirm Delete'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  )
}
