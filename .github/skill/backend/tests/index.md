# backend/tests/

## Purpose
pytest test suite for the backend. Covers unit tests (pure logic), integration tests (real DB + Redis via fixtures), and end-to-end smoke tests.

## Structure
```
backend/tests/
├── conftest.py             Shared fixtures: async DB session, Redis, test client, user/token factories
├── unit/
│   ├── test_security.py    hash_password, verify_password, JWT encode/decode, token generation
│   ├── test_queue_service.py  enqueue/dequeue logic with mocked Redis
│   ├── test_token_service.py  token creation, validation, scope enforcement
│   └── test_metrics_service.py  context-length suggestion thresholds
├── integration/
│   ├── test_auth.py        Login, refresh, logout, blocklist
│   ├── test_users.py       CRUD with real DB; role enforcement
│   ├── test_tokens.py      Token lifecycle; scope validation
│   ├── test_instances.py   Instance CRUD; start/stop (Docker SDK mocked)
│   ├── test_proxy.py       Proxy route token validation; queue bypass; context logging
│   ├── test_models.py      HF list (mocked); deploy flow
│   └── test_metrics.py     Metrics aggregation; suggestion logic end-to-end
└── e2e/
    └── smoke.py            Full flow: create user → generate token → start mock instance → send request → verify log
```

## Running Tests
```bash
# All tests (inside backend container)
pytest -v

# Unit only (no DB required)
pytest tests/unit -v

# With coverage
pytest --cov=app --cov-report=term-missing

# E2E smoke (requires running stack)
python tests/e2e/smoke.py
```

## Fixtures (conftest.py)
| Fixture | Scope | Provides |
|---|---|---|
| `db_session` | function | Async SQLAlchemy session; rolls back after each test |
| `redis_client` | session | Shared Redis connection (test DB `15`) |
| `client` | function | `AsyncClient` (httpx) wrapping the FastAPI app |
| `admin_user` | function | Pre-created admin `User` ORM object |
| `regular_user` | function | Pre-created regular `User` ORM object |
| `admin_token` | function | JWT for `admin_user` |
| `api_token` | function | Raw API token scoped to no instances (all-access) |
| `mock_docker` | function | `unittest.mock.patch` of `docker.DockerClient` |
| `mock_hf` | function | `unittest.mock.patch` of `HfApi` |

## Contracts
- No test connects to a real vLLM instance or the real HuggingFace API (all mocked).
- DB state is fully rolled back after each test function (no test pollution).
- Tests must pass with `pytest -n auto` (parallel execution via `pytest-xdist`).
