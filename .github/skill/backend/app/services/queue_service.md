# backend/app/services/queue_service.py

## Purpose
Manages the per-instance, per-priority Redis request queues. Prioritises high-priority users over medium/low ones within each instance's work pool. All functions are module-level.

## Priority Levels
Three priority levels in descending order:
1. `high_priority`
2. `medium_priority`
3. `low_priority`

Each instance has **three separate Redis lists**, one per priority. Dequeue always drains higher-priority lists first.

## Queue Key Scheme
- Queue lists: `queue:instance:{instance_id}:{priority}` (e.g. `queue:instance:3:high_priority`)
- Result pub/sub channel: `result:{job_id}`

## Exported Functions

### `async enqueue(instance_id, payload, redis) -> tuple[str, int]`
- Determines priority from `payload["queue_priority_role"]` (defaults to `medium_priority`).
- `LPUSH queue:instance:{instance_id}:{priority}` with JSON-serialised payload.
- Returns `(job_id, total_depth)` where depth sums all three priority queues.

### `async dequeue_batch(instance_id, batch_size, timeout_ms, redis) -> list[dict]`
- Blocks on `BRPOP` across all three priority keys (high → medium → low) with `timeout=timeout_ms/1000`.
- Collects up to `batch_size` items non-blocking after the first; returns partial batch on timeout.
- Called exclusively by `workers.queue_worker`.

### `async get_depth(instance_id, redis) -> int`
Returns `LLEN` sum across all three priority queues for the instance.

### `async get_all_depths(instance_ids, redis) -> dict[int, int]`
Returns `{instance_id: total_depth}` for all given IDs using a pipelined `LLEN`.

### `async publish_result(job_id, result, redis) -> None`
`PUBLISH result:{job_id}` with JSON-serialised result.

### `async subscribe_result(job_id, redis, timeout_s) -> dict`
Subscribes to `result:{job_id}`, awaits a message, raises `asyncio.TimeoutError` if not received within `timeout_s` (default 60 s).

## Contracts
- Queue keys per instance are independent; a slow instance does not block others.
- `dequeue_batch` never blocks longer than `timeout_ms` to keep the worker responsive.
- The entire request lifecycle (enqueue → dequeue → forward → publish) is always in-band for all requests.
