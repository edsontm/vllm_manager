# frontend/src/api/instancesApi.ts

## Purpose
Typed API client for vLLM instance management endpoints.

## Exported Functions

| Function | HTTP | Path |
|---|---|---|
| `listInstances(page?, size?)` | GET | `/instances` |
| `getInstance(id)` | GET | `/instances/{id}` |
| `createInstance(data)` | POST | `/instances` |
| `updateInstance(id, data)` | PATCH | `/instances/{id}` |
| `deleteInstance(id)` | DELETE | `/instances/{id}` |
| `startInstance(id)` | POST | `/instances/{id}/start` |
| `stopInstance(id)` | POST | `/instances/{id}/stop` |
| `restartInstance(id)` | POST | `/instances/{id}/restart` |
| `getInstanceStatus(id)` | GET | `/instances/{id}/status` |
| `getConnectionExamples(id)` | GET | `/instances/{id}/connection-examples` |
| `streamInstanceLogs(id, onLine)` | GET SSE | `/instances/{id}/logs` |

## Key Types
```ts
interface InstanceRead {
  id: number;
  slug: string;
  display_name: string;
  model_id: string;
  status: "stopped" | "starting" | "running" | "error";
  internal_port: number;
  gpu_ids: number[];
  tensor_parallel_size: number;
  max_model_len: number | null;
  max_num_seqs: number;
  enable_chunked_prefill: boolean;
  speculative_model: string | null;
  created_at: string;
}

interface ConnectionExamples {
  python: string;
  curl: string;
  javascript: string;
}
```
