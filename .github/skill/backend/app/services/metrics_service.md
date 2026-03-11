# backend/app/services/metrics_service.py

## Purpose
Aggregates performance data from Redis (live GPU metrics) and PostgreSQL (`request_logs`) to produce the dashboard and per-instance analytics payloads. Also implements the context-length suggestion algorithm.

## Exported Class: `MetricsService`

### `async get_summary(db, redis) -> list[InstanceMetrics]`
Returns metrics for every running instance. Combines Redis live data with DB aggregates.

### `async get_instance_metrics(instance_id: int, db, redis) -> InstanceMetrics`
Full metrics object for a single instance (see `routers/metrics.md` for field list).

### `async get_context_suggestion(instance_id: int, db) -> ContextLengthSuggestion | None`
- Queries last 1000 `RequestLog` rows for the instance.
- Computes `avg_context_length` and `p95_context_length`.
- Compares against `instance.max_model_len`.
- Returns suggestion object or `None` if no action needed.

### `async get_history(instance_id: int, hours: int, db, redis) -> list[MetricPoint]`
Returns time-bucketed (5 min intervals) metrics for charting. Combines Redis hash history with DB aggregates.

### `async write_live_metrics(instance_id: int, metrics: dict, redis) -> None`
Called by `workers.metrics_worker`. Writes to `Redis HSET metrics:{instance_id}` and appends to a capped time-series list.

## Context-Length Suggestion Thresholds
| Condition | Action |
|---|---|
| `avg > 0.8 × max_model_len` | Suggest increasing `max_model_len` by 25% |
| `avg < 0.2 × max_model_len` | Suggest decreasing to `2 × avg` to reclaim GPU memory |
| Otherwise | No suggestion |

## Contracts
- Live metrics are always read from Redis (low-latency). DB is only queried for historical aggregation.
- If Redis has no data for an instance, live fields are returned as `null` (instance may have just started).
