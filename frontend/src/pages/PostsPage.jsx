/**
 * src/pages/PostsPage.jsx
 * -----------------------
 * Content Scheduling & Multi-Platform Publishing Engine.
 * Phase 1: Content Scheduling Foundation
 * Phase 2: Publishing Calendar
 * Phase 3: Draft Post Lifecycle (Create, List, Edit, Convert to Scheduled, Delete)
 */

import { useState, useEffect, useMemo, useCallback } from 'react'
import { Link } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import Navbar from '../components/Navbar'
import GlowCard from '../components/ui/GlowCard'
import Button from '../components/ui/Button'
import StatusBadge from '../components/ui/StatusBadge'
import EmptyState from '../components/ui/EmptyState'
import postsApi from '../api/postsApi'
import socialApi from '../api/socialApi'
import './PostsPage.css'

const PLATFORM_META = {
  facebook:  { label: 'Facebook', icon: '📘' },
  instagram: { label: 'Instagram', icon: '📸' },
  linkedin:  { label: 'LinkedIn', icon: '💼' },
  x:         { label: 'X (Twitter)', icon: '𝕏' },
  youtube:   { label: 'YouTube', icon: '▶️' },
  pinterest: { label: 'Pinterest', icon: '📌' },
}

const CONTENT_TYPES = [
  { id: 'text', label: '📝 Text Post' },
  { id: 'image', label: '📸 Image Post' },
  { id: 'video', label: '🎬 Video Post' },
  { id: 'carousel', label: '🎠 Carousel' },
  { id: 'story', label: '⚡ Story' },
  { id: 'reel', label: '🎞️ Reel' },
]

const DAYS_OF_WEEK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

export default function PostsPage() {
  const [mobileNav, setMobileNav] = useState(false)
  const [activeTab, setActiveTab] = useState('queue') // 'queue', 'calendar', 'drafts', 'recurring'
  const [showComposer, setShowComposer] = useState(false)

  // Real backend data states
  const [connectedAccounts, setConnectedAccounts] = useState([])
  const [scheduledPosts, setScheduledPosts] = useState([])
  const [draftPosts, setDraftPosts] = useState([])
  const [recurringRules, setRecurringRules] = useState([])
  const [calendarPosts, setCalendarPosts] = useState([])

  // Loading states
  const [isLoadingPosts, setIsLoadingPosts] = useState(true)
  const [isLoadingDrafts, setIsLoadingDrafts] = useState(true)
  const [isLoadingRecurring, setIsLoadingRecurring] = useState(false)
  const [isLoadingCalendar, setIsLoadingCalendar] = useState(false)
  const [calendarError, setCalendarError] = useState('')
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(true)

  // Selected post for details modal
  const [selectedPost, setSelectedPost] = useState(null)
  const [publishingPostId, setPublishingPostId] = useState(null)
  const [publishingLogs, setPublishingLogs] = useState([])
  const [isLoadingLogs, setIsLoadingLogs] = useState(false)

  // Dedicated Audit Logs Modal (Screenshot 1)
  const [logsModalPost, setLogsModalPost] = useState(null)
  const [logsPlatformFilter, setLogsPlatformFilter] = useState('all')
  const [logsStatusFilter, setLogsStatusFilter] = useState('all')
  const [isExportingLog, setIsExportingLog] = useState(false)
  const [logViewMode, setLogViewMode] = useState('timeline') // 'timeline' or 'raw'
  const [rawLogContent, setRawLogContent] = useState('')
  const [isLoadingRawLog, setIsLoadingRawLog] = useState(false)
  const [copySuccess, setCopySuccess] = useState(false)

  // Draft being edited (null = new post/draft)
  const [editingDraftId, setEditingDraftId] = useState(null)

  // Calendar view controls
  const [currentDate, setCurrentDate] = useState(new Date())
  const [calendarView, setCalendarView] = useState('month') // 'month', 'week', 'day'

  // Form State
  const [scheduleType, setScheduleType] = useState('one-time') // 'one-time', 'recurring'
  const [content, setContent] = useState('')
  const [selectedAccountIds, setSelectedAccountIds] = useState([])
  const [contentType, setContentType] = useState('text')
  const [scheduleDate, setScheduleDate] = useState('')
  const [scheduleTime, setScheduleTime] = useState('')
  const [recurrenceFrequency, setRecurrenceFrequency] = useState('weekly')
  const [recurrenceWeekday, setRecurrenceWeekday] = useState('Tuesday')
  const [recurrenceMonthDay, setRecurrenceMonthDay] = useState(15)
  const [recurrenceEndDate, setRecurrenceEndDate] = useState('')

  // Status & Feedback
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  // 1. Fetch connected accounts dynamically from backend
  const loadAccounts = async () => {
    setIsLoadingAccounts(true)
    try {
      const res = await socialApi.getAccounts()
      const accounts = Array.isArray(res.data) ? res.data : []
      setConnectedAccounts(accounts)
      if (accounts.length > 0 && selectedAccountIds.length === 0) {
        const activeIds = accounts
          .filter((a) => a.status === 'connected')
          .map((a) => a.id)
        setSelectedAccountIds(activeIds)
      }
    } catch (err) {
      console.error('Failed to load connected accounts:', err)
    } finally {
      setIsLoadingAccounts(false)
    }
  }

  // 2. Fetch scheduled posts for queue
  const loadQueuePosts = async () => {
    setIsLoadingPosts(true)
    try {
      const res = await postsApi.getPosts({ status: 'scheduled' })
      setScheduledPosts(res.data?.items || [])
    } catch (err) {
      console.error('Failed to load queue posts:', err)
    } finally {
      setIsLoadingPosts(false)
    }
  }

  // 3. Fetch drafts from backend
  const loadDraftPosts = async () => {
    setIsLoadingDrafts(true)
    try {
      const res = await postsApi.getPosts({ status: 'draft' })
      setDraftPosts(res.data?.items || [])
    } catch (err) {
      console.error('Failed to load drafts:', err)
    } finally {
      setIsLoadingDrafts(false)
    }
  }

  // 4. Fetch recurring rules from backend
  const loadRecurringRules = async () => {
    setIsLoadingRecurring(true)
    try {
      const res = await postsApi.getRecurringRules()
      setRecurringRules(res.data?.items || [])
    } catch (err) {
      console.error('Failed to load recurring rules:', err)
    } finally {
      setIsLoadingRecurring(false)
    }
  }


  // 4. Compute visible calendar date range
  const { rangeStart, rangeEnd } = useMemo(() => {
    const year = currentDate.getFullYear()
    const month = currentDate.getMonth()

    if (calendarView === 'month') {
      const firstOfMonth = new Date(year, month, 1)
      const lastOfMonth = new Date(year, month + 1, 0)
      const start = new Date(firstOfMonth)
      start.setDate(firstOfMonth.getDate() - firstOfMonth.getDay())
      start.setHours(0, 0, 0, 0)
      const end = new Date(lastOfMonth)
      end.setDate(lastOfMonth.getDate() + (6 - lastOfMonth.getDay()))
      end.setHours(23, 59, 59, 999)
      return { rangeStart: start, rangeEnd: end }
    } else if (calendarView === 'week') {
      const start = new Date(currentDate)
      start.setDate(currentDate.getDate() - currentDate.getDay())
      start.setHours(0, 0, 0, 0)
      const end = new Date(start)
      end.setDate(start.getDate() + 6)
      end.setHours(23, 59, 59, 999)
      return { rangeStart: start, rangeEnd: end }
    } else {
      const start = new Date(currentDate)
      start.setHours(0, 0, 0, 0)
      const end = new Date(currentDate)
      end.setHours(23, 59, 59, 999)
      return { rangeStart: start, rangeEnd: end }
    }
  }, [currentDate, calendarView])

  // 5. Fetch posts for the active calendar date range
  const loadCalendarPosts = useCallback(async () => {
    setIsLoadingCalendar(true)
    setCalendarError('')
    try {
      const res = await postsApi.getPosts({
        status: 'scheduled',
        start_date: rangeStart.toISOString(),
        end_date: rangeEnd.toISOString(),
        limit: 200,
      })
      setCalendarPosts(res.data?.items || [])
    } catch (err) {
      console.error('Failed to load calendar posts:', err)
      setCalendarError('Unable to load scheduled posts. Please try again.')
    } finally {
      setIsLoadingCalendar(false)
    }
  }, [rangeStart, rangeEnd])

  useEffect(() => {
    loadAccounts()
    loadQueuePosts()
    loadDraftPosts()
    loadRecurringRules()
  }, [])

  useEffect(() => {
    loadCalendarPosts()
  }, [loadCalendarPosts])

  // Periodic polling so automated background publishing updates UI automatically without manual reload
  useEffect(() => {
    const interval = setInterval(() => {
      loadQueuePosts()
      loadCalendarPosts()
    }, 15000)
    return () => clearInterval(interval)
  }, [loadCalendarPosts])

  // Phase 9: Fetch publishing history logs when a post or logs modal is opened
  const loadLogsForModal = async (postId) => {
    if (!postId) return
    setIsLoadingLogs(true)
    try {
      const res = await postsApi.getPublishingLogs(postId)
      setPublishingLogs(res.data?.items || [])
    } catch (err) {
      console.error('Failed to load publishing logs:', err)
      setPublishingLogs([])
    } finally {
      setIsLoadingLogs(false)
    }
  }

  const loadRawLogContent = async (postId) => {
    if (!postId) return
    setIsLoadingRawLog(true)
    try {
      const res = await postsApi.getRawPublishingLogs(postId)
      setRawLogContent(typeof res.data === 'string' ? res.data : JSON.stringify(res.data, null, 2))
    } catch (err) {
      console.error('Failed to load raw log:', err)
      setRawLogContent('No publishing log content recorded yet. Logs are generated when publishing jobs are executed.')
    } finally {
      setIsLoadingRawLog(false)
    }
  }

  const handleCopyRawLog = async () => {
    if (!rawLogContent) return
    try {
      await navigator.clipboard.writeText(rawLogContent)
      setCopySuccess(true)
      setTimeout(() => setCopySuccess(false), 2000)
    } catch (err) {
      console.error('Failed to copy to clipboard:', err)
    }
  }

  const handleOpenLogsModal = (post, e) => {
    if (e) e.stopPropagation()
    setLogsModalPost(post)
    setLogsPlatformFilter('all')
    setLogsStatusFilter('all')
    setLogViewMode('timeline')
    setRawLogContent('')
    loadLogsForModal(post.id)
    loadRawLogContent(post.id)
  }

  const handleDownloadLogFile = async (post, e) => {
    if (e) e.stopPropagation()
    if (!post?.id) return
    setIsExportingLog(true)
    try {
      const res = await postsApi.exportPublishingLogs(post.id)
      const blob = new Blob([res.data], { type: 'text/plain;charset=utf-8' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `publishing_logs_${post.id.slice(0, 8)}.log`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Failed to export publishing logs:', err)
      alert('Failed to download log file.')
    } finally {
      setIsExportingLog(false)
    }
  }

  const filteredLogs = useMemo(() => {
    return publishingLogs.filter((log) => {
      const matchPlatform =
        logsPlatformFilter === 'all' ||
        log.platform?.toLowerCase() === logsPlatformFilter.toLowerCase()
      const matchStatus =
        logsStatusFilter === 'all' ||
        log.status?.toLowerCase() === logsStatusFilter.toLowerCase()
      return matchPlatform && matchStatus
    })
  }, [publishingLogs, logsPlatformFilter, logsStatusFilter])

  useEffect(() => {
    if (selectedPost?.id) {
      loadLogsForModal(selectedPost.id)
    } else if (!logsModalPost) {
      setPublishingLogs([])
    }
  }, [selectedPost?.id])

  // Calendar Navigation Handlers
  const handlePrev = () => {
    setCurrentDate((prev) => {
      const next = new Date(prev)
      if (calendarView === 'month') next.setMonth(prev.getMonth() - 1)
      else if (calendarView === 'week') next.setDate(prev.getDate() - 7)
      else next.setDate(prev.getDate() - 1)
      return next
    })
  }

  const handleNext = () => {
    setCurrentDate((prev) => {
      const next = new Date(prev)
      if (calendarView === 'month') next.setMonth(prev.getMonth() + 1)
      else if (calendarView === 'week') next.setDate(prev.getDate() + 7)
      else next.setDate(prev.getDate() + 1)
      return next
    })
  }

  const handleToday = () => {
    setCurrentDate(new Date())
  }

  // Account selection toggles
  const toggleAccount = (id) => {
    setSelectedAccountIds((prev) =>
      prev.includes(id) ? prev.filter((accId) => accId !== id) : [...prev, id]
    )
  }

  const toggleAllAccounts = () => {
    const activeAccounts = connectedAccounts.filter((a) => a.status === 'connected')
    if (selectedAccountIds.length === activeAccounts.length) {
      setSelectedAccountIds([])
    } else {
      setSelectedAccountIds(activeAccounts.map((a) => a.id))
    }
  }

  // Open Composer in Draft Edit Mode
  const handleEditDraft = (draft) => {
    setEditingDraftId(draft.id)
    setScheduleType('one-time')
    setContent(draft.content || '')
    setSelectedAccountIds((draft.social_accounts || []).map((sa) => sa.id))
    setContentType(draft.post_type || 'text')
    if (draft.scheduled_at) {
      const d = new Date(draft.scheduled_at)
      setScheduleDate(d.toISOString().slice(0, 10))
      setScheduleTime(d.toTimeString().slice(0, 5))
    } else {
      setScheduleDate('')
      setScheduleTime('')
    }
    setErrorMessage('')
    setSuccessMessage('')
    setShowComposer(true)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Reset composer state
  const handleCancelComposer = () => {
    setShowComposer(false)
    setEditingDraftId(null)
    setScheduleType('one-time')
    setContent('')
    setScheduleDate('')
    setScheduleTime('')
    setRecurrenceEndDate('')
    setErrorMessage('')
    setSuccessMessage('')
  }

  // Handle Save as Draft
  const handleSaveDraft = async () => {
    setErrorMessage('')
    setSuccessMessage('')
    setIsSubmitting(true)

    try {
      const payload = {
        content: content,
        social_account_ids: selectedAccountIds,
        post_type: contentType,
        status: 'draft',
        media_urls: [],
      }

      if (editingDraftId) {
        await postsApi.updatePost(editingDraftId, payload)
        setSuccessMessage('Draft updated successfully in database!')
      } else {
        await postsApi.createPost(payload)
        setSuccessMessage('Draft saved successfully in database!')
      }

      await loadDraftPosts()
      handleCancelComposer()
    } catch (err) {
      console.error('Save draft error:', err)
      const detail = err.response?.data?.detail
      setErrorMessage(typeof detail === 'string' ? detail : 'Unable to save draft. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Handle Post Scheduling Form Submission (One Time, Recurring, or Draft -> Scheduled)
  const handleSchedulePost = async (e) => {
    e.preventDefault()
    setErrorMessage('')
    setSuccessMessage('')

    const trimmedContent = content.trim()
    if (!trimmedContent) {
      setErrorMessage('Post content is required.')
      return
    }

    if (selectedAccountIds.length === 0) {
      setErrorMessage('Please select at least one social account.')
      return
    }

    if (!scheduleDate || !scheduleTime) {
      setErrorMessage(scheduleType === 'recurring' ? 'Please select both a start date and time.' : 'Please select both a schedule date and time.')
      return
    }

    const scheduledDateTime = new Date(`${scheduleDate}T${scheduleTime}`)
    if (isNaN(scheduledDateTime.getTime())) {
      setErrorMessage('Please provide a valid schedule date and time.')
      return
    }

    if (scheduledDateTime.getTime() <= Date.now()) {
      setErrorMessage(scheduleType === 'recurring' ? 'Start date/time must be in the future.' : 'Scheduled time must be in the future.')
      return
    }

    // Phase 4: Recurring Post Submission
    if (scheduleType === 'recurring' && !editingDraftId) {
      if (!recurrenceEndDate) {
        setErrorMessage('Please select an end date for the recurring schedule.')
        return
      }

      const endDateTime = new Date(`${recurrenceEndDate}T23:59:59`)
      if (isNaN(endDateTime.getTime()) || endDateTime.getTime() <= scheduledDateTime.getTime()) {
        setErrorMessage('End date must be after the start date.')
        return
      }

      setIsSubmitting(true)
      try {
        const payload = {
          content: trimmedContent,
          social_account_ids: selectedAccountIds,
          frequency: recurrenceFrequency,
          interval: 1,
          start_at: scheduledDateTime.toISOString(),
          end_at: endDateTime.toISOString(),
          by_weekday: recurrenceFrequency === 'weekly' ? recurrenceWeekday : undefined,
          by_month_day: recurrenceFrequency === 'monthly' ? parseInt(recurrenceMonthDay, 10) : undefined,
          post_type: contentType,
          media_urls: [],
        }

        const res = await postsApi.createRecurringRule(payload)
        const count = res.data?.generated_count || res.data?.occurrences?.length || 0
        setSuccessMessage(`Recurring schedule created! Generated ${count} scheduled occurrences across Queue and Calendar.`)
        handleCancelComposer()
        await Promise.all([loadQueuePosts(), loadCalendarPosts(), loadRecurringRules()])
      } catch (err) {
        console.error('Recurring scheduling error:', err)
        const detail = err.response?.data?.detail
        if (typeof detail === 'string') {
          setErrorMessage(detail)
        } else if (Array.isArray(detail) && detail.length > 0) {
          setErrorMessage(detail.map((d) => d.msg || d).join(', '))
        } else {
          setErrorMessage('Unable to create recurring schedule. Please try again.')
        }
      } finally {
        setIsSubmitting(false)
      }
      return
    }

    // One-Time Post Submission
    setIsSubmitting(true)
    try {
      const payload = {
        content: trimmedContent,
        social_account_ids: selectedAccountIds,
        scheduled_at: scheduledDateTime.toISOString(),
        post_type: contentType,
        status: 'scheduled',
        media_urls: [],
      }

      if (editingDraftId) {
        // DRAFT -> SCHEDULED conversion (same post record updated)
        await postsApi.updatePost(editingDraftId, payload)
        setSuccessMessage(`Draft scheduled successfully for ${scheduledDateTime.toLocaleString()}!`)
      } else {
        await postsApi.createPost(payload)
        setSuccessMessage(`Post scheduled successfully for ${scheduledDateTime.toLocaleString()}!`)
      }

      handleCancelComposer()
      // Refresh all lists: draft disappears from drafts, appears in queue & calendar
      await Promise.all([loadQueuePosts(), loadDraftPosts(), loadCalendarPosts()])
    } catch (err) {
      console.error('Scheduling error:', err)
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') {
        setErrorMessage(detail)
      } else if (Array.isArray(detail) && detail.length > 0) {
        setErrorMessage(detail.map((d) => d.msg || d).join(', '))
      } else {
        setErrorMessage('Unable to schedule the post. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  // Handle deleting a recurring rule
  const handleDeleteRecurringRule = async (ruleId) => {
    if (!window.confirm('Are you sure you want to delete this recurring schedule? This will also remove all scheduled occurrences created by it.')) return
    try {
      await postsApi.deleteRecurringRule(ruleId)
      setRecurringRules((prev) => prev.filter((r) => r.id !== ruleId))
      await Promise.all([loadQueuePosts(), loadCalendarPosts()])
    } catch (err) {
      console.error('Failed to delete recurring rule:', err)
      alert(err.response?.data?.detail || 'Failed to delete recurring rule.')
    }
  }

  // Handle activating / deactivating a recurring rule
  const handleToggleActiveRule = async (rule) => {
    try {
      await postsApi.updateRecurringRule(rule.id, { is_active: !rule.is_active })
      await loadRecurringRules()
    } catch (err) {
      console.error('Failed to update recurring rule:', err)
      alert(err.response?.data?.detail || 'Failed to update recurring rule.')
    }
  }


  // Handle deleting a post or draft
  const handleDeletePost = async (postId) => {
    if (!window.confirm('Are you sure you want to delete this post?')) return
    try {
      await postsApi.deletePost(postId)
      setScheduledPosts((prev) => prev.filter((p) => p.id !== postId))
      setDraftPosts((prev) => prev.filter((p) => p.id !== postId))
      setCalendarPosts((prev) => prev.filter((p) => p.id !== postId))
      if (selectedPost && selectedPost.id === postId) {
        setSelectedPost(null)
      }
    } catch (err) {
      console.error('Failed to delete post:', err)
      alert(err.response?.data?.detail || 'Failed to delete post.')
    }
  }

  // Handle publishing a post immediately / force publish
  const handlePublishNow = async (post) => {
    if (!post?.id) return
    const accCount = post.social_accounts?.length || 0
    if (accCount === 0) {
      alert('This post has no attached social accounts. Please edit and select at least one social account first.')
      return
    }
    if (!window.confirm(`Are you sure you want to force publish this post immediately to ${accCount} social account(s)?`)) return

    setPublishingPostId(post.id)
    setErrorMessage('')
    setSuccessMessage('')
    try {
      const res = await postsApi.publishPost(post.id)
      const updatedPost = res.data

      if (updatedPost.status === 'publishing') {
        setSuccessMessage('Publishing started in background... 🚀 Status will update momentarily.')
      } else {
        // Check results if available immediately
        const results = updatedPost.publish_results || []
        const successCount = results.filter((r) => r.status === 'published').length
        const failedCount = results.filter((r) => r.status === 'failed').length

        if (failedCount === 0 && successCount > 0) {
          setSuccessMessage(`Post successfully published to all ${successCount} platform(s)! 🚀`)
        } else if (successCount > 0 && failedCount > 0) {
          setSuccessMessage(`Partially published: ${successCount} succeeded, ${failedCount} failed. Check details below.`)
        } else if (failedCount > 0) {
          setErrorMessage(`Publishing failed on all targeted accounts. Check error details.`)
        } else {
          setSuccessMessage('Publishing executed successfully.')
        }
      }

      // Refresh post lists and open modals
      await Promise.all([loadQueuePosts(), loadCalendarPosts(), loadDraftPosts()])
      if (selectedPost && selectedPost.id === post.id) {
        setSelectedPost(updatedPost)
      }
      if (logsModalPost && logsModalPost.id === post.id) {
        setLogsModalPost(updatedPost)
        loadLogsForModal(post.id)
        loadRawLogContent(post.id)
      }
    } catch (err) {
      console.error('Failed to publish post:', err)
      const detail = err.response?.data?.detail
      setErrorMessage(typeof detail === 'string' ? detail : 'Failed to publish post.')
    } finally {
      setPublishingPostId(null)
    }
  }

  // Build array of days for month/week/day grid
  const calendarDays = useMemo(() => {
    const days = []
    const curr = new Date(rangeStart)
    while (curr <= rangeEnd) {
      days.push(new Date(curr))
      curr.setDate(curr.getDate() + 1)
    }
    return days
  }, [rangeStart, rangeEnd])

  // Map calendar posts to dates
  const postsByDate = useMemo(() => {
    const map = {}
    calendarPosts.forEach((p) => {
      if (!p.scheduled_at) return
      const d = new Date(p.scheduled_at)
      const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
      if (!map[key]) map[key] = []
      map[key].push(p)
    })
    return map
  }, [calendarPosts])

  // Formatted calendar header title
  const calendarTitle = useMemo(() => {
    const options = { month: 'long', year: 'numeric' }
    if (calendarView === 'month') {
      return currentDate.toLocaleDateString(undefined, options)
    } else if (calendarView === 'week') {
      return `Week of ${rangeStart.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} – ${rangeEnd.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`
    } else {
      return currentDate.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
    }
  }, [currentDate, calendarView, rangeStart, rangeEnd])

  const today = new Date()

  return (
    <div className="app-layout body-bg">
      <Sidebar mobileOpen={mobileNav} onCloseMobile={() => setMobileNav(false)} />

      <main className="app-main">
        <Navbar
          pageTitle="Content Scheduling & Publishing Engine"
          pageSubtitle="Create, schedule, and automate posts across all 6 social media platforms"
          mobileMenuLabel="Open menu"
          onMobileMenu={() => setMobileNav(true)}
        />

        {/* Top Header Row with Tabs and Composer Trigger */}
        <div className="posts-header-row">
          <div className="posts-tabs">
            <button
              type="button"
              className={`posts-tab-btn ${activeTab === 'queue' ? 'active' : ''}`}
              onClick={() => setActiveTab('queue')}
            >
              📜 Scheduled Queue ({scheduledPosts.length})
            </button>
            <button
              type="button"
              className={`posts-tab-btn ${activeTab === 'calendar' ? 'active' : ''}`}
              onClick={() => setActiveTab('calendar')}
            >
              📅 Publishing Calendar
            </button>
            <button
              type="button"
              className={`posts-tab-btn ${activeTab === 'drafts' ? 'active' : ''}`}
              onClick={() => setActiveTab('drafts')}
            >
              📝 Drafts ({draftPosts.length})
            </button>
            <button
              type="button"
              className={`posts-tab-btn ${activeTab === 'recurring' ? 'active' : ''}`}
              onClick={() => setActiveTab('recurring')}
            >
              🔄 Recurring Schedules ({recurringRules.length})
            </button>
          </div>

          <button
            type="button"
            className="btn-create-schedule-gradient"
            onClick={() => {
              if (showComposer) {
                handleCancelComposer()
              } else {
                setEditingDraftId(null)
                setContent('')
                setScheduleDate('')
                setScheduleTime('')
                setShowComposer(true)
              }
            }}
          >
            {showComposer ? '✕ Close Composer' : '+ Create & Schedule Post'}
          </button>
        </div>

        {/* Global Success / Error Banners */}
        {successMessage && !showComposer && (
          <div className="posts-banner-success" style={{ marginTop: '16px' }}>
            <span>✅</span>
            <span>{successMessage}</span>
          </div>
        )}

        {/* Create Post / Edit Draft Composer Section */}
        {showComposer && (
          <GlowCard className="composer-card" hover style={{ marginTop: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 className="section-heading" style={{ margin: 0 }}>
                {editingDraftId ? '✏️ Edit Draft Post' : 'Create Social Post'}
              </h3>
              <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                {editingDraftId ? 'Editing existing draft in database' : 'Phase 1-3: Scheduling & Drafts'}
              </span>
            </div>

            {/* Error Banner */}
            {errorMessage && (
              <div className="posts-banner-error">
                <span>⚠️</span>
                <span>{errorMessage}</span>
              </div>
            )}

            {/* Success Banner */}
            {successMessage && (
              <div className="posts-banner-success">
                <span>✅</span>
                <span>{successMessage}</span>
              </div>
            )}

            <form onSubmit={handleSchedulePost} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              {/* Content Format Selector */}
              <div>
                <label className="form-label" style={{ marginBottom: '8px', display: 'block' }}>
                  Post Format
                </label>
                <div className="content-type-selector">
                  {CONTENT_TYPES.map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      className={`content-type-chip ${contentType === t.id ? 'selected' : ''}`}
                      onClick={() => setContentType(t.id)}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Target Social Accounts */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <label className="form-label" style={{ margin: 0 }}>
                    Target Social Accounts ({selectedAccountIds.length} selected)
                  </label>
                  {connectedAccounts.length > 0 && (
                    <button
                      type="button"
                      onClick={toggleAllAccounts}
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
                      {selectedAccountIds.length === connectedAccounts.length ? '✓ Unselect All' : '☐ Select All'}
                    </button>
                  )}
                </div>

                {isLoadingAccounts ? (
                  <div style={{ fontSize: '13px', color: '#94a3b8', padding: '12px 0' }}>
                    Loading your connected accounts...
                  </div>
                ) : connectedAccounts.length === 0 ? (
                  <div className="no-accounts-warning">
                    <div>
                      <strong>No connected accounts found.</strong> You need at least one connected social account to schedule posts.
                    </div>
                    <Link to="/accounts">
                      <Button variant="outline" size="sm">
                        Connect Account →
                      </Button>
                    </Link>
                  </div>
                ) : (
                  <div className="platform-checkboxes">
                    {connectedAccounts.map((acc) => {
                      const isChecked = selectedAccountIds.includes(acc.id)
                      const isConnected = acc.status === 'connected'
                      const meta = PLATFORM_META[acc.platform.toLowerCase()] || { label: acc.platform, icon: '📱' }

                      return (
                        <button
                          key={acc.id}
                          type="button"
                          disabled={!isConnected}
                          className={`platform-check-btn ${isChecked ? 'checked' : ''}`}
                          onClick={() => toggleAccount(acc.id)}
                          style={{
                            opacity: isConnected ? 1 : 0.5,
                            cursor: isConnected ? 'pointer' : 'not-allowed',
                          }}
                          title={!isConnected ? 'Account is not connected or token expired' : acc.account_name}
                        >
                          <span>{meta.icon}</span>
                          <span>
                            <strong>{meta.label}</strong> ({acc.account_name || acc.account_username || 'Account'})
                          </span>
                          <span>{isChecked ? '✓' : '+'}</span>
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Content / Caption Input */}
              <div className="form-group">
                <label className="form-label">Post Content / Message</label>
                <textarea
                  className="form-input post-textarea"
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Write your post caption, thoughts, hashtags, or links..."
                  rows={4}
                />
              </div>

              {/* Schedule Type Selection (One-Time vs Recurring) */}
              {!editingDraftId && (
                <div className="form-group">
                  <label className="form-label" style={{ marginBottom: '6px' }}>Schedule Type</label>
                  <div className="schedule-type-toggle">
                    <button
                      type="button"
                      className={`schedule-type-btn ${scheduleType === 'one-time' ? 'active' : ''}`}
                      onClick={() => setScheduleType('one-time')}
                    >
                      <span>○</span>
                      <span>One Time Post</span>
                    </button>
                    <button
                      type="button"
                      className={`schedule-type-btn ${scheduleType === 'recurring' ? 'active' : ''}`}
                      onClick={() => setScheduleType('recurring')}
                    >
                      <span>●</span>
                      <span>Recurring Post 🔄</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Schedule Date & Time Selection */}
              {(scheduleType === 'one-time' || editingDraftId) ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div className="form-group">
                    <label className="form-label">Publish Date (Required to Schedule)</label>
                    <input
                      type="date"
                      className="form-input"
                      value={scheduleDate}
                      onChange={(e) => setScheduleDate(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Publish Time (Required to Schedule)</label>
                    <input
                      type="time"
                      className="form-input"
                      value={scheduleTime}
                      onChange={(e) => setScheduleTime(e.target.value)}
                    />
                  </div>
                </div>
              ) : (
                <div className="recurring-config-grid">
                  <div className="form-group">
                    <label className="form-label">Repeat</label>
                    <select
                      className="form-input"
                      value={recurrenceFrequency}
                      onChange={(e) => setRecurrenceFrequency(e.target.value)}
                    >
                      <option value="daily">Daily</option>
                      <option value="weekly">Weekly</option>
                      <option value="monthly">Monthly</option>
                    </select>
                  </div>

                  {recurrenceFrequency === 'weekly' && (
                    <div className="form-group">
                      <label className="form-label">Day of Week</label>
                      <select
                        className="form-input"
                        value={recurrenceWeekday}
                        onChange={(e) => setRecurrenceWeekday(e.target.value)}
                      >
                        <option value="Monday">Monday</option>
                        <option value="Tuesday">Tuesday</option>
                        <option value="Wednesday">Wednesday</option>
                        <option value="Thursday">Thursday</option>
                        <option value="Friday">Friday</option>
                        <option value="Saturday">Saturday</option>
                        <option value="Sunday">Sunday</option>
                      </select>
                    </div>
                  )}

                  {recurrenceFrequency === 'monthly' && (
                    <div className="form-group">
                      <label className="form-label">Day of Month (1 - 31)</label>
                      <input
                        type="number"
                        min="1"
                        max="31"
                        className="form-input"
                        value={recurrenceMonthDay}
                        onChange={(e) => setRecurrenceMonthDay(e.target.value)}
                      />
                    </div>
                  )}

                  <div className="form-group">
                    <label className="form-label">Start Date</label>
                    <input
                      type="date"
                      className="form-input"
                      value={scheduleDate}
                      onChange={(e) => setScheduleDate(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Start Time</label>
                    <input
                      type="time"
                      className="form-input"
                      value={scheduleTime}
                      onChange={(e) => setScheduleTime(e.target.value)}
                    />
                  </div>

                  <div className="form-group" style={{ gridColumn: recurrenceFrequency === 'daily' ? 'span 2' : 'span 1' }}>
                    <label className="form-label">End Date (Recurrence boundary)</label>
                    <input
                      type="date"
                      className="form-input"
                      value={recurrenceEndDate}
                      onChange={(e) => setRecurrenceEndDate(e.target.value)}
                    />
                  </div>
                </div>
              )}

              {/* Action Buttons: Save Draft & Schedule Post */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={handleCancelComposer}
                >
                  Cancel
                </Button>

                <div style={{ display: 'flex', gap: '12px' }}>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleSaveDraft}
                    disabled={isSubmitting}
                  >
                    Save as Draft 💾
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={isSubmitting || connectedAccounts.length === 0}
                  >
                    {isSubmitting
                      ? 'Processing...'
                      : editingDraftId
                      ? 'Schedule Draft 🚀'
                      : scheduleType === 'recurring'
                      ? 'Create Recurring Schedule 🔄'
                      : 'Schedule Post 🚀'}
                  </Button>
                </div>
              </div>

            </form>
          </GlowCard>
        )}

        {/* TAB 1: SCHEDULED QUEUE (MATCHING SCREENSHOT 2) */}
        {activeTab === 'queue' && (
          <div className="scheduled-queue-container" style={{ marginTop: '20px' }}>
            {isLoadingPosts ? (
              <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
                Loading scheduled posts...
              </div>
            ) : scheduledPosts.length === 0 ? (
              <EmptyState
                icon="📋"
                title="No scheduled posts yet"
                description="You haven't scheduled any posts yet. Click '+ Create & Schedule Post' above to compose and schedule your first post."
                size="md"
              />
            ) : (
              <div className="scheduled-posts-stack">
                {scheduledPosts.map((post) => {
                  const scheduledDateFormatted = post.scheduled_at
                    ? new Date(post.scheduled_at).toLocaleString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                        hour: 'numeric',
                        minute: '2-digit',
                        hour12: true,
                      })
                    : 'Not scheduled'

                  return (
                    <div key={post.id} className="scheduled-post-row-card">
                      {/* Left Block: Icon + Details + Chips + Time */}
                      <div className="scheduled-post-meta-left">
                        <div
                          className="scheduled-post-icon-box"
                          onClick={() => setSelectedPost(post)}
                          title="Click to view details"
                        >
                          <span className="scheduled-post-icon">📄</span>
                        </div>

                        <div
                          className="scheduled-post-content-group"
                          onClick={() => setSelectedPost(post)}
                          title="Click to view details"
                          style={{ cursor: 'pointer' }}
                        >
                          <div className="scheduled-post-caption">
                            {post.content || 'Untitled Post'}
                          </div>
                          <div className="scheduled-post-format-label">
                            Format: {(post.post_type || 'TEXT').toUpperCase()}
                          </div>
                        </div>

                        <span className="post-inline-dot">•</span>

                        {/* Attached Social Platforms */}
                        <div className="scheduled-post-platforms-list">
                          <span className="platforms-prefix">Platforms:</span>
                          {post.social_accounts && post.social_accounts.length > 0 ? (
                            post.social_accounts.map((sa) => {
                              const meta = PLATFORM_META[sa.platform.toLowerCase()] || { icon: '📱', label: sa.platform }
                              return (
                                <span key={sa.id} className="scheduled-platform-badge" title={`${meta.label}: ${sa.account_name || sa.account_username}`}>
                                  <span className="platform-icon">{meta.icon}</span>
                                  <span className="platform-name">{sa.account_name || sa.account_username || meta.label}</span>
                                </span>
                              )
                            })
                          ) : (
                            <span style={{ color: '#64748b', fontSize: '12px' }}>No platforms</span>
                          )}
                        </div>

                        <span className="post-inline-dot">•</span>

                        {/* Scheduled Timestamp */}
                        <div className="scheduled-post-timestamp">
                          Scheduled: <span className="time-highlight">{scheduledDateFormatted}</span>
                        </div>
                      </div>

                      {/* Right Block: Publish Now + SCHEDULED Badge + Logs + Delete */}
                      <div className="scheduled-post-actions-right">
                        <button
                          type="button"
                          className="btn-action-publish-gradient"
                          disabled={publishingPostId === post.id}
                          onClick={(e) => {
                            e.stopPropagation()
                            handlePublishNow(post)
                          }}
                          title="Publish immediately to real social channels"
                        >
                          {publishingPostId === post.id ? 'Publishing...' : '🚀 Publish Now'}
                        </button>

                        <div className="pill-badge-scheduled">
                          <span className="amber-dot">•</span>
                          <span>SCHEDULED</span>
                        </div>

                        <button
                          type="button"
                          className="btn-vertical-action logs-btn"
                          onClick={(e) => handleOpenLogsModal(post, e)}
                          title="View Publishing History & Audit Logs"
                        >
                          <span className="v-icon">📜</span>
                          <span className="v-text">Logs</span>
                        </button>

                        <button
                          type="button"
                          className="btn-vertical-action delete-btn"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDeletePost(post.id)
                          }}
                          title="Delete this scheduled post"
                        >
                          <span className="v-icon">🗑️</span>
                          <span className="v-text">Delete</span>
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: PUBLISHING CALENDAR */}
        {activeTab === 'calendar' && (
          <GlowCard style={{ padding: '24px', marginTop: '20px' }}>
            {/* Calendar Controls */}
            <div className="calendar-controls-bar">
              <div className="calendar-nav-group">
                <button type="button" className="calendar-btn" onClick={handlePrev} title="Previous period">
                  ◀
                </button>
                <button type="button" className="calendar-btn" onClick={handleToday}>
                  Today
                </button>
                <button type="button" className="calendar-btn" onClick={handleNext} title="Next period">
                  ▶
                </button>
                <h3 className="section-heading" style={{ margin: '0 0 0 12px' }}>
                  {calendarTitle}
                </h3>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                {/* View Switcher */}
                <div className="calendar-view-toggle">
                  <button
                    type="button"
                    className={`calendar-view-btn ${calendarView === 'month' ? 'active' : ''}`}
                    onClick={() => setCalendarView('month')}
                  >
                    Month
                  </button>
                  <button
                    type="button"
                    className={`calendar-view-btn ${calendarView === 'week' ? 'active' : ''}`}
                    onClick={() => setCalendarView('week')}
                  >
                    Week
                  </button>
                  <button
                    type="button"
                    className={`calendar-view-btn ${calendarView === 'day' ? 'active' : ''}`}
                    onClick={() => setCalendarView('day')}
                  >
                    Day
                  </button>
                </div>
              </div>
            </div>

            {/* Error or Loading Banners */}
            {calendarError && (
              <div className="posts-banner-error" style={{ marginBottom: '16px' }}>
                <span>⚠️ {calendarError}</span>
                <Button variant="outline" size="sm" onClick={loadCalendarPosts} style={{ marginLeft: 'auto' }}>
                  Retry
                </Button>
              </div>
            )}

            {isLoadingCalendar && (
              <div style={{ textAlign: 'center', padding: '16px', color: '#94a3b8', fontSize: '13px' }}>
                Loading scheduled posts for {calendarTitle}...
              </div>
            )}

            {/* Empty state when no posts in range */}
            {!isLoadingCalendar && calendarPosts.length === 0 && (
              <div style={{ marginBottom: '16px' }}>
                <EmptyState
                  icon="📅"
                  title="No scheduled posts"
                  description={`You don't have any posts scheduled for this ${calendarView}. Click '+ Create & Schedule Post' above to schedule one.`}
                  size="sm"
                />
              </div>
            )}

            {/* Calendar Grid Headers (Sunday to Saturday for month/week) */}
            {calendarView !== 'day' && (
              <div className="calendar-grid">
                {DAYS_OF_WEEK.map((d) => (
                  <div key={d} className="calendar-day-header">
                    {d}
                  </div>
                ))}
              </div>
            )}

            {/* Calendar Days Cells */}
            <div
              className="calendar-grid"
              style={{
                gridTemplateColumns: calendarView === 'day' ? '1fr' : 'repeat(7, 1fr)',
              }}
            >
              {calendarDays.map((dayDate) => {
                const dayKey = `${dayDate.getFullYear()}-${dayDate.getMonth()}-${dayDate.getDate()}`
                const dayPosts = postsByDate[dayKey] || []
                const isToday =
                  dayDate.getDate() === today.getDate() &&
                  dayDate.getMonth() === today.getMonth() &&
                  dayDate.getFullYear() === today.getFullYear()
                const isOutsideMonth =
                  calendarView === 'month' && dayDate.getMonth() !== currentDate.getMonth()

                return (
                  <div
                    key={dayKey}
                    className={`calendar-day-box ${isToday ? 'today' : ''} ${isOutsideMonth ? 'outside-month' : ''}`}
                    style={{ minHeight: calendarView === 'day' ? '180px' : '105px' }}
                  >
                    <div className="calendar-day-top">
                      <span className="calendar-day-num">{dayDate.getDate()}</span>
                      {dayPosts.length > 0 && (
                        <span style={{ fontSize: '10px', color: '#a855f7', fontWeight: 700 }}>
                          {dayPosts.length} {dayPosts.length === 1 ? 'post' : 'posts'}
                        </span>
                      )}
                    </div>

                    {/* Render Events */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
                      {dayPosts.map((post) => {
                        const postTime = new Date(post.scheduled_at).toLocaleTimeString(undefined, {
                          hour: '2-digit',
                          minute: '2-digit',
                        })

                        return (
                          <div
                            key={post.id}
                            className="calendar-post-badge"
                            onClick={() => setSelectedPost(post)}
                            title="Click to view full post details"
                          >
                            <div className="calendar-post-badge-time">
                              <span>🕒 {postTime}</span>
                              {post.recurring_rule_id && (
                                <span title="Recurring Post" style={{ fontSize: '10px' }}>🔄</span>
                              )}
                              <span style={{ marginLeft: 'auto' }}>
                                {post.social_accounts?.map((sa) => {
                                  const meta = PLATFORM_META[sa.platform.toLowerCase()] || { icon: '📱' }
                                  return meta.icon
                                }).join(' ')}
                              </span>
                            </div>
                            <div className="calendar-post-badge-text">{post.content}</div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
            </div>
          </GlowCard>
        )}


        {/* TAB 3: DRAFTS (PHASE 3) */}
        {activeTab === 'drafts' && (
          <div style={{ marginTop: '20px' }}>
            <div style={{ marginBottom: '16px' }}>
              <h3 className="section-heading" style={{ margin: 0 }}>
                Draft Posts ({draftPosts.length})
              </h3>
              <p className="section-subheading" style={{ margin: 0, marginTop: '4px' }}>
                Unfinished posts saved in database that you can edit and schedule
              </p>
            </div>

            {isLoadingDrafts ? (
              <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
                Loading saved drafts...
              </div>
            ) : draftPosts.length === 0 ? (
              <EmptyState
                icon="📝"
                title="No saved drafts"
                description="You don't have any drafts saved yet. Open the composer and click 'Save as Draft' to save unfinished posts."
                size="md"
              />
            ) : (
              <div className="posts-grid-list">
                {draftPosts.map((draft) => (
                  <GlowCard key={draft.id} className="post-item-card" hover>
                    <div className="post-item-left" style={{ flex: 1 }}>
                      <div className="post-type-icon">📝</div>
                      <div className="post-info-meta" style={{ flex: 1 }}>
                        <div className="post-caption">
                          {draft.content ? draft.content : <em style={{ color: '#64748b' }}>(Untitled / Empty draft)</em>}
                        </div>
                        <div className="post-sub-meta">
                          <span>Format: <strong>{draft.post_type}</strong></span>
                          <span>•</span>
                          <span>
                            Accounts:{' '}
                            {draft.social_accounts && draft.social_accounts.length > 0 ? (
                              draft.social_accounts.map((sa) => {
                                const meta = PLATFORM_META[sa.platform.toLowerCase()] || { icon: '📱', label: sa.platform }
                                return (
                                  <span key={sa.id} style={{ marginRight: '6px' }}>
                                    {meta.icon} {meta.label}
                                  </span>
                                )
                              })
                            ) : (
                              <em>None selected</em>
                            )}
                          </span>
                          <span>•</span>
                          <span>Last updated: {new Date(draft.updated_at || draft.created_at).toLocaleDateString()}</span>
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <StatusBadge status="info" label="DRAFT" showDot />
                      {draft.social_accounts && draft.social_accounts.length > 0 && (
                        <button
                          type="button"
                          className="btn-action-publish-gradient"
                          style={{ padding: '6px 12px', fontSize: '11px' }}
                          disabled={publishingPostId === draft.id}
                          onClick={() => handlePublishNow(draft)}
                          title="Force publish this draft immediately"
                        >
                          {publishingPostId === draft.id ? 'Publishing...' : '🚀 Publish'}
                        </button>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleEditDraft(draft)}
                        title="Edit this draft"
                      >
                        ✏️ Edit
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeletePost(draft.id)}
                        style={{ color: '#ef4444', padding: '4px 8px' }}
                        title="Delete this draft"
                      >
                        🗑️
                      </Button>
                    </div>
                  </GlowCard>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: RECURRING RULES (PHASE 4) */}
        {activeTab === 'recurring' && (
          <div style={{ marginTop: '20px' }}>
            <div style={{ marginBottom: '16px' }}>
              <h3 className="section-heading" style={{ margin: 0 }}>
                Active Recurring Schedules ({recurringRules.length})
              </h3>
              <p className="section-subheading" style={{ margin: 0, marginTop: '4px' }}>
                Manage repeating post schedules, next run dates, and occurrence boundaries
              </p>
            </div>

            {isLoadingRecurring ? (
              <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
                Loading recurring schedules...
              </div>
            ) : recurringRules.length === 0 ? (
              <EmptyState
                icon="🔄"
                title="No recurring schedules"
                description="You haven't set up any recurring posts yet. Open '+ Create Post' and choose 'Recurring Post' to schedule repeating content."
                size="md"
              />
            ) : (
              <div className="posts-grid-list">
                {recurringRules.map((rule) => {
                  const nextRunFormatted = rule.next_run_at
                    ? new Date(rule.next_run_at).toLocaleString(undefined, {
                        dateStyle: 'medium',
                        timeStyle: 'short',
                      })
                    : 'None scheduled'
                  const endFormatted = rule.end_at
                    ? new Date(rule.end_at).toLocaleDateString(undefined, { dateStyle: 'medium' })
                    : 'Indefinite'

                  const freqDisplay = rule.frequency.toUpperCase() + (
                    rule.frequency.toLowerCase() === 'weekly' && rule.by_weekday !== null && rule.by_weekday !== undefined
                      ? ` (${['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][rule.by_weekday]})`
                      : rule.frequency.toLowerCase() === 'monthly' && rule.by_month_day
                      ? ` (Day ${rule.by_month_day})`
                      : ''
                  )

                  return (
                    <GlowCard key={rule.id} className="post-item-card" hover>
                      <div className="post-item-left" style={{ flex: 1 }}>
                        <div className="post-type-icon">🔄</div>
                        <div className="post-info-meta" style={{ flex: 1 }}>
                          <div className="post-caption">{rule.content}</div>
                          <div className="post-sub-meta">
                            <span>Frequency: <strong>{freqDisplay}</strong></span>
                            <span>•</span>
                            <span>Next Run: <strong>{nextRunFormatted}</strong></span>
                            <span>•</span>
                            <span>End: <strong>{endFormatted}</strong></span>
                            <span>•</span>
                            <span>
                              Accounts:{' '}
                              {rule.social_accounts && rule.social_accounts.length > 0 ? (
                                rule.social_accounts.map((sa) => {
                                  const meta = PLATFORM_META[sa.platform.toLowerCase()] || { icon: '📱', label: sa.platform }
                                  return (
                                    <span key={sa.id} style={{ marginRight: '6px' }} title={`${meta.label}: ${sa.account_name}`}>
                                      {meta.icon} {meta.label}
                                    </span>
                                  )
                                })
                              ) : (
                                <em>None</em>
                              )}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <StatusBadge
                          status={rule.is_active ? 'success' : 'neutral'}
                          label={rule.is_active ? 'ACTIVE' : 'INACTIVE'}
                          showDot
                        />
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleToggleActiveRule(rule)}
                          title={rule.is_active ? 'Deactivate this rule' : 'Activate this rule'}
                        >
                          {rule.is_active ? 'Deactivate' : 'Activate'}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteRecurringRule(rule.id)}
                          style={{ color: '#ef4444', padding: '4px 8px' }}
                          title="Delete this recurring rule and its generated occurrences"
                        >
                          🗑️
                        </Button>
                      </div>
                    </GlowCard>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* Post Details Modal */}

        {selectedPost && (
          <div className="modal-backdrop" onClick={() => setSelectedPost(null)}>
            <div className="post-modal-card" onClick={(e) => e.stopPropagation()}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 className="section-heading" style={{ margin: 0 }}>
                  Post Details
                </h3>
                <button
                  type="button"
                  onClick={() => setSelectedPost(null)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#94a3b8',
                    fontSize: '18px',
                    cursor: 'pointer',
                  }}
                >
                  ✕
                </button>
              </div>

              <div>
                <StatusBadge
                  status={selectedPost.status === 'scheduled' ? 'warning' : selectedPost.status === 'published' ? 'success' : 'info'}
                  label={selectedPost.status.toUpperCase()}
                  showDot
                />
              </div>

              <div className="modal-detail-row">
                <span className="modal-detail-label">Post Content / Caption</span>
                <div className="modal-detail-content">
                  {selectedPost.content || <em>(Empty content)</em>}
                </div>
              </div>

              <div className="modal-detail-row">
                <span className="modal-detail-label">Target Social Accounts</span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '4px' }}>
                  {selectedPost.social_accounts && selectedPost.social_accounts.length > 0 ? (
                    selectedPost.social_accounts.map((sa) => {
                      const meta = PLATFORM_META[sa.platform.toLowerCase()] || { icon: '📱', label: sa.platform }
                      return (
                        <div
                          key={sa.id}
                          style={{
                            padding: '6px 12px',
                            background: 'rgba(255, 255, 255, 0.05)',
                            border: '1px solid rgba(255, 255, 255, 0.1)',
                            borderRadius: '8px',
                            fontSize: '12px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                          }}
                        >
                          <span>{meta.icon}</span>
                          <strong>{meta.label}</strong>
                          <span style={{ color: '#94a3b8' }}>({sa.account_name || sa.account_username})</span>
                        </div>
                      )
                    })
                  ) : (
                    <span style={{ fontSize: '12px', color: '#94a3b8' }}>No accounts attached</span>
                  )}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="modal-detail-row">
                  <span className="modal-detail-label">Scheduled Date & Time</span>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: '#f1f5f9' }}>
                    {selectedPost.scheduled_at
                      ? new Date(selectedPost.scheduled_at).toLocaleString(undefined, {
                          dateStyle: 'full',
                          timeStyle: 'short',
                        })
                      : 'Not scheduled (Draft)'}
                  </span>
                </div>
                <div className="modal-detail-row">
                  <span className="modal-detail-label">Format</span>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: '#f1f5f9' }}>
                    {CONTENT_TYPES.find((c) => c.id === selectedPost.post_type)?.label || selectedPost.post_type}
                  </span>
                </div>
              </div>

              {/* Phase 5: Publishing Results Section */}
              {selectedPost.publish_results && selectedPost.publish_results.length > 0 && (
                <div className="modal-detail-row">
                  <span className="modal-detail-label">Publishing Results (Phase 5)</span>
                  <div className="publish-results-container">
                    {selectedPost.publish_results.map((res) => {
                      const meta = PLATFORM_META[res.platform.toLowerCase()] || { icon: '📱', label: res.platform }
                      const isSuccess = res.status === 'published'

                      return (
                        <div key={res.id} className={`publish-result-row ${isSuccess ? 'success' : 'failed'}`}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span>{meta.icon}</span>
                            <strong>{meta.label}</strong>
                            <span className={`publish-status-tag ${isSuccess ? 'published' : 'failed'}`}>
                              {isSuccess ? '✓ Published' : '✗ Failed'}
                            </span>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            {res.published_url && (
                              <a
                                href={res.published_url}
                                target="_blank"
                                rel="noreferrer"
                                className="publish-link-btn"
                              >
                                View Post ↗
                              </a>
                            )}
                            {res.error_message && (
                              <span style={{ color: '#f87171', fontSize: '11px', maxWidth: '280px' }} title={res.error_message}>
                                ⚠️ {res.error_message.length > 40 ? res.error_message.slice(0, 40) + '...' : res.error_message}
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Phase 8: Publishing Queue & Retry Status */}
              {selectedPost.publishing_jobs && selectedPost.publishing_jobs.length > 0 && (
                <div className="modal-detail-row">
                  <span className="modal-detail-label">Publishing Queue & Retries (Phase 8)</span>
                  <div className="publish-results-container">
                    {selectedPost.publishing_jobs.map((job) => {
                      const plat = (job.platform || 'platform').toLowerCase()
                      const meta = PLATFORM_META[plat] || { icon: '📱', label: job.platform || 'Account' }
                      const status = job.status || 'queued'
                      let label = 'Queued'
                      if (status === 'processing') label = '⚙️ Processing...'
                      else if (status === 'retrying') label = `🔄 Retry scheduled (${job.attempt_count}/${job.max_attempts})`
                      else if (status === 'published') label = '✓ Published'
                      else if (status === 'failed') label = `✗ Failed (${job.attempt_count}/${job.max_attempts})`
                      else if (status === 'cancelled') label = '🚫 Cancelled'

                      return (
                        <div key={job.id} className={`publish-result-row ${status === 'published' ? 'success' : status === 'failed' ? 'failed' : ''}`}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span>{meta.icon}</span>
                            <strong>{meta.label}</strong>
                            <span className={`publish-status-tag ${status}`}>
                              {label}
                            </span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            {job.next_retry_at && status === 'retrying' && (
                              <span style={{ color: '#fb923c', fontSize: '11px' }}>
                                Next attempt: {new Date(job.next_retry_at).toLocaleTimeString()}
                              </span>
                            )}
                            {job.last_error && (
                              <span style={{ color: '#f87171', fontSize: '11px', maxWidth: '260px' }} title={job.last_error}>
                                ⚠️ {job.last_error.length > 35 ? job.last_error.slice(0, 35) + '...' : job.last_error}
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Phase 9: Publishing History & Timeline Section */}
              <div className="modal-detail-row">
                <span className="modal-detail-label">Publishing History & Timeline (Phase 9)</span>
                {isLoadingLogs ? (
                  <div style={{ color: '#94a3b8', fontSize: '12px', padding: '8px 0' }}>Loading publishing history...</div>
                ) : publishingLogs && publishingLogs.length > 0 ? (
                  <div className="publish-results-container">
                    {publishingLogs.map((log) => {
                      const plat = (log.platform || 'platform').toLowerCase()
                      const meta = PLATFORM_META[plat] || { icon: '📱', label: log.platform }
                      const status = log.status || 'info'
                      const isSuccess = status === 'published'
                      const isFail = status === 'failed'

                      return (
                        <div key={log.id} className={`publish-result-row ${isSuccess ? 'success' : isFail ? 'failed' : ''}`}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span>{meta.icon}</span>
                            <strong>{meta.label}</strong>
                            <span className={`publish-status-tag ${status}`}>
                              {log.event_type}
                            </span>
                            <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                              Attempt #{log.attempt_number}
                            </span>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span style={{ fontSize: '11px', color: '#64748b' }}>
                              {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                            </span>
                            {log.published_url && (
                              <a
                                href={log.published_url}
                                target="_blank"
                                rel="noreferrer"
                                className="publish-link-btn"
                              >
                                View ↗
                              </a>
                            )}
                            {log.error_message && (
                              <span style={{ color: '#f87171', fontSize: '11px', maxWidth: '240px' }} title={log.error_message}>
                                ⚠️ {log.error_message.length > 30 ? log.error_message.slice(0, 30) + '...' : log.error_message}
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div style={{ color: '#64748b', fontSize: '12px', padding: '6px 0' }}>No publishing history events recorded yet.</div>
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px' }}>
                <Button
                  variant="ghost"
                  onClick={() => handleDeletePost(selectedPost.id)}
                  style={{ color: '#ef4444' }}
                >
                  🗑️ Delete Post
                </Button>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {['scheduled', 'failed', 'draft'].includes(selectedPost.status) && (
                    <button
                      type="button"
                      className="btn-publish-now"
                      disabled={publishingPostId === selectedPost.id}
                      onClick={() => handlePublishNow(selectedPost)}
                    >
                      {publishingPostId === selectedPost.id ? 'Publishing...' : 'Publish Now 🚀'}
                    </button>
                  )}
                  {selectedPost.status === 'draft' && (
                    <Button
                      variant="outline"
                      onClick={() => {
                        const p = selectedPost
                        setSelectedPost(null)
                        handleEditDraft(p)
                      }}
                    >
                      ✏️ Edit Draft
                    </Button>
                  )}
                  <Button variant="primary" onClick={() => setSelectedPost(null)}>
                    Close
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* PUBLISHING HISTORY & AUDIT LOGS MODAL (MATCHING SCREENSHOT 1) */}
        {logsModalPost && (
          <div className="modal-backdrop" onClick={() => setLogsModalPost(null)}>
            <div className="audit-logs-modal-dialog" onClick={(e) => e.stopPropagation()}>
              <div className="audit-logs-dialog-header">
                <div className="audit-logs-title-area">
                  <h3 className="audit-logs-main-title">📜 Publishing History & Audit Logs</h3>
                  <p className="audit-logs-sub-title">
                    Audited timeline for post: <strong>"{logsModalPost.content?.length > 40 ? logsModalPost.content.slice(0, 40) + '...' : (logsModalPost.content || 'Untitled')}"</strong>
                  </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    type="button"
                    className="btn-action-publish-gradient"
                    style={{ padding: '6px 14px', fontSize: '12px' }}
                    disabled={publishingPostId === logsModalPost.id}
                    onClick={() => handlePublishNow(logsModalPost)}
                    title="Force publish this post immediately across all connected channels"
                  >
                    {publishingPostId === logsModalPost.id ? 'Publishing...' : '🚀 Force Publish Now'}
                  </button>
                  <button
                    type="button"
                    className="audit-logs-dialog-close"
                    onClick={() => setLogsModalPost(null)}
                    title="Close modal"
                  >
                    ✕
                  </button>
                </div>
              </div>

              {/* View Mode Toggle: Visual Timeline vs. Raw Log File Content */}
              <div className="audit-view-mode-tabs">
                <button
                  type="button"
                  className={`audit-mode-tab-btn ${logViewMode === 'timeline' ? 'active' : ''}`}
                  onClick={() => setLogViewMode('timeline')}
                >
                  📊 Visual Timeline
                </button>
                <button
                  type="button"
                  className={`audit-mode-tab-btn ${logViewMode === 'raw' ? 'active' : ''}`}
                  onClick={() => {
                    setLogViewMode('raw')
                    if (!rawLogContent) loadRawLogContent(logsModalPost.id)
                  }}
                >
                  📄 View Raw Log File ({rawLogContent ? `${rawLogContent.split('\n').length} lines` : 'Show Content'})
                </button>
              </div>

              {/* Filters & Actions Bar */}
              <div className="audit-logs-bar">
                {logViewMode === 'timeline' ? (
                  <>
                    <div className="audit-filter-item">
                      <span className="audit-filter-label">Platform:</span>
                      <select
                        className="audit-select-dropdown"
                        value={logsPlatformFilter}
                        onChange={(e) => setLogsPlatformFilter(e.target.value)}
                      >
                        <option value="all">All Platforms</option>
                        <option value="facebook">Facebook</option>
                        <option value="instagram">Instagram</option>
                        <option value="linkedin">LinkedIn</option>
                        <option value="x">X (Twitter)</option>
                        <option value="youtube">YouTube</option>
                        <option value="pinterest">Pinterest</option>
                      </select>
                    </div>

                    <div className="audit-filter-item">
                      <span className="audit-filter-label">Status:</span>
                      <select
                        className="audit-select-dropdown"
                        value={logsStatusFilter}
                        onChange={(e) => setLogsStatusFilter(e.target.value)}
                      >
                        <option value="all">All Statuses</option>
                        <option value="published">Published</option>
                        <option value="failed">Failed</option>
                        <option value="retrying">Retrying</option>
                        <option value="queued">Queued</option>
                        <option value="processing">Processing</option>
                      </select>
                    </div>

                    <button
                      type="button"
                      className="btn-audit-refresh"
                      onClick={() => loadLogsForModal(logsModalPost.id)}
                      disabled={isLoadingLogs}
                    >
                      🔄 Refresh
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      className="btn-copy-raw-log"
                      onClick={handleCopyRawLog}
                    >
                      {copySuccess ? '✓ Copied to Clipboard!' : '📋 Copy Log Content'}
                    </button>

                    <button
                      type="button"
                      className="btn-audit-refresh"
                      onClick={() => loadRawLogContent(logsModalPost.id)}
                      disabled={isLoadingRawLog}
                    >
                      🔄 Reload Log
                    </button>
                  </>
                )}

                <button
                  type="button"
                  className="btn-audit-download-file"
                  onClick={(e) => handleDownloadLogFile(logsModalPost, e)}
                  disabled={isExportingLog}
                  title="Download and save the .log file to your computer"
                >
                  {isExportingLog ? '⏳ Downloading...' : '📥 Download Log File'}
                </button>
              </div>

              {/* Body Content: Timeline vs Raw Log File Terminal */}
              <div className="audit-logs-dialog-body">
                {logViewMode === 'raw' ? (
                  <div className="raw-log-viewer-box">
                    <div className="raw-log-status-bar">
                      <span>File: publishing_logs_{logsModalPost.id.slice(0, 8)}.log</span>
                      <span>Format: UTF-8 Plaintext Audit Trail</span>
                    </div>
                    {isLoadingRawLog ? (
                      <div className="audit-logs-state-text">Loading log file contents...</div>
                    ) : (
                      <pre className="raw-log-code-pre">{rawLogContent || 'No log records found for this post.'}</pre>
                    )}
                  </div>
                ) : isLoadingLogs ? (
                  <div className="audit-logs-state-text">Loading audit timeline...</div>
                ) : filteredLogs.length === 0 ? (
                  <div className="audit-logs-empty-message">
                    No publishing logs recorded yet for this post. Logs are created when publishing jobs are queued or processed.
                  </div>
                ) : (
                  <div className="audit-logs-items-list">
                    {filteredLogs.map((log) => {
                      const plat = (log.platform || 'platform').toLowerCase()
                      const meta = PLATFORM_META[plat] || { icon: '📱', label: log.platform }
                      const status = log.status || 'info'
                      const isSuccess = status === 'published'
                      const isFail = status === 'failed'

                      return (
                        <div key={log.id} className={`audit-log-entry-row ${isSuccess ? 'success' : isFail ? 'failed' : ''}`}>
                          <div className="log-entry-left">
                            <span className="log-platform-icon">{meta.icon}</span>
                            <strong className="log-platform-name">{meta.label}</strong>
                            <span className={`log-status-pill ${status}`}>
                              {log.event_type || status}
                            </span>
                            <span className="log-attempt-text">
                              Attempt #{log.attempt_number}
                            </span>
                          </div>

                          <div className="log-entry-right">
                            <span className="log-timestamp">
                              {new Date(log.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'medium' })}
                            </span>
                            {log.published_url && (
                              <a
                                href={log.published_url}
                                target="_blank"
                                rel="noreferrer"
                                className="log-url-link"
                              >
                                View Post ↗
                              </a>
                            )}
                            {log.error_message && (
                              <span className="log-error-text" title={log.error_message}>
                                ⚠️ {log.error_message}
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Dialog Footer */}
              <div className="audit-logs-dialog-footer">
                <button
                  type="button"
                  className="btn-audit-dialog-close"
                  onClick={() => setLogsModalPost(null)}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
