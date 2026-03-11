import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface CurrentUser {
  id: number
  username: string
  email: string
  role: 'admin' | 'user'
}

export interface Notification {
  id: string
  type: 'success' | 'error' | 'info' | 'warning'
  message: string
}

interface AuthState {
  isAuthenticated: boolean
  accessToken: string | null
  currentUser: CurrentUser | null
  setAuth: (token: string, user: CurrentUser) => void
  logout: () => void
}

interface UIState {
  sidebarOpen: boolean
  notifications: Notification[]
  toggleSidebar: () => void
  addNotification: (n: Omit<Notification, 'id'>) => void
  removeNotification: (id: string) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      isAuthenticated: false,
      accessToken: null,
      currentUser: null,
      setAuth: (token, user) =>
        set({ isAuthenticated: true, accessToken: token, currentUser: user }),
      logout: () =>
        set({ isAuthenticated: false, accessToken: null, currentUser: null }),
    }),
    { name: 'vllm-auth' },
  ),
)

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  notifications: [],
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  addNotification: (n) =>
    set((s) => ({
      notifications: [
        ...s.notifications,
        { ...n, id: Math.random().toString(36).slice(2) },
      ],
    })),
  removeNotification: (id) =>
    set((s) => ({ notifications: s.notifications.filter((n) => n.id !== id) })),
}))
