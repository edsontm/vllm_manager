# backend/requirements.txt

## Purpose
Python dependencies for the backend application and workers.

## Core Dependencies

| Package | Purpose |
|---|---|
| `fastapi` | Web framework |
| `uvicorn[standard]` | ASGI server (prod: `--workers 4`) |
| `pydantic-settings` | Settings management from env vars |
| `sqlalchemy[asyncio]` | ORM with async support |
| `asyncpg` | Async PostgreSQL driver |
| `alembic` | Database migrations |
| `redis[asyncio]` | Async Redis client |
| `python-jose[cryptography]` | JWT encode/decode |
| `passlib[bcrypt]` | Password hashing |
| `httpx` | Async HTTP client (proxy forwarding, health checks) |
| `docker` | Docker Python SDK (vllm_service) |
| `huggingface_hub` | HF model discovery and download |
| `structlog` | Structured JSON logging |
| `pynvml` | NVIDIA GPU metrics (metrics_worker) |

## Dev / Test Dependencies (requirements-dev.txt)
| Package | Purpose |
|---|---|
| `pytest` | Test runner |
| `pytest-asyncio` | Async test support |
| `httpx` | `TestClient` for FastAPI |
| `pytest-docker` | Spin up PostgreSQL + Redis for integration tests |
| `factory-boy` | ORM model factories |
| `faker` | Fake data generation |

## Version Pinning
- All packages pinned to exact versions in `requirements.txt`.
- `requirements-dev.txt` extends `requirements.txt` with `-r requirements.txt`.
