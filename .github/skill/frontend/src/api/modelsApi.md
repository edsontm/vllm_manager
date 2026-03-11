# frontend/src/api/modelsApi.ts

## Purpose
Typed API client for HuggingFace model discovery and instance model management.

## Exported Functions

| Function | HTTP | Path |
|---|---|---|
| `listAvailableModels(search?, limit?, offset?)` | GET | `/models/available` |
| `getModelInfo(modelId)` | GET | `/models/available/{modelId}` |
| `listLocalModels()` | GET | `/models/local` |
| `prefill(modelId)` | GET | `/models/prefill/{modelId}` |
| `deployModel(request)` | POST | `/models/deploy` |
| `switchModel(instanceId, request)` | POST | `/models/switch/{instanceId}` |
| `updateModel(instanceId)` | POST | `/models/update/{instanceId}` |
| `streamDeployProgress(jobId, onProgress)` | GET SSE | `/models/deploy/{jobId}/status` |

## Key Types
```ts
interface HFModelInfo {
  id: string;                    // e.g. "mistralai/Mistral-7B-Instruct-v0.2"
  downloads: number;
  likes: number;
  tags: string[];
  pipeline_tag: string;
  private: boolean;
  parameters?: number;           // total param count if available
  vram_required_gb: number | null; // estimated from .safetensors shard sizes × 1.2; null if unavailable
}

interface LocalModelInfo {
  id: string;                    // same format as HF model id ("org/name")
  local_path: string;
  size_gb: number;               // total disk footprint of the model directory
  last_modified: string;         // ISO 8601 timestamp
  vram_required_gb: number | null; // sum of local .safetensors sizes × 1.2 overhead; null if no safetensors files
}

/** Returned by GET /models/prefill/{modelId} — pre-populates the Create Instance drawer */
interface ModelPrefill {
  model_id: string;              // original HF id, e.g. "mistralai/Mistral-7B-Instruct-v0.2"
  suggested_slug: string;        // lowercased, hyphens, max 48 chars
  suggested_display_name: string; // title-cased model name tail
  vram_required_gb: number | null;
}

interface DeployModelRequest {
  model_id: string;
  slug: string;
  display_name: string;
  gpu_ids: number[];
  tensor_parallel_size: number;
  max_model_len?: number;
  auto_start: boolean;
}

interface DeployProgress {
  percent: number;
  file: string;
  done: boolean;
}
```

## VRAM Display Conventions
- Both `HFModelInfo` and `LocalModelInfo` carry `vram_required_gb`.
- The Models page renders an amber chip (e.g. `~14 GB VRAM`) on every card where the value is non-null.
- When `null`, the chip is omitted rather than showing "Unknown" — keeps cards clean for models with missing metadata.
- `prefill()` is called when the user clicks a model name; the returned `vram_required_gb` is passed along in `location.state` so the Create Instance drawer can show the estimate without an extra fetch.
