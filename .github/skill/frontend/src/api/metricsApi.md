# frontend/src/api/metricsApi.ts

## Purpose
Typed API client for performance metrics and context-length analytics endpoints.

## Exported Functions

| Function | HTTP | Path |
|---|---|---|
| `getMetricsSummary()` | GET | `/metrics` |
| `getInstanceMetrics(id)` | GET | `/metrics/{id}` |
| `getContextSuggestion(id)` | GET | `/metrics/{id}/context-suggestion` |
| `getMetricsHistory(id, hours)` | GET | `/metrics/{id}/history?hours={hours}` |

## Key Types
```ts
interface InstanceMetrics {
  instance_id: number;
  status: string;
  gpu_utilization_pct: number | null;
  gpu_memory_used_mb: number | null;
  tokens_per_second: number | null;
  avg_latency_ms: number | null;
  queue_depth: number;
  total_requests_1h: number;
  avg_context_length: number | null;
  p95_context_length: number | null;
}

interface ContextLengthSuggestion {
  instance_id: number;
  avg_context_length: number;
  current_max_model_len: number;
  suggested_max_model_len: number;
  suggestion_text: string;
}

interface MetricPoint {
  timestamp: string;
  tokens_per_second: number;
  avg_latency_ms: number;
  queue_depth: number;
  gpu_utilization_pct: number;
}
```
