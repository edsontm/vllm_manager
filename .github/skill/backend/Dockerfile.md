# backend/Dockerfile

## Purpose
Multi-stage Docker image for the FastAPI backend and workers. Produces a lean production image.

## Build Stages

### Stage 1: `builder`
- Base: `python:3.12-slim`
- Installs build dependencies (`gcc`, `libpq-dev`)
- Creates a virtualenv and installs all `requirements.txt` packages into it

### Stage 2: `runtime`
- Base: `python:3.12-slim`
- Copies only the virtualenv from `builder` (no build tools in prod image)
- Copies `app/` source
- Sets `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`
- Default `CMD`: `["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]`
- Worker override CMD: `["python", "-m", "app.workers.queue_worker"]`

## Docker Compose Services Using This Image
- `backend` — runs the FastAPI app
- `queue-worker` — runs the queue worker (same image, `command` override)
- `metrics-worker` — runs the metrics poller (same image, `command` override)

## Port
- Exposes `8080` internally. **Never exposed to host directly** — nginx proxies to it on `127.0.0.1:8080`.

## Volume Mounts (prod)
- `hf_cache:/home/vllm/.cache/huggingface` — shared with vLLM containers
- `/var/run/docker.sock:/var/run/docker.sock` — Docker SDK access for vllm_service
