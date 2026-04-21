import api from './base'
import { useAuthStore } from '@/store'

export interface InstanceRead {
  id: number
  slug: string
  display_name: string
  model_id: string
  internal_port: number
  status: 'stopped' | 'starting' | 'running' | 'error' | 'pulling'
  error_message?: string | null
  warning_message?: string | null
  gpu_ids: number[]
  max_model_len: number | null
  gpu_memory_utilization: number
  tensor_parallel_size: number
  dtype: string
  quantization: string | null
  description: string | null
  extra_args: Record<string, string> | null
  created_at: string
}

export interface InstanceCreate {
  slug: string
  display_name: string
  model_id: string
  gpu_ids: number[]
  max_model_len?: number
  gpu_memory_utilization?: number
  tensor_parallel_size?: number
  dtype?: string
  quantization?: string
  description?: string
  extra_args?: Record<string, string>
}

export interface ConnectionExamples {
  curl: string
  python: string
  javascript: string
  openai_url: string
}

export const instancesApi = {
  list: async (): Promise<InstanceRead[]> => {
    const { data } = await api.get<InstanceRead[]>('/instances')
    return data
  },
  get: async (id: number): Promise<InstanceRead> => {
    const { data } = await api.get<InstanceRead>(`/instances/${id}`)
    return data
  },
  create: async (body: InstanceCreate): Promise<InstanceRead> => {
    const { data } = await api.post<InstanceRead>('/instances', body)
    return data
  },
  update: async (id: number, body: Partial<InstanceCreate>): Promise<InstanceRead> => {
    const { data } = await api.patch<InstanceRead>(`/instances/${id}`, body)
    return data
  },
  delete: async (id: number): Promise<void> => {
    await api.delete(`/instances/${id}`)
  },
  start: async (id: number): Promise<InstanceRead> => {
    const { data } = await api.post<InstanceRead>(`/instances/${id}/start`)
    return data
  },
  stop: async (id: number): Promise<InstanceRead> => {
    const { data } = await api.post<InstanceRead>(`/instances/${id}/stop`)
    return data
  },
  restart: async (id: number): Promise<InstanceRead> => {
    const { data } = await api.post<InstanceRead>(`/instances/${id}/restart`)
    return data
  },
  status: async (id: number): Promise<InstanceRead> => {
    const { data } = await api.get<InstanceRead>(`/instances/${id}/status`)
    return data
  },
  connectionExamples: async (id: number): Promise<ConnectionExamples> => {
    const { data } = await api.get<ConnectionExamples>(`/instances/${id}/connection-examples`)
    return data
  },
  /** Stream SSE logs. Returns a cancel function. */
  streamLogs: (id: number, onLine: (line: string) => void, tail = 300): (() => void) => {
    const token = useAuthStore.getState().accessToken
    const controller = new AbortController()
    fetch(`/api/instances/${id}/logs?tail=${tail}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok || !res.body) return
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const parts = buffer.split('\n')
          buffer = parts.pop() ?? ''
          for (const part of parts) {
            if (part.startsWith('data: ')) onLine(part.slice(6))
          }
        }
      })
      .catch(() => {})
    return () => controller.abort()
  },
}
