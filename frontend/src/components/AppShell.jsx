/**
 * src/components/AppShell.jsx
 * ──────────────────────────
 * Reusable page wrapper that includes:
 * - Collapsible sidebar
 * - Sticky top bar
 * - Main content area
 *
 * All authenticated pages should use this wrapper.
 * Drop-in replacement for the old inline sidebar + dashboard div pattern.
 */

import { useState, useEffect } from 'react'
import Sidebar from './Sidebar'
import Navbar from './Navbar'
import './AppShell.css'

export default function AppShell({ children, pageTitle, pageSubtitle }) {
  const [mobileNav, setMobileNav] = useState(false)
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem('sp-sidebar-collapsed') === 'true'
  )

  useEffect(() => {
    localStorage.setItem('sp-sidebar-collapsed', collapsed)
    document.documentElement.style.setProperty(
      '--sidebar-current-width',
      collapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)'
    )
  }, [collapsed])

  // Close mobile nav on resize to desktop
  useEffect(() => {
    const handler = () => {
      if (window.innerWidth > 900) setMobileNav(false)
    }
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])

  return (
    <div className="sp-shell">
      <Sidebar
        mobileOpen={mobileNav}
        onCloseMobile={() => setMobileNav(false)}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((c) => !c)}
      />

      <div className={`sp-shell-content ${collapsed ? 'sidebar-collapsed' : ''}`}>
        <Navbar
          pageTitle={pageTitle}
          pageSubtitle={pageSubtitle}
          onMobileMenu={() => setMobileNav(true)}
          onSidebarToggle={() => setCollapsed((c) => !c)}
        />

        <main className="sp-shell-main">
          {children}
        </main>
      </div>
    </div>
  )
}
