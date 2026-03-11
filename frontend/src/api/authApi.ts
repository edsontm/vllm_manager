import api from './base'

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface UserRead {
  id: number
  username: string
  email: string
  role: 'admin' | 'user'
  is_active: boolean
  created_at: string
}

export const authApi = {
  login: async (username: string, password: string): Promise<LoginResponse> => {
    const { data } = await api.post<LoginResponse>('/auth/login', { username, password })
    return data
  },
  me: async (token?: string): Promise<UserRead> => {
    const { data } = await api.get<UserRead>('/users/me', {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    })
    return data
  },
  logout: async (): Promise<void> => {
    await api.post('/auth/logout')
  },
}
