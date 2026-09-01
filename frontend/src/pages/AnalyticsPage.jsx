/**
 * src/pages/AnalyticsPage.jsx
 * ----------------------------
 * Analytics Dashboard Module & Reports Export Module (Modules 6 & 8 from PDF Spec).
 * Content Analytics, Audience Growth & Demographics, Campaign Analytics, PDF & Excel Export triggers.
 */

import { useState } from 'react'
import Sidebar from '../components/Sidebar'
import Navbar from '../components/Navbar'
import GlowCard from '../components/ui/GlowCard'
import Button from '../components/ui/Button'
import './AnalyticsPage.css'

export default function AnalyticsPage() {
  const [mobileNav, setMobileNav] = useState(false)
  const [exportNotice, setExportNotice] = useState('')

  const handleExportPDF = () => {
    setExportNotice('📄 Generating PDF Analytics & Campaign Report... File download starting!')
    setTimeout(() => setExportNotice(''), 4000)
  }

  const handleExportExcel = () => {
    setExportNotice('📊 Exporting Raw Analytics Data to Excel (.xlsx)... File download starting!')
    setTimeout(() => setExportNotice(''), 4000)
  }

  const chartData = [
    { day: 'Mon', val: 65 },
    { day: 'Tue', val: 85 },
    { day: 'Wed', val: 40 },
    { day: 'Thu', val: 95 },
    { day: 'Fri', val: 75 },
    { day: 'Sat', val: 110 },
    { day: 'Sun', val: 90 },
  ]

  const geoData = [
    { country: '🇺🇸 United States', percent: '38%', count: '14.2K followers' },
    { country: '🇮🇳 India', percent: '26%', count: '9.8K followers' },
    { country: '🇬🇧 United Kingdom', percent: '14%', count: '5.2K followers' },
    { country: '🇩🇪 Germany', percent: '12%', count: '4.5K followers' },
    { country: '🇨🇦 Canada', percent: '10%', count: '3.7K followers' },
  ]

  return (
    <div className="app-layout body-bg">
      <Sidebar mobileOpen={mobileNav} onCloseMobile={() => setMobileNav(false)} />

      <main className="app-main">
        <Navbar
          pageTitle="Analytics Dashboard & Reports Module"
          pageSubtitle="Track engagement, reach, impressions, audience growth, and export PDF/Excel reports"
          mobileMenuLabel="Open menu"
          onMobileMenu={() => setMobileNav(true)}
        />

        {/* Top Header Row with PDF & Excel Export Buttons */}
        <div className="analytics-top-bar">
          <div>
            <h2 className="section-heading">Cross-Platform Performance & Audience Analytics</h2>
            <p className="section-subheading" style={{ marginBottom: 0 }}>
              Real-time insights into content engagement, follower growth, and campaign ROI.
            </p>
          </div>
          <div className="export-actions">
            <Button variant="outline" onClick={handleExportPDF}>
              📄 Export PDF Report
            </Button>
            <Button variant="primary" onClick={handleExportExcel}>
              📊 Export Excel Data
            </Button>
          </div>
        </div>

        {/* Export Notification Banner */}
        {exportNotice && (
          <div className="alert alert-success" style={{ animation: 'fadeSlideIn 0.3s ease' }}>
            <span>✅</span>
            <span>{exportNotice}</span>
          </div>
        )}

        {/* Key Metric Stat Cards */}
        <div className="analytics-stats-grid">
          <GlowCard className="analytics-card" hover>
            <div style={{ fontSize: '12px', color: '#94a3b8' }}>Total Impressions</div>
            <div style={{ fontSize: '28px', fontWeight: 800, color: '#f1f5f9', margin: '4px 0' }}>184.5K</div>
            <div style={{ fontSize: '11px', color: '#10b981' }}>▲ +18.4% vs last month</div>
          </GlowCard>

          <GlowCard className="analytics-card" hover>
            <div style={{ fontSize: '12px', color: '#94a3b8' }}>Total Reach</div>
            <div style={{ fontSize: '28px', fontWeight: 800, color: '#f1f5f9', margin: '4px 0' }}>112.9K</div>
            <div style={{ fontSize: '11px', color: '#10b981' }}>▲ +12.1% unique users</div>
          </GlowCard>

          <GlowCard className="analytics-card" hover>
            <div style={{ fontSize: '12px', color: '#94a3b8' }}>Total Clicks & Link Taps</div>
            <div style={{ fontSize: '28px', fontWeight: 800, color: '#c084fc', margin: '4px 0' }}>14.8K</div>
            <div style={{ fontSize: '11px', color: '#10b981' }}>▲ 8.4% CTR Average</div>
          </GlowCard>

          <GlowCard className="analytics-card" hover>
            <div style={{ fontSize: '12px', color: '#94a3b8' }}>Engagement Rate</div>
            <div style={{ fontSize: '28px', fontWeight: 800, color: '#60a5fa', margin: '4px 0' }}>6.8%</div>
            <div style={{ fontSize: '11px', color: '#10b981' }}>▲ +2.3% benchmark</div>
          </GlowCard>
        </div>

        {/* Two Column Section: Content Performance Trends & Geographic Distribution */}
        <div className="analytics-grid-two">
          {/* Content Performance Bar Chart */}
          <GlowCard style={{ padding: '24px' }} hover>
            <div className="section-title-row">
              <h3 className="ds-title">Weekly Engagement & Reach Trends</h3>
              <span style={{ fontSize: '12px', color: '#94a3b8' }}>Past 7 Days</span>
            </div>

            <div className="bar-chart-simulated">
              {chartData.map((d) => (
                <div key={d.day} className="bar-col">
                  <div className="bar-fill" style={{ height: `${d.val}%` }} />
                  <span className="bar-lbl">{d.day}</span>
                </div>
              ))}
            </div>
          </GlowCard>

          {/* Geographic & Demographics */}
          <GlowCard style={{ padding: '24px' }} hover>
            <div className="section-title-row">
              <h3 className="ds-title">Audience Geographic Distribution</h3>
              <span style={{ fontSize: '12px', color: '#94a3b8' }}>Top Countries</span>
            </div>

            <div className="geo-list">
              {geoData.map((g) => (
                <div key={g.country} className="geo-item">
                  <span>{g.country}</span>
                  <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    <span style={{ fontSize: '12px', color: '#94a3b8' }}>{g.count}</span>
                    <strong style={{ color: '#c084fc' }}>{g.percent}</strong>
                  </div>
                </div>
              ))}
            </div>
          </GlowCard>
        </div>

        {/* Campaign Analytics & ROI Tracking */}
        <GlowCard style={{ padding: '24px' }} hover>
          <h3 className="section-heading">Campaign Analytics & Platform Comparison</h3>
          <p className="section-subheading">Side-by-side performance metrics across all social platforms.</p>

          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8' }}>
                <th style={{ padding: '12px' }}>Platform</th>
                <th style={{ padding: '12px' }}>Followers</th>
                <th style={{ padding: '12px' }}>Avg. Reach</th>
                <th style={{ padding: '12px' }}>Engagement</th>
                <th style={{ padding: '12px' }}>Campaign ROI</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <td style={{ padding: '12px' }}>📘 Facebook Pages</td>
                <td style={{ padding: '12px' }}>14,500</td>
                <td style={{ padding: '12px' }}>32.4K</td>
                <td style={{ padding: '12px' }}>5.4%</td>
                <td style={{ padding: '12px', color: '#10b981', fontWeight: '700' }}>+210%</td>
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <td style={{ padding: '12px' }}>📸 Instagram Business</td>
                <td style={{ padding: '12px' }}>22,100</td>
                <td style={{ padding: '12px' }}>54.1K</td>
                <td style={{ padding: '12px' }}>8.9%</td>
                <td style={{ padding: '12px', color: '#10b981', fontWeight: '700' }}>+340%</td>
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <td style={{ padding: '12px' }}>💼 LinkedIn Company</td>
                <td style={{ padding: '12px' }}>8,900</td>
                <td style={{ padding: '12px' }}>18.2K</td>
                <td style={{ padding: '12px' }}>6.2%</td>
                <td style={{ padding: '12px', color: '#10b981', fontWeight: '700' }}>+185%</td>
              </tr>
              <tr>
                <td style={{ padding: '12px' }}>𝕏 X (Twitter)</td>
                <td style={{ padding: '12px' }}>12,400</td>
                <td style={{ padding: '12px' }}>24.8K</td>
                <td style={{ padding: '12px' }}>4.1%</td>
                <td style={{ padding: '12px', color: '#10b981', fontWeight: '700' }}>+140%</td>
              </tr>
            </tbody>
          </table>
        </GlowCard>
      </main>
    </div>
  )
}
