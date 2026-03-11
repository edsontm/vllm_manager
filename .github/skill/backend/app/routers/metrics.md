# backend/app/routers/metrics.py

## Purpose
Aggregated performance metrics for the dashboard and per-instance analytics. Includes the context-length suggestion engine.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/metrics/gpus` | any authenticated | Per-GPU VRAM and utilization summary (pynvml or nvidia-smi fallback) |
| `GET` | `/metrics` | any authenticated | Summary metrics for all instances |
| `GET` | `/metrics/{instance_id}` | any authenticated | Detailed metrics for one instance |
| `GET` | `/metrics/{instance_id}/context-suggestion` | any authenticated | Context-length adjustment suggestion |
| `GET` | `/metrics/{instance_id}/history` | any authenticated | Time-series data for charts (from request_logs) |

## Metrics Returned per Instance (`InstanceMetrics`)
```json
{
  "instance_id": 3,
  "slug": "mistral-7b",
  "status": "running",
  "gpu_utilization_pct": 87.4,
  "gpu_memory_used_mb": 14200,
  "gpu_memory_total_mb": 24576,
  "tokens_per_second": 342.1,
  "avg_latency_ms": 1240,
  "queue_depth": 5,
  "requests_total_1h": 1820,
  "avg_context_length": 1536
}
```
Live fields (`gpu_*`, `tokens_per_second`, `avg_latency_ms`) are `null` if no metrics worker data exists yet.

## Context-Length Suggestion Logic
- Computes rolling average of `context_length` from `request_logs` (last 1000 requests).
- If `avg_context_length > 0.8 × instance.max_model_len` → suggest increasing `max_model_len`.
- If `avg_context_length < 0.2 × instance.max_model_len` → suggest decreasing to save GPU memory.
- Response includes `suggestion_text` (human-readable) and `suggested_max_model_len` (integer).

## Data Sources
- Live GPU stats: pulled from Redis (written by `workers.metrics_worker` every 30 s).
- Historical data: queried from `request_logs` table.
- Queue depth: Redis `LLEN` on the instance's queue key.
