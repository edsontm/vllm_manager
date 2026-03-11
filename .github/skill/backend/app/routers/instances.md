# backend/app/routers/instances.py

## Purpose
CRUD and lifecycle control for vLLM instances. Admins manage configuration; all authenticated users can read status.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/instances` | any authenticated | List all instances; error messages enriched from Redis |
| `POST` | `/instances` | admin | Create instance config (does not start it) |
| `GET` | `/instances/{id}` | any authenticated | Single instance detail |
| `PATCH` | `/instances/{id}` | admin | Update config |
| `DELETE` | `/instances/{id}` | admin | Delete config (stops container first if running) |
| `POST` | `/instances/{id}/start` | admin | Start Docker container via `vllm_service` |
| `POST` | `/instances/{id}/stop` | admin | Stop Docker container |
| `POST` | `/instances/{id}/restart` | admin | Stop then start (2 s delay) |
| `GET` | `/instances/{id}/status` | any authenticated | Live container state |
| `GET` | `/instances/{id}/logs` | admin | SSE stream of last N container log lines (`?tail=100`) |
| `GET` | `/instances/{id}/connection-examples` | any authenticated | curl, Python, JavaScript, and openai_url code snippets |

## Dependencies
- `get_admin_user`, `get_current_active_user`
- `services.vllm_service`

## Connection Examples
`GET /instances/{id}/connection-examples` returns `ConnectionExamples`:
```json
{
  "curl": "curl https://llm.ufms.br/v1/{slug}/chat/completions ...",
  "python": "from openai import OpenAI\\nclient = OpenAI(base_url='https://llm.ufms.br/v1/{slug}', ...)",
  "javascript": "import OpenAI from 'openai'; ...",
  "openai_url": "https://llm.ufms.br/v1/{slug}/"
}
```
All URLs use the configured `BASE_URL` — never raw internal ports.

## Contracts
- `start`/`restart` clear any stale `instance:error:{id}` key from Redis before starting.
- `/logs` streams as `text/event-stream` with `Cache-Control: no-cache` and `X-Accel-Buffering: no`.
