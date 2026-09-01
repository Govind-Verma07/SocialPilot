/**
 * src/pages/NotificationsPage.jsx
 * --------------------------------
 * Notification Module (Module 7 from PDF Spec).
 * Scheduled post reminders, publishing status notifications, campaign alerts, and team activity updates.
 */

import { useState } from 'react'
import Sidebar from '../components/Sidebar'
import Navbar from '../components/Navbar'
import GlowCard from '../components/ui/GlowCard'
import Button from '../components/ui/Button'
import './NotificationsPage.css'

const INITIAL_NOTIFICATIONS = [
  {
    id: 'n-1',
    type: 'reminder',
    icon: '⏰',
    title: 'Post Reminder: Product Launch Announcement',
    desc: 'Scheduled to publish across Facebook, LinkedIn & X tomorrow at 10:00 AM.',
    time: '10 mins ago',
    unread: true,
  },
  {
    id: 'n-2',
    type: 'publishing',
    icon: '✅',
    title: 'Post Published Successfully',
    desc: 'Your Reel "Behind the scenes AI scheduler" was successfully published to Instagram & YouTube.',
    time: '2 hours ago',
    unread: true,
  },
  {
    id: 'n-3',
    type: 'campaign',
    icon: '🎯',
    title: 'Campaign Milestone Reached',
    desc: 'Q3 Product Awareness & Growth reached over 45,000 unique reach target!',
    time: 'Yesterday at 4:15 PM',
    unread: false,
  },
  {
    id: 'n-4',
    type: 'team',
    icon: '👥',
    title: 'Team Member Activity',
    desc: 'Aman Singh edited the draft for "5 Essential Social Media Strategies".',
    time: '2 days ago',
    unread: false,
  },
]

export default function NotificationsPage() {
  const [mobileNav, setMobileNav] = useState(false)
  const [filter, setFilter] = useState('all')
  const [notifs, setNotifs] = useState(INITIAL_NOTIFICATIONS)

  const handleMarkAllRead = () => {
    setNotifs(notifs.map((n) => ({ ...n, unread: false })))
  }

  const filteredNotifs = notifs.filter((n) => filter === 'all' || n.type === filter)

  return (
    <div className="app-layout body-bg">
      <Sidebar mobileOpen={mobileNav} onCloseMobile={() => setMobileNav(false)} />

      <main className="app-main">
        <Navbar
          pageTitle="Notifications & Alert Operations"
          pageSubtitle="Scheduled post reminders, publishing logs, campaign alerts, and team collaboration updates"
          mobileMenuLabel="Open menu"
          onMobileMenu={() => setMobileNav(true)}
        />

        <div className="posts-header-row">
          <div className="notifs-filter-row">
            <button
              className={`notif-filter-chip ${filter === 'all' ? 'active' : ''}`}
              onClick={() => setFilter('all')}
            >
              All Notifications ({notifs.length})
            </button>
            <button
              className={`notif-filter-chip ${filter === 'reminder' ? 'active' : ''}`}
              onClick={() => setFilter('reminder')}
            >
              ⏰ Scheduled Reminders
            </button>
            <button
              className={`notif-filter-chip ${filter === 'publishing' ? 'active' : ''}`}
              onClick={() => setFilter('publishing')}
            >
              ✅ Publishing Status
            </button>
            <button
              className={`notif-filter-chip ${filter === 'campaign' ? 'active' : ''}`}
              onClick={() => setFilter('campaign')}
            >
              🎯 Campaign Alerts
            </button>
            <button
              className={`notif-filter-chip ${filter === 'team' ? 'active' : ''}`}
              onClick={() => setFilter('team')}
            >
              👥 Team Activity
            </button>
          </div>

          <Button variant="ghost" size="sm" onClick={handleMarkAllRead}>
            Mark All as Read ✓
          </Button>
        </div>

        <div className="notifs-list">
          {filteredNotifs.map((n) => (
            <GlowCard
              key={n.id}
              className="notif-card"
              style={{
                background: n.unread ? 'rgba(124, 58, 237, 0.08)' : undefined,
                border: n.unread ? '1px solid rgba(124, 58, 237, 0.3)' : undefined,
              }}
              hover
            >
              <div className="notif-icon-box">{n.icon}</div>
              <div className="notif-content">
                <div className="notif-title">
                  {n.title} {n.unread && <span style={{ color: '#10b981', fontSize: '10px' }}>● NEW</span>}
                </div>
                <div className="notif-desc">{n.desc}</div>
                <div className="notif-time">{n.time}</div>
              </div>
            </GlowCard>
          ))}
        </div>
      </main>
    </div>
  )
}
