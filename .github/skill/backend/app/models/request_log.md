# backend/app/models/request_log.py

## Purpose
SQLAlchemy ORM model for the `request_logs` table. Records every inference request that passes through the proxy for performance analysis, context-length tracking, and audit.

## Table: `request_logs`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `BigInteger` | PK, autoincrement | |
| `user_id` | `Integer` | FK `users.id`, nullable | Null if token deleted |
| `instance_id` | `Integer` | FK `vllm_instances.id`, nullable | Null if instance deleted |
| `token_id` | `Integer` | FK `access_tokens.id`, nullable | Which token was used |
| `request_id` | `UUID` | NOT NULL | `X-Request-ID` for correlation with logs |
| `prompt_tokens` | `Integer` | nullable | Token count of the prompt |
| `completion_tokens` | `Integer` | nullable | Token count of the completion |
| `context_length` | `Integer` | nullable | `prompt_tokens + completion_tokens` |
| `latency_ms` | `Integer` | nullable | Total wall-clock time |
| `status_code` | `SmallInteger` | NOT NULL | HTTP status returned to client |
| `error_message` | `Text` | nullable | Error detail on non-2xx |
| `created_at` | `DateTime(tz=True)` | server_default `now()` | Request timestamp |

## Indexes
- `(instance_id, created_at)` — for metrics aggregation queries
- `(user_id, created_at)` — for per-user analytics

## Contracts
- Rows are inserted asynchronously via background task — never in the hot path of the proxy response.
- `context_length` is used by `services.metrics_service` to compute the rolling average and generate adjustment suggestions.
- Rows are never deleted; archiving strategy (e.g. pg_partman by month) is a future enhancement.
