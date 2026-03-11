import api from './base'

export interface TokenRead {
  id: number
  user_id: number
  name: string
  token: string | null
  token_prefix: string
  is_enabled: boolean
  scoped_instance_ids: number[]
  scoped_model_ids: string[]
  expires_at: string | null
  last_used_at: string | null
  created_at: string
  // Owner info — populated by the backend when the related User is loaded
  owner_username: string | null
  owner_queue_priority_role: 'high_priority' | 'medium_priority' | 'low_priority' | null
}

export interface TokenCreateResponse extends TokenRead {
  token: string
}

export interface TokenCreate {
  name: string
  /** Admin-only: assign the token to a specific user. Ignored for non-admins. */
  user_id?: number
  scoped_instance_ids?: number[]
  scoped_model_ids?: string[]
  expires_in_days?: number
}

export interface TokenUpdate {
  name?: string
  is_enabled?: boolean
  scoped_instance_ids?: number[]
  scoped_model_ids?: string[]
}

export const tokensApi = {
  list: async (): Promise<TokenRead[]> => {
    const { data } = await api.get<TokenRead[]>('/tokens')
    return data
  },
  create: async (body: TokenCreate): Promise<TokenCreateResponse> => {
    const { data } = await api.post<TokenCreateResponse>('/tokens', body)
    return data
  },
  update: async (id: number, body: TokenUpdate): Promise<TokenRead> => {
    const { data } = await api.patch<TokenRead>(`/tokens/${id}`, body)
    return data
  },
  revoke: async (id: number): Promise<void> => {
    await api.delete(`/tokens/${id}`)
  },
}

