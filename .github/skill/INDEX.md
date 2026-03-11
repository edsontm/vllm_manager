# vllm_manager — Skill Index

This index maps the project files covered by the skill documentation set. Each `.md` file documents the purpose, public interface, contracts, and usage examples for the associated code file.

## Reading this Index

- **Left column** — source file path (relative to project root)
- **Right column** — skill doc path (relative to `.github/skill/`)

All external access to vLLM runs exclusively through **ports 80/443 via nginx**. Internal ports are `127.0.0.1`-bound and never exposed externally.

---

## Root / Deployment

| Source file | Skill doc |
|---|---|
| `.env.example` | [env.example.md](env.example.md) |
| `docker-compose.yml` | [docker-compose.md](docker-compose.md) |
| `docker-compose.override.yml` | [docker-compose.override.md](docker-compose.override.md) |
| `nginx/vllm_manager.conf` | [nginx/vllm_manager.conf.md](nginx/vllm_manager.conf.md) |

---

## Backend

| Source file | Skill doc |
|---|---|
| `backend/Dockerfile` | [backend/Dockerfile.md](backend/Dockerfile.md) |
| `backend/requirements.txt` | [backend/requirements.md](backend/requirements.md) |
| `backend/alembic/` | [backend/alembic/index.md](backend/alembic/index.md) |
| `backend/tests/` | [backend/tests/index.md](backend/tests/index.md) |
| `backend/app/main.py` | [backend/app/main.md](backend/app/main.md) |
| `backend/app/config.py` | [backend/app/config.md](backend/app/config.md) |
| `backend/app/dependencies.py` | [backend/app/dependencies.md](backend/app/dependencies.md) |

### Core

| Source file | Skill doc |
|---|---|
| `backend/app/core/security.py` | [backend/app/core/security.md](backend/app/core/security.md) |
| `backend/app/core/logging.py` | [backend/app/core/logging.md](backend/app/core/logging.md) |
| `backend/app/core/exceptions.py` | [backend/app/core/exceptions.md](backend/app/core/exceptions.md) |
| `backend/app/core/abac.py` | [backend/app/core/abac.md](backend/app/core/abac.md) |

### Models (ORM)

| Source file | Skill doc |
|---|---|
| `backend/app/models/user.py` | [backend/app/models/user.md](backend/app/models/user.md) |
| `backend/app/models/access_token.py` | [backend/app/models/access_token.md](backend/app/models/access_token.md) |
| `backend/app/models/vllm_instance.py` | [backend/app/models/vllm_instance.md](backend/app/models/vllm_instance.md) |
| `backend/app/models/request_log.py` | [backend/app/models/request_log.md](backend/app/models/request_log.md) |
| `backend/app/models/abac_policy.py` | [backend/app/models/abac_policy.md](backend/app/models/abac_policy.md) |

### Schemas (Pydantic)

| Source file | Skill doc |
|---|---|
| `backend/app/schemas/` | [backend/app/schemas/index.md](backend/app/schemas/index.md) |

### Routers

| Source file | Skill doc |
|---|---|
| `backend/app/routers/auth.py` | [backend/app/routers/auth.md](backend/app/routers/auth.md) |
| `backend/app/routers/users.py` | [backend/app/routers/users.md](backend/app/routers/users.md) |
| `backend/app/routers/tokens.py` | [backend/app/routers/tokens.md](backend/app/routers/tokens.md) |
| `backend/app/routers/instances.py` | [backend/app/routers/instances.md](backend/app/routers/instances.md) |
| `backend/app/routers/metrics.py` | [backend/app/routers/metrics.md](backend/app/routers/metrics.md) |
| `backend/app/routers/queue.py` | [backend/app/routers/queue.md](backend/app/routers/queue.md) |
| `backend/app/routers/proxy.py` | [backend/app/routers/proxy.md](backend/app/routers/proxy.md) |
| `backend/app/routers/models.py` | [backend/app/routers/models.md](backend/app/routers/models.md) |
| `backend/app/routers/policies.py` | [backend/app/routers/policies.md](backend/app/routers/policies.md) |

### Services

| Source file | Skill doc |
|---|---|
| `backend/app/services/vllm_service.py` | [backend/app/services/vllm_service.md](backend/app/services/vllm_service.md) |
| `backend/app/services/token_service.py` | [backend/app/services/token_service.md](backend/app/services/token_service.md) |
| `backend/app/services/auth_service.py` | [backend/app/services/auth_service.md](backend/app/services/auth_service.md) |
| `backend/app/services/user_service.py` | [backend/app/services/user_service.md](backend/app/services/user_service.md) |
| `backend/app/services/queue_service.py` | [backend/app/services/queue_service.md](backend/app/services/queue_service.md) |
| `backend/app/services/hf_service.py` | [backend/app/services/hf_service.md](backend/app/services/hf_service.md) |
| `backend/app/services/metrics_service.py` | [backend/app/services/metrics_service.md](backend/app/services/metrics_service.md) |
| `backend/app/services/abac_service.py` | [backend/app/services/abac_service.md](backend/app/services/abac_service.md) |

### Workers

| Source file | Skill doc |
|---|---|
| `backend/app/workers/metrics_worker.py` | [backend/app/workers/metrics_worker.md](backend/app/workers/metrics_worker.md) |
| `backend/app/workers/queue_worker.py` | [backend/app/workers/queue_worker.md](backend/app/workers/queue_worker.md) |

---

## Frontend

| Source file | Skill doc |
|---|---|
| `frontend/Dockerfile` | [frontend/Dockerfile.md](frontend/Dockerfile.md) |
| `frontend/vite.config.ts` | [frontend/vite.config.md](frontend/vite.config.md) |
| `frontend/src/__tests__/` | [frontend/src/__tests__/index.md](frontend/src/__tests__/index.md) |
| `frontend/src/store/index.ts` | [frontend/src/store/index.md](frontend/src/store/index.md) |

### API Clients

| Source file | Skill doc |
|---|---|
| `frontend/src/api/base.ts` | [frontend/src/api/base.md](frontend/src/api/base.md) |
| `frontend/src/api/authApi.ts` | [frontend/src/api/authApi.md](frontend/src/api/authApi.md) |
| `frontend/src/api/instancesApi.ts` | [frontend/src/api/instancesApi.md](frontend/src/api/instancesApi.md) |
| `frontend/src/api/metricsApi.ts` | [frontend/src/api/metricsApi.md](frontend/src/api/metricsApi.md) |
| `frontend/src/api/modelsApi.ts` | [frontend/src/api/modelsApi.md](frontend/src/api/modelsApi.md) |
| `frontend/src/api/usersApi.ts` | [frontend/src/api/usersApi.md](frontend/src/api/usersApi.md) |
| `frontend/src/api/tokensApi.ts` | [frontend/src/api/tokensApi.md](frontend/src/api/tokensApi.md) |
| `frontend/src/api/queueApi.ts` | [frontend/src/api/queueApi.md](frontend/src/api/queueApi.md) |

### Pages

| Source file | Skill doc |
|---|---|
| `frontend/src/pages/Login.tsx` | [frontend/src/pages/Login.md](frontend/src/pages/Login.md) |
| `frontend/src/pages/Dashboard.tsx` | [frontend/src/pages/Dashboard.md](frontend/src/pages/Dashboard.md) |
| `frontend/src/pages/Instances.tsx` | [frontend/src/pages/Instances.md](frontend/src/pages/Instances.md) |
| `frontend/src/pages/Models.tsx` | [frontend/src/pages/Models.md](frontend/src/pages/Models.md) |
| `frontend/src/pages/Users.tsx` | [frontend/src/pages/Users.md](frontend/src/pages/Users.md) |
| `frontend/src/pages/Tokens.tsx` | [frontend/src/pages/Tokens.md](frontend/src/pages/Tokens.md) |
| `frontend/src/pages/Queue.tsx` | [frontend/src/pages/Queue.md](frontend/src/pages/Queue.md) |
| `frontend/src/pages/TestInterface.tsx` | [frontend/src/pages/TestInterface.md](frontend/src/pages/TestInterface.md) |
| `frontend/src/pages/StressTest.tsx` | [frontend/src/pages/StressTest.md](frontend/src/pages/StressTest.md) |

### Components

| Source file | Skill doc |
|---|---|
| `frontend/src/components/CodeExample.tsx` | [frontend/src/components/CodeExample.md](frontend/src/components/CodeExample.md) |
| `frontend/src/components/Layout.tsx` | [frontend/src/components/Layout.md](frontend/src/components/Layout.md) |
