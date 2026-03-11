import api from './base'

export type QueuePriorityRole = 'high_priority' | 'medium_priority' | 'low_priority'

export interface UserRead {
  id: number
  username: string
  email: string
  role: 'admin' | 'user'
  queue_priority_role: QueuePriorityRole
  is_active: boolean
  created_at: string
}

export interface UserCreate {
  username: string
  email: string
  password: string
  role?: 'admin' | 'user'
  queue_priority_role?: QueuePriorityRole
}

export interface UserUpdate {
  email?: string
  password?: string
  role?: 'admin' | 'user'
  queue_priority_role?: QueuePriorityRole
  is_active?: boolean
}

export interface UserList {
  items: UserRead[]
  total: number
  page: number
  size: number
}

export interface AbacPolicyRead {
  id: number
  subject_user_id: number | null
  subject_role: string | null
  resource_type: string
  resource_id: number | null
  action: string
  effect: 'allow' | 'deny'
  created_at: string
  created_by_id: number | null
}

export interface AbacPolicyCreate {
  subject_user_id?: number | null
  subject_role?: 'admin' | 'user' | null
  resource_type: 'instance' | 'model' | 'token' | 'queue' | 'user'
  resource_id?: number | null
  action: 'read' | 'create' | 'update' | 'delete' | 'start' | 'stop' | 'infer'
  effect: 'allow' | 'deny'
}

export interface AbacPolicyList {
  items: AbacPolicyRead[]
  total: number
  page: number
  size: number
}

export const usersApi = {
  list: async (page = 1, size = 20, search = ''): Promise<UserList> => {
    const { data } = await api.get<UserList>('/users', { params: { page, size, search } })
    return data
  },
  get: async (id: number): Promise<UserRead> => {
    const { data } = await api.get<UserRead>(`/users/${id}`)
    return data
  },
  create: async (body: UserCreate): Promise<UserRead> => {
    const { data } = await api.post<UserRead>('/users', body)
    return data
  },
  update: async (id: number, body: UserUpdate): Promise<UserRead> => {
    const { data } = await api.patch<UserRead>(`/users/${id}`, body)
    return data
  },
  delete: async (id: number): Promise<void> => {
    await api.delete(`/users/${id}`)
  },
  // Password management
  changeOwnPassword: async (currentPassword: string, newPassword: string): Promise<void> => {
    await api.patch('/users/me/password', { current_password: currentPassword, new_password: newPassword })
  },
  adminResetPassword: async (id: number, newPassword: string): Promise<void> => {
    await api.patch(`/users/${id}/password`, { new_password: newPassword })
  },
  // ABAC policies
  listPolicies: async (userId: number): Promise<AbacPolicyList> => {
    const { data } = await api.get<AbacPolicyList>(`/users/${userId}/policies`)
    return data
  },
  clearPolicies: async (userId: number): Promise<void> => {
    await api.delete(`/users/${userId}/policies`)
  },
  createPolicy: async (body: AbacPolicyCreate): Promise<AbacPolicyRead> => {
    const { data } = await api.post<AbacPolicyRead>('/policies', body)
    return data
  },
  deletePolicy: async (policyId: number): Promise<void> => {
    await api.delete(`/policies/${policyId}`)
  },
}
