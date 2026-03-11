# backend/app/workers/metrics_worker.py

## Purpose
Background worker that periodically polls each running vLLM instance's Prometheus metrics endpoint and writes the results to Redis for the dashboard.

## Entry Point
```bash
python -m app.workers.metrics_worker
```
Runs as a separate Docker service (`queue-worker` image, different `CMD`).

## Poll Loop
1. Query DB for all `VllmInstance` records with `status == "running"`.
2. For each instance, HTTP GET `http://127.0.0.1:<port>/metrics` (Prometheus text format).
3. Parse relevant metrics:
   - `vllm:gpu_cache_usage_perc` → GPU KV-cache utilisation
   - `vllm:num_requests_running` → in-flight requests
   - `vllm:num_requests_waiting` → queue waiting in vLLM
   - `vllm:generation_tokens_total` → cumulative tokens generated
   - GPU utilisation and memory via `nvidia-smi` subprocess (or `pynvml`)
4. Call `services.metrics_service.write_live_metrics()` to store in Redis.
5. Sleep `settings.metrics_poll_interval_s` (default 30 s).

## Error Handling
- If an instance is unreachable, logs a warning and updates its Redis entry with `{"reachable": false}`.
- Does not crash the loop — continues polling other instances.
- If an instance's DB status is `running` but unreachable for > 3 consecutive polls, updates DB status to `error`.

## Environment Variables Consumed
- `DATABASE_URL`, `REDIS_URL`, `METRICS_POLL_INTERVAL_S`
