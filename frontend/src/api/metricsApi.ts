import api from './base'

export interface GpuInfo {
  index: number
  name: string
  memory_total_mb: number
  memory_used_mb: number
  memory_free_mb: number
  utilization_pct: number | null
}

export interface GpuSummary {
  gpus: GpuInfo[]
  system_memory_total_mb: number | null
  system_memory_used_mb: number | null
  system_memory_free_mb: number | null
}

export interface InstanceMetrics {
  instance_id: number
  slug: string
  status: string
  gpu_utilization_pct: number | null
  gpu_memory_used_mb: number | null
  gpu_memory_total_mb: number | null
  gpu_memory_by_index_mb: Record<string, number> | null
  tokens_per_second: number | null
  avg_latency_ms: number | null
  queue_depth: number
  requests_total_1h: number
  avg_context_length: number | null
  system_memory_used_mb: number | null
  system_memory_total_mb: number | null
}

export interface MetricsSummary {
  instances: InstanceMetrics[]
  total_requests_1h: number
  total_instance_gpu_memory_used_mb: number
  total_instance_system_memory_used_mb: number
}

export interface ContextLengthSuggestion {
  instance_id: number
  current_max_model_len: number | null
  avg_context_length: number
  suggestion: 'increase' | 'decrease' | 'ok'
  suggested_value: number | null
}

export const metricsApi = {
  gpus: async (): Promise<GpuSummary> => {
    const { data } = await api.get<GpuSummary>('/metrics/gpus')
    return data
  },
  summary: async (): Promise<MetricsSummary> => {
    const { data } = await api.get<MetricsSummary>('/metrics')
    return data
  },
  instance: async (id: number): Promise<InstanceMetrics> => {
    const { data } = await api.get<InstanceMetrics>(`/metrics/${id}`)
    return data
  },
  contextSuggestion: async (id: number): Promise<ContextLengthSuggestion> => {
    const { data } = await api.get<ContextLengthSuggestion>(`/metrics/${id}/context-suggestion`)
    return data
  },
  history: async (id: number): Promise<unknown[]> => {
    const { data } = await api.get<unknown[]>(`/metrics/${id}/history`)
    return data
  },
}
