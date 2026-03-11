# frontend/src/api/queueApi.ts

## Purpose
Typed API client for queue status monitoring and batch configuration.

## Exported Functions

| Function | HTTP | Path |
|---|---|---|
| `getQueueStatus(instanceId)` | GET | `/queue/{instanceId}/status` |
| `getAllQueueStatuses()` | GET | `/queue/status` |
| `updateQueueConfig(instanceId, config)` | PATCH | `/queue/{instanceId}/config` |

## Key Types
```ts
interface QueueStatus {
  instance_id: number;
  depth: number;               // current number of queued jobs
  batch_size: number;          // configured max batch
  batch_timeout_ms: number;    // configured assembly window
  jobs_processed_1h: number;   // throughput indicator
}

interface QueueConfig {
  batch_size?: number;         // 1–512
  batch_timeout_ms?: number;   // 50–5000
}
```
