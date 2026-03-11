# docker-compose.override.yml

## Purpose
Development overrides applied automatically by Docker Compose on top of `docker-compose.yml`. Enables hot-reload for both backend (Uvicorn `--reload`) and frontend (Vite HMR) without modifying the production compose file.

## Overrides

### `backend`
- Overrides `command` to: `uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload`
- Volume-mounts `./backend/app:/app/app` so code changes are reflected immediately without rebuilding the image.

### `queue-worker`
- Volume-mounts `./backend/app:/app/app` (same source mount so workers pick up local edits).
- `command` unchanged — no reload for workers (restart manually when changing worker code).

### `metrics-worker`
- Same volume mount as `queue-worker`.

### `frontend`
- Overrides `command` to: `pnpm dev --host 0.0.0.0 --port 5174`
- Volume-mounts `./frontend/src:/app/src` for HMR.
- Skips the multi-stage build (uses the `deps` stage only in dev).

## Usage
```bash
# ── Check ports before starting (dev) ───────────────────────────
# Required free ports: 8088 (backend), 5174 (frontend HMR),
# 5432 (postgres), 6379 (redis)
for port in 5432 6379 8088 5174; do
  ss -tlnp | grep -q ":${port}" && echo "PORT $port IN USE — fix before starting" || echo "port $port OK"
done

# Development (override is applied automatically)
docker compose up --build

# Production (skip the override file)
docker compose -f docker-compose.yml up --build -d
```

## Contracts
- This file is never used in CI or production deployments.
- It must never be committed with secrets hardcoded.
- Port bindings remain `127.0.0.1:`-prefixed even in development.
