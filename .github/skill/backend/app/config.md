# backend/app/config.py

## Purpose
Single source of truth for all application configuration. Uses `pydantic-settings` to load values from environment variables and the `.env` file.

## Exported Symbol
`Settings` — a `BaseSettings` subclass. A module-level singleton `settings = Settings()` is imported everywhere.

## Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `app_name` | `str` | `"vllm_manager"` | Application display name |
| `debug` | `bool` | `False` | Enable debug mode |
| `secret_key` | `str` | required | JWT signing secret (min 32 chars) |
| `algorithm` | `str` | `"HS256"` | JWT algorithm |
| `access_token_expire_minutes` | `int` | `60` | JWT TTL |
| `database_url` | `str` | required | PostgreSQL DSN |
| `redis_url` | `str` | required | Redis DSN |
| `hf_token` | `str` | optional | HuggingFace API token |
| `vllm_base_port` | `int` | `9000` | First port in the internal vLLM port range |
| `vllm_port_range` | `int` | `100` | Number of ports available for vLLM instances |
| `vllm_bind_host` | `str` | `"127.0.0.1"` | Host vLLM containers bind to (MUST remain 127.0.0.1) |
| `cors_origins` | `list[str]` | `["https://llm.ufms.br"]` | Allowed CORS origins |
| `queue_batch_size` | `int` | `16` | Max requests per vLLM batch |
| `queue_batch_timeout_ms` | `int` | `200` | Batch assembly window |
| `metrics_poll_interval_s` | `int` | `30` | Metrics worker polling interval |

## Environment Variables
All fields map directly to uppercase env var names (pydantic-settings convention), e.g. `SECRET_KEY`, `DATABASE_URL`.

## Constraints
- `vllm_bind_host` must always be `127.0.0.1`. Any other value breaks the security requirement that vLLM ports are never externally exposed.
- `cors_origins` must only list HTTPS origins in production.
