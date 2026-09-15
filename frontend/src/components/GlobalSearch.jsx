/**
 * src/components/GlobalSearch.jsx
 * ------------------------------
 * Live, categorized, keyboard-navigable global search across all SocialPilot modules:
 * - Posts (Scheduled, Published)
 * - Drafts
 * - Social Accounts
 * - Campaigns
 * - Media & Recurring Rules
 * - Core Navigation & Quick Actions
 */

import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search,
  X,
  FileText,
  SquarePen,
  CalendarDays,
  BookMarked,
  Clock,
  RefreshCw,
  Users2,
  Megaphone,
  BarChart2,
  Bell,
  Settings,
  User,
  Loader2,
  ArrowRight,
  Sparkles,
  UsersRound,
} from 'lucide-react'
import postsApi from '../api/postsApi'
import socialApi from '../api/socialApi'
import './GlobalSearch.css'

// Built-in navigation destinations & actions
const APP_NAV_ITEMS = [
  {
    id: 'nav-dashboard',
    title: 'Dashboard Overview',
    subtitle: 'KPIs, performance summaries, and recent activity',
    category: 'Pages & Actions',
    path: '/dashboard',
    icon: BarChart2,
    badge: 'Page',
  },
  {
    id: 'nav-create-post',
    title: 'Create Post',
    subtitle: 'Publish or schedule text, images, carousels, videos, stories',
    category: 'Pages & Actions',
    path: '/posts?tab=create',
    icon: SquarePen,
    badge: 'Action',
  },
  {
    id: 'nav-all-posts',
    title: 'All Posts & History',
    subtitle: 'View, filter, and inspect published and queued content',
    category: 'Pages & Actions',
    path: '/posts',
    icon: FileText,
    badge: 'Page',
  },
  {
    id: 'nav-calendar',
    title: 'Publishing Calendar',
    subtitle: 'Interactive calendar view for scheduled posts',
    category: 'Pages & Actions',
    path: '/posts?tab=calendar',
    icon: CalendarDays,
    badge: 'View',
  },
  {
    id: 'nav-drafts',
    title: 'Drafts Management',
    subtitle: 'Work-in-progress content and unscheduled drafts',
    category: 'Pages & Actions',
    path: '/posts?tab=drafts',
    icon: BookMarked,
    badge: 'View',
  },
  {
    id: 'nav-queue',
    title: 'Publishing Queue',
    subtitle: 'Upcoming scheduled posts ready to be published',
    category: 'Pages & Actions',
    path: '/posts?tab=queue',
    icon: Clock,
    badge: 'Queue',
  },
  {
    id: 'nav-recurring',
    title: 'Recurring Posts & Rules',
    subtitle: 'Automated repeat schedules and periodic campaigns',
    category: 'Pages & Actions',
    path: '/posts?tab=recurring',
    icon: RefreshCw,
    badge: 'Automation',
  },
  {
    id: 'nav-accounts',
    title: 'Social Accounts',
    subtitle: 'Connect LinkedIn, Facebook, Instagram, X, Pinterest, YouTube',
    category: 'Pages & Actions',
    path: '/accounts',
    icon: Users2,
    badge: 'Channels',
  },
  {
    id: 'nav-campaigns',
    title: 'Campaigns & Goals',
    subtitle: 'Social marketing objectives, timelines, and budgets',
    category: 'Pages & Actions',
    path: '/campaigns',
    icon: Megaphone,
    badge: 'Marketing',
  },
  {
    id: 'nav-analytics',
    title: 'Analytics & Reports',
    subtitle: 'Engagement metrics, follower growth, and reach insights',
    category: 'Pages & Actions',
    path: '/analytics',
    icon: BarChart2,
    badge: 'Insights',
  },
  {
    id: 'nav-notifications',
    title: 'Notifications & Audit Logs',
    subtitle: 'System events, delivery notifications, and status alerts',
    category: 'Pages & Actions',
    path: '/notifications',
    icon: Bell,
    badge: 'Activity',
  },
  {
    id: 'nav-team',
    title: 'Team & Workspace',
    subtitle: 'Manage team members, roles, and collaborative workspaces',
    category: 'Pages & Actions',
    path: '/team',
    icon: UsersRound,
    badge: 'Workspace',
  },
  {
    id: 'nav-settings',
    title: 'Settings & Security',
    subtitle: 'Application configuration, notification controls, and account settings',
    category: 'Pages & Actions',
    path: '/settings',
    icon: Settings,
    badge: 'Settings',
  },
  {
    id: 'nav-profile',
    title: 'User Profile',
    subtitle: 'Manage your personal profile and display information',
    category: 'Pages & Actions',
    path: '/profile',
    icon: User,
    badge: 'Profile',
  },
]

// Fallback campaigns if none loaded
const DEFAULT_CAMPAIGNS = [
  { id: 'cmp-1', name: 'Q3 Product Awareness & Growth', objective: 'Brand Awareness & Engagement', platform: 'FB, IG, LinkedIn' },
  { id: 'cmp-2', name: 'Fall Influencer & Creator Showcase', objective: 'Lead Generation & Conversions', platform: 'Instagram & YouTube' },
  { id: 'cmp-3', name: 'SMB Founder Masterclass Webinar', objective: 'Webinar Registrations', platform: 'LinkedIn & X (Twitter)' },
]

export default function GlobalSearch({ isMobileOpen, onCloseMobileSearch }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)

  // Cached remote data
  const [posts, setPosts] = useState([])
  const [accounts, setAccounts] = useState([])
  const [recurringRules, setRecurringRules] = useState([])
  const [campaigns, setCampaigns] = useState(DEFAULT_CAMPAIGNS)
  const [hasLoadedData, setHasLoadedData] = useState(false)

  const containerRef = useRef(null)
  const inputRef = useRef(null)
  const resultsRef = useRef(null)

  // Fetch searchable application data once or on focus
  const loadSearchableData = useCallback(async () => {
    if (hasLoadedData) return
    setLoading(true)
    try {
      const [postsRes, accRes, recurRes] = await Promise.allSettled([
        postsApi.getPosts({ limit: 60 }),
        socialApi.getAccounts(),
        postsApi.getRecurringRules(),
      ])

      if (postsRes.status === 'fulfilled' && postsRes.value?.data) {
        const pItems = Array.isArray(postsRes.value.data.items)
          ? postsRes.value.data.items
          : Array.isArray(postsRes.value.data)
          ? postsRes.value.data
          : []
        setPosts(pItems)
      }

      if (accRes.status === 'fulfilled' && accRes.value?.data) {
        const aItems = Array.isArray(accRes.value.data) ? accRes.value.data : []
        setAccounts(aItems)
      }

      if (recurRes.status === 'fulfilled' && recurRes.value?.data) {
        const rItems = Array.isArray(recurRes.value.data)
          ? recurRes.value.data
          : Array.isArray(recurRes.value.data?.items)
          ? recurRes.value.data.items
          : []
        setRecurringRules(rItems)
      }

      // Load local campaigns if available
      try {
        const localCmps = localStorage.getItem('sp-campaigns')
        if (localCmps) {
          const parsed = JSON.parse(localCmps)
          if (Array.isArray(parsed) && parsed.length > 0) {
            setCampaigns(parsed)
          }
        }
      } catch {
        // ignore JSON errors
      }

      setHasLoadedData(true)
    } catch (err) {
      console.warn('GlobalSearch: Non-blocking data fetch issue', err)
    } finally {
      setLoading(false)
    }
  }, [hasLoadedData])

  // Global keyboard shortcut: Ctrl+K or Cmd+K to focus search
  useEffect(() => {
    const handleGlobalKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
        setIsOpen(true)
        loadSearchableData()
      }
    }
    window.addEventListener('keydown', handleGlobalKeyDown)
    return () => window.removeEventListener('keydown', handleGlobalKeyDown)
  }, [loadSearchableData])

  // Close search when clicking outside
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [])

  // Filter items matching query
  const filteredResults = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) {
      // When query is empty but search is open, show quick actions & primary destinations
      return {
        groups: [
          {
            category: 'Quick Actions & Pages',
            items: APP_NAV_ITEMS.slice(0, 7),
          },
        ],
        totalCount: 7,
      }
    }

    const groups = []

    // 1. Pages & Actions
    const matchedNav = APP_NAV_ITEMS.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        item.subtitle.toLowerCase().includes(q) ||
        item.badge.toLowerCase().includes(q)
    )
    if (matchedNav.length > 0) {
      groups.push({ category: 'Pages & Navigation', items: matchedNav })
    }

    // 2. Drafts
    const draftItems = posts
      .filter((p) => p.status === 'draft')
      .filter((p) => (p.content || '').toLowerCase().includes(q) || (p.title || '').toLowerCase().includes(q))
      .slice(0, 5)
      .map((p) => ({
        id: `draft-${p.id}`,
        title: (p.content || 'Untitled Draft').slice(0, 75),
        subtitle: `Draft • ${p.created_at ? new Date(p.created_at).toLocaleDateString() : 'Recent'}`,
        category: 'Drafts',
        path: '/posts?tab=drafts',
        icon: BookMarked,
        badge: 'Draft',
      }))
    if (draftItems.length > 0) {
      groups.push({ category: 'Drafts', items: draftItems })
    }

    // 3. Scheduled Posts / Queue
    const scheduledItems = posts
      .filter((p) => p.status === 'scheduled')
      .filter((p) => (p.content || '').toLowerCase().includes(q) || (p.title || '').toLowerCase().includes(q))
      .slice(0, 5)
      .map((p) => ({
        id: `sched-${p.id}`,
        title: (p.content || 'Scheduled Post').slice(0, 75),
        subtitle: `Scheduled for ${p.scheduled_at ? new Date(p.scheduled_at).toLocaleString() : 'queue'}`,
        category: 'Scheduled Posts',
        path: '/posts?tab=queue',
        icon: Clock,
        badge: 'Scheduled',
      }))
    if (scheduledItems.length > 0) {
      groups.push({ category: 'Scheduled Queue', items: scheduledItems })
    }

    // 4. Published Posts
    const publishedItems = posts
      .filter((p) => p.status === 'published')
      .filter((p) => (p.content || '').toLowerCase().includes(q) || (p.title || '').toLowerCase().includes(q))
      .slice(0, 5)
      .map((p) => ({
        id: `pub-${p.id}`,
        title: (p.content || 'Published Post').slice(0, 75),
        subtitle: `Published • ${p.published_at ? new Date(p.published_at).toLocaleDateString() : 'Done'}`,
        category: 'Published Posts',
        path: '/posts',
        icon: FileText,
        badge: 'Published',
      }))
    if (publishedItems.length > 0) {
      groups.push({ category: 'Published Posts', items: publishedItems })
    }

    // 5. Social Accounts
    const matchedAccounts = accounts
      .filter(
        (a) =>
          (a.name || '').toLowerCase().includes(q) ||
          (a.platform || '').toLowerCase().includes(q) ||
          (a.username || '').toLowerCase().includes(q)
      )
      .slice(0, 6)
      .map((a) => ({
        id: `acc-${a.id}`,
        title: a.name || a.username || `${a.platform} Account`,
        subtitle: `${(a.platform || 'Social').toUpperCase()} • ${a.status || 'Connected'}`,
        category: 'Social Accounts',
        path: '/accounts',
        icon: Users2,
        badge: a.platform || 'Channel',
      }))
    if (matchedAccounts.length > 0) {
      groups.push({ category: 'Social Accounts', items: matchedAccounts })
    }

    // 6. Campaigns
    const matchedCampaigns = campaigns
      .filter(
        (c) =>
          (c.name || '').toLowerCase().includes(q) ||
          (c.objective || '').toLowerCase().includes(q) ||
          (c.platform || '').toLowerCase().includes(q)
      )
      .slice(0, 5)
      .map((c) => ({
        id: `cmp-${c.id}`,
        title: c.name,
        subtitle: `${c.objective} • ${c.platform || 'Social'}`,
        category: 'Campaigns',
        path: '/campaigns',
        icon: Megaphone,
        badge: 'Campaign',
      }))
    if (matchedCampaigns.length > 0) {
      groups.push({ category: 'Campaigns', items: matchedCampaigns })
    }

    // 7. Recurring Rules
    const matchedRules = recurringRules
      .filter(
        (r) =>
          (r.title || '').toLowerCase().includes(q) ||
          (r.frequency || '').toLowerCase().includes(q) ||
          (r.cron_expression || '').toLowerCase().includes(q)
      )
      .slice(0, 4)
      .map((r) => ({
        id: `rule-${r.id}`,
        title: r.title || `Recurring ${r.frequency || 'Rule'}`,
        subtitle: `Repeats: ${r.frequency || r.cron_expression || 'Automated schedule'}`,
        category: 'Recurring Rules',
        path: '/posts?tab=recurring',
        icon: RefreshCw,
        badge: 'Recurring',
      }))
    if (matchedRules.length > 0) {
      groups.push({ category: 'Recurring Rules', items: matchedRules })
    }

    const totalCount = groups.reduce((acc, g) => acc + g.items.length, 0)
    return { groups, totalCount }
  }, [query, posts, accounts, campaigns, recurringRules])

  // Flattened list for index navigation
  const flatItems = useMemo(() => {
    return filteredResults.groups.flatMap((g) => g.items)
  }, [filteredResults])

  // Reset selected index when query changes
  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  // Handle item selection & navigation
  const handleSelect = (item) => {
    setIsOpen(false)
    setQuery('')
    if (onCloseMobileSearch) onCloseMobileSearch()
    navigate(item.path)
  }

  // Keyboard navigation within results
  const handleKeyDown = (e) => {
    if (!isOpen) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        setIsOpen(true)
        loadSearchableData()
      }
      return
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((prev) => (flatItems.length === 0 ? 0 : (prev + 1) % flatItems.length))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((prev) => (flatItems.length === 0 ? 0 : (prev - 1 + flatItems.length) % flatItems.length))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (flatItems[selectedIndex]) {
        handleSelect(flatItems[selectedIndex])
      }
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setIsOpen(false)
      if (onCloseMobileSearch) onCloseMobileSearch()
      inputRef.current?.blur()
    }
  }

  return (
    <div
      className={`sp-search-container ${isOpen ? 'is-open' : ''} ${isMobileOpen ? 'mobile-modal-open' : ''}`}
      ref={containerRef}
    >
      {/* Search Input Box */}
      <div className="sp-search-input-box">
        <Search size={15} className="sp-search-icon" />
        <input
          ref={inputRef}
          type="text"
          placeholder="Search posts, accounts, campaigns… (Ctrl+K)"
          className="sp-search-input"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            if (!isOpen) setIsOpen(true)
          }}
          onFocus={() => {
            setIsOpen(true)
            loadSearchableData()
          }}
          onKeyDown={handleKeyDown}
          aria-label="Search posts, drafts, accounts, campaigns"
          aria-expanded={isOpen}
          aria-controls="sp-search-dropdown"
          autoComplete="off"
          spellCheck="false"
        />

        {loading && <Loader2 size={14} className="sp-search-spinner" />}

        {query && (
          <button
            type="button"
            className="sp-search-clear-btn"
            onClick={() => {
              setQuery('')
              inputRef.current?.focus()
            }}
            aria-label="Clear search"
          >
            <X size={13} />
          </button>
        )}

        <kbd className="sp-search-kbd" title="Press Ctrl+K or Cmd+K to search">
          ⌘K
        </kbd>

        {isMobileOpen && (
          <button
            type="button"
            className="sp-search-close-mobile-btn"
            onClick={onCloseMobileSearch}
            aria-label="Close search"
          >
            Cancel
          </button>
        )}
      </div>

      {/* Results Dropdown / Modal */}
      {isOpen && (
        <div className="sp-search-dropdown" id="sp-search-dropdown" ref={resultsRef}>
          {filteredResults.groups.length === 0 ? (
            <div className="sp-search-empty-state">
              <div className="sp-search-empty-icon">
                <Search size={22} />
              </div>
              <p className="sp-search-empty-title">No results found for &ldquo;{query}&rdquo;</p>
              <p className="sp-search-empty-desc">
                Try searching by post text, channel (e.g. &lsquo;Instagram&rsquo; or &lsquo;LinkedIn&rsquo;), campaign name, or draft.
              </p>
            </div>
          ) : (
            <div className="sp-search-groups-list">
              {filteredResults.groups.map((group) => (
                <div key={group.category} className="sp-search-group">
                  <div className="sp-search-group-header">
                    <span className="sp-search-group-label">{group.category}</span>
                    <span className="sp-search-group-count">{group.items.length}</span>
                  </div>

                  <div className="sp-search-group-items">
                    {group.items.map((item) => {
                      const flatIdx = flatItems.findIndex((fi) => fi.id === item.id)
                      const isSelected = flatIdx === selectedIndex
                      const Icon = item.icon || Sparkles

                      return (
                        <div
                          key={item.id}
                          className={`sp-search-result-item ${isSelected ? 'selected' : ''}`}
                          onClick={() => handleSelect(item)}
                          onMouseEnter={() => setSelectedIndex(flatIdx)}
                          role="option"
                          aria-selected={isSelected}
                        >
                          <div className="sp-search-item-icon">
                            <Icon size={16} />
                          </div>

                          <div className="sp-search-item-details">
                            <span className="sp-search-item-title">{item.title}</span>
                            {item.subtitle && (
                              <span className="sp-search-item-subtitle">{item.subtitle}</span>
                            )}
                          </div>

                          <div className="sp-search-item-meta">
                            {item.badge && <span className="sp-search-item-badge">{item.badge}</span>}
                            <ArrowRight size={13} className="sp-search-item-arrow" />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Footer Guide */}
          <div className="sp-search-footer">
            <div className="sp-search-footer-hint">
              <span>Use <kbd>↑</kbd> <kbd>↓</kbd> to navigate</span>
              <span><kbd>Enter</kbd> to open</span>
              <span><kbd>Esc</kbd> to close</span>
            </div>
            <div className="sp-search-footer-brand">SocialPilot</div>
          </div>
        </div>
      )}
    </div>
  )
}
