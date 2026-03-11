# backend/app/main.py

## Purpose
Application entry point. Creates and configures the FastAPI instance, registers all routers, mounts CORS/middleware, and attaches global exception handlers.

## Responsibilities
- Instantiate `FastAPI` with title, version, and OpenAPI metadata.
- Include all feature routers with their URL prefixes and tags.
- Add `CORSMiddleware` (origins from `Settings.cors_origins`).
- Add `RequestIDMiddleware` (generates a unique `X-Request-ID` per request).
- Register global exception handlers from `core.exceptions`.
- Run startup/shutdown lifecycle hooks (DB connection pool, Redis ping).

## Registered Routers

| Prefix | Router module | Tag |
|---|---|---|
| `/auth` | `routers.auth` | Auth |
| `/users` | `routers.users` | Users |
| `/tokens` | `routers.tokens` | Tokens |
| `/instances` | `routers.instances` | Instances |
| `/models` | `routers.models` | Models |
| `/metrics` | `routers.metrics` | Metrics |
| `/v1` | `routers.proxy` | Proxy |
| `/queue` | `routers.queue` | Queue |

## Environment Variables Consumed
None directly — all via `config.Settings`.

## Usage
```bash
# development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# production (inside Docker)
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
```

## Contracts
- All routes are versioned under the prefix above; no bare `/v1/...` routes exist outside `routers.proxy`.
- The `/health` endpoint returns `{"status": "ok"}` and is unauthenticated (used by nginx upstream checks).

## Startup Port Check (Lifecycle Hook)
The `startup` event handler in `main.py` must verify critical ports before accepting traffic:

```python
import socket, logging

PORTS_REQUIRED = {
    "postgres": ("postgres", 5432),   # service name resolved inside Docker network
    "redis":    ("redis",    6379),
}

@app.on_event("startup")
async def check_dependencies():
    for name, (host, port) in PORTS_REQUIRED.items():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            if s.connect_ex((host, port)) != 0:
                logging.critical(f"Required dependency '{name}' not reachable at {host}:{port} — aborting")
                raise RuntimeError(f"{name} unreachable at startup")
        logging.info(f"Dependency '{name}' reachable at {host}:{port}")
```

This prevents the app from starting in a degraded state where DB or Redis is down, which would cause cryptic errors on the first real request instead of a clear early failure.
