import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { ProfileProvider, useProfile } from './auth/ProfileContext'
import { ToastProvider } from './components/Toast'
import { ErrorBox, Loading } from './components/ui'
import Layout from './components/Layout'
import Login from './pages/Login'
import Register from './pages/Register'
import ForgotPassword from './pages/ForgotPassword'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import Bills from './pages/Bills'
import Budgets from './pages/Budgets'
import Analytics from './pages/Analytics'
import Goals from './pages/Goals'
import Notifications from './pages/Notifications'
import Reports from './pages/Reports'
import AiAssistant from './pages/AiAssistant'
import Settings from './pages/Settings'

/** 需要登录：启动恢复中显示加载；未登录跳转登录页 */
function AuthGate() {
  const { booting, token } = useAuth()
  if (booting) return <Loading text="正在恢复登录状态…" />
  if (!token) return <Navigate to="/login" replace />
  return <Outlet />
}

/** 需要完成财务资料初始化 */
function RequireProfile() {
  const { profile, loading, error, refresh } = useProfile()
  if (loading) return <Loading text="正在加载财务档案…" />
  if (error) return <ErrorBox text={error} onRetry={() => void refresh()} />
  if (profile && !profile.initialized) return <Navigate to="/onboarding" replace />
  return <Outlet />
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <ProfileProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route element={<AuthGate />}>
                <Route path="/onboarding" element={<Onboarding />} />
                <Route element={<RequireProfile />}>
                  <Route element={<Layout />}>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/bills" element={<Bills />} />
                    <Route path="/budgets" element={<Budgets />} />
                    <Route path="/analytics" element={<Analytics />} />
                    <Route path="/goals" element={<Goals />} />
                    <Route path="/notifications" element={<Notifications />} />
                    <Route path="/reports" element={<Reports />} />
                    <Route path="/ai" element={<AiAssistant />} />
                    <Route path="/settings" element={<Settings />} />
                  </Route>
                </Route>
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </ProfileProvider>
      </ToastProvider>
    </AuthProvider>
  )
}
