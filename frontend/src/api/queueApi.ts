import api from './base'

export interface QueueStatus {
  instance_id: number
  slug: string
  depth: number
}

export interface QueueJob {
  job_id: string
  instance_slug: string
  method: string
  path: string
  priority: string
  enqueue_time: number
  model: string | null
  prompt_preview: string | null
  max_tokens: number | null
  stream: boolean
}

export const queueApi = {
  allDepths: async (): Promise<QueueStatus[]> => {
    const { data } = await api.get<QueueStatus[]>('/queue')
    return data
  },
  depth: async (instanceId: number): Promise<QueueStatus> => {
    const { data } = await api.get<QueueStatus>(`/queue/${instanceId}`)
    return data
  },
  clear: async (instanceId: number): Promise<{ cleared: number }> => {
    const { data } = await api.delete<{ cleared: number }>(`/queue/${instanceId}`)
    return data
  },
  listJobs: async (instanceId: number): Promise<QueueJob[]> => {
    const { data } = await api.get<QueueJob[]>(`/queue/${instanceId}/jobs`)
    return data
  },
}
