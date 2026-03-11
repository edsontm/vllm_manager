# docker-compose.yml

## Purpose
Defines all application services, networks, and volumes. Orchestrates the full vllm_manager stack for both development and production.

## Services

### `postgres`
| Setting | Value |
|---|---|
| Image | `postgres:16-alpine` |
| Port | `127.0.0.1:5432:5432` (localhost only) |
| Volume | `pgdata:/var/lib/postgresql/data` |
| Env | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` from `.env` |
| Health check | `pg_isready` every 10 s |

### `redis`
| Setting | Value |
|---|---|
| Image | `redis:7-alpine` |
| Port | `127.0.0.1:6379:6379` (localhost only) |
| Volume | `redisdata:/data` |
| Health check | `redis-cli ping` every 10 s |

### `backend`
| Setting | Value |
|---|---|
| Build | `./backend` |
| Port | `127.0.0.1:8088:8080` (localhost only — nginx proxy target) |
| Depends on | `postgres` (healthy), `redis` (healthy) |
| Volumes | `hf_cache:/home/vllm/.cache/huggingface`, `/var/run/docker.sock:/var/run/docker.sock` |
| Env file | `.env` |
| Command | `uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4` |

### `queue-worker`
| Setting | Value |
|---|---|
| Build | `./backend` (same image) |
| Command | `python -m app.workers.queue_worker` |
| Depends on | `backend`, `redis`, `postgres` |
| No exposed ports | internal only |

### `metrics-worker`
| Setting | Value |
|---|---|
| Build | `./backend` (same image) |
| Command | `python -m app.workers.metrics_worker` |
| Depends on | `backend`, `redis`, `postgres` |
| No exposed ports | internal only |

### `frontend` (dev only — see docker-compose.override.yml)
| Setting | Value |
|---|---|
| Build | `./frontend` |
| Port | `127.0.0.1:5174:5174` (localhost only — nginx proxy target in dev) |
| Command | `pnpm dev --host 0.0.0.0 --port 5174` |

## Networks
- All services share `vllm_network` (bridge driver).
- No service port is bound to `0.0.0.0`; all use `127.0.0.1:` prefix to prevent direct external access.

## Named Volumes
- `pgdata` — PostgreSQL data
- `redisdata` — Redis persistence
- `hf_cache` — HuggingFace model cache (shared between backend and future vLLM containers)

## Quick Start
```bash
cp .env.example .env
# Edit .env with secrets

# ── 1. Check required ports are free BEFORE starting ────────────
# These ports must not be in use by any other process:
#   5432 (postgres)  6379 (redis)  8088 (backend)  5174 (frontend dev)
for port in 5432 6379 8088 5174; do
  ss -tlnp | grep -q ":${port}" && echo "PORT $port IN USE — fix before starting" || echo "port $port OK"
done

# Development (with hot-reload)
docker compose up --build

# Production (build static frontend first)
docker compose -f docker-compose.yml up --build -d
```

## Run Migrations
```bash
docker compose exec backend alembic upgrade head
```
