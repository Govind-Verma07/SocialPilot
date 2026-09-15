/**
 * src/pages/TeamPage.jsx
 * Workspace & Team Management page.
 * Allows creating workspaces, viewing members, inviting members, updating roles, and member removal.
 */

import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext'
import { teamApi } from '../api/teamApi'
import AppShell from '../components/AppShell'
import Modal from '../components/Modal'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import GlowCard from '../components/ui/GlowCard'
import LoadingState from '../components/ui/LoadingState'
import ErrorMessage from '../components/ui/ErrorMessage'
import './TeamPage.css'

export default function TeamPage() {
  const { user } = useAuth()
  const [teams, setTeams] = useState([])
  const [activeTeamId, setActiveTeamId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [mobileNav, setMobileNav] = useState(false)

  // Modals & form state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newTeamName, setNewTeamName] = useState('')
  const [creatingTeam, setCreatingTeam] = useState(false)

  const [showInviteModal, setShowInviteModal] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('member')
  const [inviting, setInviting] = useState(false)

  const [successMsg, setSuccessMsg] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  const fetchTeams = useCallback(async () => {
    try {
      const { data } = await teamApi.getTeams()
      setTeams(data)
      if (data.length > 0 && !activeTeamId) {
        setActiveTeamId(data[0].id)
      }
    } catch (err) {
      console.error('Failed to load teams', err)
      setErrorMsg('Failed to load workspaces.')
    } finally {
      setLoading(false)
    }
  }, [activeTeamId])

  useEffect(() => {
    fetchTeams()
  }, [fetchTeams])

  const activeTeam = teams.find((t) => t.id === activeTeamId) || teams[0]

  const handleCreateTeam = async (e) => {
    e.preventDefault()
    if (!newTeamName.trim() || newTeamName.trim().length < 2) {
      setErrorMsg('Workspace name must be at least 2 characters.')
      return
    }

    setCreatingTeam(true)
    setErrorMsg('')
    try {
      const { data } = await teamApi.createTeam({ name: newTeamName.trim() })
      setTeams((prev) => [...prev, data])
      setActiveTeamId(data.id)
      setShowCreateModal(false)
      setNewTeamName('')
      setSuccessMsg(`Workspace "${data.name}" created!`)
      setTimeout(() => setSuccessMsg(''), 4000)
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to create workspace.')
    } finally {
      setCreatingTeam(false)
    }
  }

  const handleAddMember = async (e) => {
    e.preventDefault()
    if (!inviteEmail.trim() || !inviteEmail.includes('@')) {
      setErrorMsg('Please enter a valid email address.')
      return
    }

    setInviting(true)
    setErrorMsg('')
    try {
      const { data } = await teamApi.addMember(activeTeam.id, {
        email: inviteEmail.trim(),
        role: inviteRole,
      })
      setTeams((prev) =>
        prev.map((t) =>
          t.id === activeTeam.id
            ? { ...t, members: [...t.members, data], member_count: t.member_count + 1 }
            : t
        )
      )
      setShowInviteModal(false)
      setInviteEmail('')
      setInviteRole('member')
      setSuccessMsg('Member invited successfully!')
      setTimeout(() => setSuccessMsg(''), 4000)
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to invite team member.')
    } finally {
      setInviting(false)
    }
  }

  const handleRoleChange = async (memberId, newRole) => {
    try {
      const { data } = await teamApi.updateMemberRole(activeTeam.id, memberId, { role: newRole })
      setTeams((prev) =>
        prev.map((t) =>
          t.id === activeTeam.id
            ? { ...t, members: t.members.map((m) => (m.id === memberId ? data : m)) }
            : t
        )
      )
      setSuccessMsg('Member role updated.')
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to update member role.')
    }
  }

  const handleRemoveMember = async (memberId, memberName) => {
    if (!window.confirm(`Are you sure you want to remove ${memberName || 'this member'} from the workspace?`)) {
      return
    }

    try {
      await teamApi.removeMember(activeTeam.id, memberId)
      setTeams((prev) =>
        prev.map((t) =>
          t.id === activeTeam.id
            ? {
                ...t,
                members: t.members.filter((m) => m.id !== memberId),
                member_count: Math.max(1, t.member_count - 1),
              }
            : t
        )
      )
      setSuccessMsg('Member removed from workspace.')
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to remove member.')
    }
  }

  return (
    <AppShell pageTitle="Team & Workspace" pageSubtitle="Manage shared workspaces and collaborate with team members">

        {successMsg && (
          <div className="alert alert-success" role="alert">
            <span>✓</span>
            <span>{successMsg}</span>
          </div>
        )}

        {errorMsg && <ErrorMessage message={errorMsg} />}

        {loading ? (
          <LoadingState message="Loading workspaces…" size="lg" />
        ) : teams.length === 0 ? (
          <GlowCard className="empty-team-card" hover={false}>
            <div className="empty-icon">👥</div>
            <h2 className="empty-title">No Workspace Found</h2>
            <p className="empty-desc">
              Create your workspace to organize your social accounts and collaborate with your team.
            </p>
            <Button variant="primary" size="lg" onClick={() => setShowCreateModal(true)}>
              Create Your First Workspace →
            </Button>
          </GlowCard>
        ) : (
          <div className="team-content">
            {/* Workspace switcher tabs */}
            {teams.length > 1 && (
              <div className="team-tabs">
                {teams.map((t) => (
                  <button
                    key={t.id}
                    className={`team-tab-btn ${t.id === activeTeam?.id ? 'active' : ''}`}
                    onClick={() => setActiveTeamId(t.id)}
                  >
                    🏢 {t.name}
                  </button>
                ))}
              </div>
            )}

            {activeTeam && (
              <>
                {/* Workspace Summary */}
                <GlowCard className="workspace-summary-card" hover={false}>
                  <div className="ws-info-top">
                    <div>
                      <div className="ws-badge-row">
                        <span className="ws-type-tag">Workspace</span>
                        {activeTeam.is_owner && <span className="owner-tag">👑 Owner</span>}
                      </div>
                      <h2 className="ws-name">{activeTeam.name}</h2>
                      <p className="ws-date">
                        Created on{' '}
                        {new Date(activeTeam.created_at).toLocaleDateString('en-US', {
                          month: 'long',
                          day: 'numeric',
                          year: 'numeric',
                        })}
                      </p>
                    </div>
                    {activeTeam.is_owner && (
                      <Button variant="outline" size="sm" onClick={() => setShowInviteModal(true)}>
                        + Add Member
                      </Button>
                    )}
                  </div>
                </GlowCard>

                {/* Members Section */}
                <GlowCard className="members-card" hover={false}>
                  <div className="section-title-row">
                    <div>
                      <h3 className="section-heading">Workspace Members</h3>
                      <p className="section-subheading">
                        {activeTeam.members?.length || 0} user
                        {(activeTeam.members?.length || 0) === 1 ? '' : 's'} with access to this workspace.
                      </p>
                    </div>
                  </div>

                  <div className="table-wrapper">
                    <table className="members-table">
                      <thead>
                        <tr>
                          <th>Member</th>
                          <th>Role</th>
                          <th>Joined</th>
                          <th style={{ textAlign: 'right' }}>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {activeTeam.members?.map((m) => {
                          const isCurrentUser = m.user_id === user?.id
                          const isOwnerRow = m.role === 'owner' || m.user_id === activeTeam.owner_id
                          const initials = m.full_name
                            ? m.full_name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
                            : 'U'

                          return (
                            <tr key={m.id} className="member-row">
                              <td>
                                <div className="member-user-cell">
                                  <div className="member-avatar">{initials}</div>
                                  <div>
                                    <span className="member-name">
                                      {m.full_name || 'Anonymous User'}{' '}
                                      {isCurrentUser && <span className="you-pill">You</span>}
                                    </span>
                                    <span className="member-email">{m.email}</span>
                                  </div>
                                </div>
                              </td>
                              <td>
                                {activeTeam.is_owner && !isOwnerRow ? (
                                  <select
                                    value={m.role}
                                    onChange={(e) => handleRoleChange(m.id, e.target.value)}
                                    className="role-select"
                                  >
                                    <option value="admin">Admin</option>
                                    <option value="member">Member</option>
                                    <option value="viewer">Viewer</option>
                                  </select>
                                ) : (
                                  <span className={`member-role-badge role-${m.role}`}>
                                    {m.role === 'owner'
                                      ? '👑 Owner'
                                      : m.role.charAt(0).toUpperCase() + m.role.slice(1)}
                                  </span>
                                )}
                              </td>
                              <td className="member-joined-cell">
                                {new Date(m.joined_at).toLocaleDateString('en-US', {
                                  month: 'short',
                                  day: 'numeric',
                                  year: 'numeric',
                                })}
                              </td>
                              <td style={{ textAlign: 'right' }}>
                                {!isOwnerRow && (activeTeam.is_owner || isCurrentUser) && (
                                  <button
                                    className="btn btn-ghost btn-sm remove-member-btn"
                                    onClick={() => handleRemoveMember(m.id, m.full_name)}
                                    title={isCurrentUser ? 'Leave workspace' : 'Remove member'}
                                  >
                                    {isCurrentUser ? 'Leave' : 'Remove'}
                                  </button>
                                )}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </GlowCard>
              </>
            )}
          </div>
        )}

        {/* ── Create Workspace Modal ── */}
        <Modal
          isOpen={showCreateModal}
          onClose={() => setShowCreateModal(false)}
          title="Create New Workspace"
          size="md"
          footer={
            <div className="modal-actions">
              <Button variant="ghost" onClick={() => setShowCreateModal(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                loading={creatingTeam}
                disabled={creatingTeam}
                form="create-workspace-form"
              >
                {creatingTeam ? 'Creating…' : 'Create Workspace'}
              </Button>
            </div>
          }
        >
          <form id="create-workspace-form" onSubmit={handleCreateTeam} className="modal-form">
            <Input
              id="workspace-name-input"
              name="workspaceName"
              label="Workspace Name"
              type="text"
              placeholder="e.g. Acme Marketing, Personal Brand"
              value={newTeamName}
              onChange={(e) => setNewTeamName(e.target.value)}
              required
              autoComplete="off"
            />
          </form>
        </Modal>

        {/* ── Add Member Modal ── */}
        <Modal
          isOpen={showInviteModal}
          onClose={() => setShowInviteModal(false)}
          title="Add Team Member"
          size="md"
          footer={
            <div className="modal-actions">
              <Button variant="ghost" onClick={() => setShowInviteModal(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                loading={inviting}
                disabled={inviting}
                form="add-member-form"
              >
                {inviting ? 'Adding…' : 'Add Member'}
              </Button>
            </div>
          }
        >
          <form id="add-member-form" onSubmit={handleAddMember} className="modal-form">
            <Input
              id="member-email-input"
              name="inviteEmail"
              label="User Email Address"
              type="email"
              placeholder="colleague@example.com"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              hint="The user must have an active SocialPilot account."
              required
              autoComplete="email"
            />

            <div className="form-group">
              <label className="form-label" htmlFor="member-role-select">
                Workspace Role
              </label>
              <select
                id="member-role-select"
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className="form-input form-select"
              >
                <option value="admin">Admin (Can invite members and manage accounts)</option>
                <option value="member">Member (Can create posts and manage connected accounts)</option>
                <option value="viewer">Viewer (Read-only access to workspace)</option>
              </select>
            </div>
          </form>
        </Modal>
    </AppShell>
  )
}
