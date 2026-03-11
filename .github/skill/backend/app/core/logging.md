# backend/app/core/logging.py

## Purpose
Configures `structlog` for JSON-structured, request-scoped logging across the entire backend. Provides the middleware that injects a `request_id` into every log entry.

## Key Components

### `configure_logging()`
Called once at startup in `main.py`. Sets up structlog processors: timestamp, log level, request ID, JSON renderer. Outputs to stdout so Docker/systemd can ship logs.

### `RequestIDMiddleware` (Starlette middleware)
- Generates `X-Request-ID` UUID per request (or forwards one from the incoming header).
- Binds it to the structlog context for the duration of the request.
- Adds `X-Request-ID` to the response headers.

### `log_inference_request(instance_id, user_id, context_length, latency_ms)`
Helper called by `routers.proxy` after each inference. Writes a structured log entry and inserts a `RequestLog` record via the background task queue.

## Log Fields (per request)
```json
{
  "timestamp": "2026-03-03T10:00:00Z",
  "level": "info",
  "request_id": "uuid",
  "method": "POST",
  "path": "/v1/my-model/chat/completions",
  "status_code": 200,
  "duration_ms": 342,
  "user_id": 7,
  "instance_id": 3,
  "context_length": 1024
}
```

## Contracts
- All log output is JSON (no plaintext lines in production).
- `context_length` is always logged for inference requests, even on error (set to `null` if parsing fails).
