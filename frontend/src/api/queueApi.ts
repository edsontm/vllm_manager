import api from './base'

export interface QueueStatus {
  instance_id: number
  slug: string
  depth: number
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
}
