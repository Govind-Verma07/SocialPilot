/**
 * src/App.jsx
 * -----------
 * Root router. Defines all page routes with auth protection aligned strictly with SocialPilot PDF Spec.
 */

import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { NotificationProvider } from './context/NotificationContext'
import ProtectedRoute from './components/ProtectedRoute'
import LandingPage       from './pages/LandingPage'
import LoginPage         from './pages/LoginPage'
import RegisterPage      from './pages/RegisterPage'
import DashboardPage     from './pages/DashboardPage'
import AccountsPage      from './pages/AccountsPage'
import PostsPage         from './pages/PostsPage'
import CampaignsPage     from './pages/CampaignsPage'
import AnalyticsPage     from './pages/AnalyticsPage'
import NotificationsPage from './pages/NotificationsPage'
import ProfilePage       from './pages/ProfilePage'
import SettingsPage      from './pages/SettingsPage'
import TeamPage          from './pages/TeamPage'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <NotificationProvider>
          <Routes>
          <Route path="/"          element={<LandingPage />} />
          <Route path="/login"     element={<LoginPage />} />
          <Route path="/register"  element={<RegisterPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/accounts"
            element={
              <ProtectedRoute>
                <AccountsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/posts"
            element={
              <ProtectedRoute>
                <PostsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/calendar"
            element={
              <ProtectedRoute>
                <Navigate to="/posts?tab=calendar" replace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/drafts"
            element={
              <ProtectedRoute>
                <Navigate to="/posts?tab=drafts" replace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/recurring-posts"
            element={
              <ProtectedRoute>
                <Navigate to="/posts?tab=recurring" replace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/publishing-queue"
            element={
              <ProtectedRoute>
                <Navigate to="/posts?tab=queue" replace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/campaigns"
            element={
              <ProtectedRoute>
                <CampaignsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/analytics"
            element={
              <ProtectedRoute>
                <AnalyticsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/notifications"
            element={
              <ProtectedRoute>
                <NotificationsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <SettingsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/team"
            element={
              <ProtectedRoute>
                <TeamPage />
              </ProtectedRoute>
            }
          />
          {/* Catch-all → dashboard (ProtectedRoute will handle unauthenticated) */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
        </NotificationProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
