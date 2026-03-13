import api from './base'

export interface HFModelInfo {
  model_id: string
  author: string | null
  pipeline_tag: string | null
  downloads: number
  likes: number
  tags: string[]
  last_modified: string | null
  parameter_count_b: number | null
  vram_required_gb: number | null
  supports_image: boolean
  capabilities: string[]
}

export interface LocalModelInfo {
  model_id: string
  cache_path: string
  size_gb: number
  vram_required_gb: number | null
}

export interface ModelPrefill {
  model_id: string
  suggested_slug: string
  suggested_display_name: string
  vram_required_gb: number | null
}

export interface DeployModelRequest {
  model_id: string
  revision?: string
}

export interface SwitchModelRequest {
  model_id: string
}

export const modelsApi = {
  available: async (query = '', limit = 20, sort = 'downloads', task = 'all'): Promise<HFModelInfo[]> => {
    const { data } = await api.get<HFModelInfo[]>('/models/available', { params: { query, limit, sort, task } })
    return data
  },
  local: async (): Promise<LocalModelInfo[]> => {
    const { data } = await api.get<LocalModelInfo[]>('/models/local')
    return data
  },
  info: async (modelId: string): Promise<HFModelInfo> => {
    const { data } = await api.get<HFModelInfo>(`/models/${modelId}/info`)
    return data
  },
  prefill: async (modelId: string): Promise<ModelPrefill> => {
    const { data } = await api.get<ModelPrefill>(`/models/prefill/${modelId}`)
    return data
  },
  /** Returns an EventSource URL — caller is responsible for SSE handling. */
  deployUrl: () => '/api/models/deploy',
  switchModel: async (instanceId: number, modelId: string): Promise<void> => {
    await api.post(`/models/switch/${instanceId}`, { model_id: modelId })
  },
  updateWeightsUrl: (instanceId: number) => `/api/models/update/${instanceId}`,
}
