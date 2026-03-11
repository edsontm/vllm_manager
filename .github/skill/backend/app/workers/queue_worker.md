# backend/app/workers/queue_worker.py

## Purpose
Drains the per-instance Redis request queues, batches requests, forwards them to the appropriate vLLM instance, and publishes results back via Redis pub/sub.

## Entry Point
```bash
python -m app.workers.queue_worker
```
Runs as the `queue-worker` Docker service (same image as `backend`, different `CMD`).

## Worker Loop (per instance)
1. Query DB for all running instances.
2. Spawn one `asyncio` task per instance (fan-out, instances are independent).
3. Each task calls `services.queue_service.dequeue_batch()` with configured `batch_size` and `batch_timeout_ms`.
4. Forward each request in the batch as a concurrent `httpx` request to `http://127.0.0.1:<port>/v1/...`.
5. Collect responses; publish each via `services.queue_service.publish_result(job_id, result)`.
6. Insert `RequestLog` rows for each completed request (context_length, latency_ms, status_code).
7. Loop back to dequeue.

## Batching Strategy
- Does **not** merge multiple prompts into a single vLLM request (vLLM handles continuous batching natively).
- Instead, sends up to `batch_size` requests **concurrently** to vLLM (fan-out) to saturate the GPU.
- `batch_timeout_ms` prevents starvation when queue is nearly empty.

## Speculative Execution Note
- If `instance.speculative_model` is set, vLLM automatically uses draft tokens internally.
- The worker has no special handling — it just sends standard OpenAI-compatible requests.

## Error Handling
- If vLLM returns non-2xx, publishes `{"error": ..., "status_code": ...}` to the result channel.
- Failed requests are logged but not retried (caller can retry at the API level).

## Environment Variables Consumed
- `DATABASE_URL`, `REDIS_URL`, `QUEUE_BATCH_SIZE`, `QUEUE_BATCH_TIMEOUT_MS`
