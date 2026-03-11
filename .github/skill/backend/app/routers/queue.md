# backend/app/routers/queue.py

## Purpose
Queue monitoring endpoints for authenticated users. Exposes queue depth per instance and system-wide queue depth summaries.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/queue` | any authenticated | Returns queue depth for all known instances |
| `GET` | `/queue/{instance_id}` | any authenticated | Returns queue depth for a specific instance |

## Endpoint Details

### `GET /queue`
- Loads all instances from `vllm_service.list_instances`.
- Returns `[]` when no instances are registered.
- Reads queue depths in bulk using `queue_service.get_all_depths(instance_ids, redis)`.
- Response model: `list[QueueStatus]`.

### `GET /queue/{instance_id}`
- Verifies instance existence with `vllm_service.get_instance`.
- Reads depth with `queue_service.get_depth(instance_id, redis)`.
- Response model: `QueueStatus`.

## Dependencies
- `get_current_active_user` (authentication guard)
- `get_db` (`AsyncSession`)
- `get_redis` (`Redis`)
- `app.services.vllm_service`
- `app.services.queue_service`

## Response Model
`QueueStatus` includes:
- `instance_id`
- `slug`
- `depth`

## Contracts
- Endpoints are read-only and never mutate queue state.
- Queue depth is computed from Redis list lengths and reflects near-real-time state.
- Unauthenticated requests are rejected at dependency level.
