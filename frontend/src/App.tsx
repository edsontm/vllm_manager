import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { useAuthStore } from '@/store'
import Dashboard from '@/pages/Dashboard'
import Instances from '@/pages/Instances'
import Models from '@/pages/Models'
import Users from '@/pages/Users'
import Tokens from '@/pages/Tokens'
import Queue from '@/pages/Queue'
import TestInterface from '@/pages/TestInterface'
import StressTest from '@/pages/StressTest'
import Login from '@/pages/Login'
import Layout from '@/components/Layout'

function RequireAuth() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />
}

function RequireAdmin() {
  const currentUser = useAuthStore((s) => s.currentUser)
  return currentUser?.role === 'admin' ? <Outlet /> : <Navigate to="/" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<RequireAuth />}>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/instances" element={<Instances />} />
            <Route path="/models" element={<Models />} />
            <Route path="/tokens" element={<Tokens />} />
            <Route path="/queue" element={<Queue />} />
            <Route path="/test" element={<TestInterface />} />
            <Route path="/stress" element={<StressTest />} />
            <Route element={<RequireAdmin />}>
              <Route path="/users" element={<Users />} />
            </Route>
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
