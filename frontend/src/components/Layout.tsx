import { Outlet, NavLink } from 'react-router-dom'
import { useAuthStore, useUIStore } from '@/store'
import { authApi } from '@/api/authApi'
import {
  LayoutDashboard,
  Cpu,
  Library,
  Users,
  KeyRound,
  ListOrdered,
  TestTube2,
  Gauge,
  LogOut,
  Menu,
} from 'lucide-react'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/instances', label: 'Instances', icon: Cpu },
  { to: '/models', label: 'Models', icon: Library },
  { to: '/tokens', label: 'Tokens', icon: KeyRound },
  { to: '/queue', label: 'Queue', icon: ListOrdered },
  { to: '/test', label: 'Test', icon: TestTube2 },
  { to: '/stress', label: 'Stress Test', icon: Gauge },
  { to: '/users', label: 'Users (Admin)', icon: Users, adminOnly: true },
]

export default function Layout() {
  const { currentUser, logout } = useAuthStore()
  const { sidebarOpen, toggleSidebar } = useUIStore()

  const handleLogout = async () => {
    try { await authApi.logout() } catch { /* ignore */ }
    logout()
    window.location.href = '/login'
  }

  const visibleItems = navItems.filter((item) =>
    item.adminOnly ? currentUser?.role === 'admin' : true,
  )

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100">
      {/* Sidebar */}
      <aside
        className={`${sidebarOpen ? 'w-56' : 'w-16'} flex flex-col bg-gray-900 border-r border-gray-800 transition-all duration-200`}
      >
        <div className="flex items-center justify-between px-3 py-4 border-b border-gray-800">
          {sidebarOpen && (
            <span className="font-heading font-[800] text-lg text-white tracking-tight">
              vLLM Manager
            </span>
          )}
          <button onClick={toggleSidebar} className="p-1 rounded hover:bg-gray-800">
            <Menu size={18} />
          </button>
        </div>
        <nav className="flex-1 py-4 space-y-1 px-2 overflow-y-auto">
          {visibleItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-sans font-[200] transition-colors ${
                  isActive
                    ? 'bg-indigo-600 text-white'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <Icon size={16} className="shrink-0" />
              {sidebarOpen && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-gray-800 p-3">
          {sidebarOpen && (
            <p className="text-xs font-mono font-[300] text-gray-500 mb-2 truncate">
              {currentUser?.username}
            </p>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-red-400 transition-colors"
          >
            <LogOut size={16} />
            {sidebarOpen && <span>Logout</span>}
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
