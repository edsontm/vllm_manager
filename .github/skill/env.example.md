# .env.example

## Purpose
Template for all required and optional environment variables. Copy to `.env` and fill in secret values before starting the stack.

**Never commit `.env` to version control.** `.gitignore` must include `.env`.

## Required Variables

```dotenv
# ── Application ──────────────────────────────────────────────
APP_NAME=vllm_manager
DEBUG=false

# JWT — generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=CHANGE_ME_use_secrets_token_hex_32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# ── Database ──────────────────────────────────────────────────
POSTGRES_USER=vllm_manager
POSTGRES_PASSWORD=CHANGE_ME
POSTGRES_DB=vllm_manager
DATABASE_URL=postgresql+asyncpg://vllm_manager:CHANGE_ME@postgres:5432/vllm_manager

# ── Redis ─────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ── HuggingFace ───────────────────────────────────────────────
# Required for gated models (obtain at https://huggingface.co/settings/tokens)
HF_TOKEN=hf_CHANGE_ME
HF_CACHE_DIR=/home/vllm/.cache/huggingface

# ── vLLM Instance Port Pool ───────────────────────────────────
# Internal ports bound to 127.0.0.1 only — NEVER exposed externally
VLLM_BASE_PORT=9000
VLLM_PORT_RANGE=100
VLLM_BIND_HOST=127.0.0.1      # MUST remain 127.0.0.1

# vLLM Docker image to use when starting instances
VLLM_DOCKER_IMAGE=vllm/vllm-openai:latest

# ── CORS ──────────────────────────────────────────────────────
# Comma-separated list of allowed origins (HTTPS only in production)
CORS_ORIGINS=https://llm.ufms.br

# ── Queue Worker ──────────────────────────────────────────────
QUEUE_BATCH_SIZE=16
QUEUE_BATCH_TIMEOUT_MS=200

# ── Metrics Worker ────────────────────────────────────────────
METRICS_POLL_INTERVAL_S=30

# ── Frontend (build-time Vite env) ───────────────────────────
# Set in docker-compose or CI; not read by Python
VITE_API_BASE_URL=/api
VITE_APP_TITLE=vLLM Manager
```

## Security Notes
- `SECRET_KEY` must be at least 32 random bytes. Rotate it to invalidate all existing JWTs.
- `VLLM_BIND_HOST` must always be `127.0.0.1`. Changing it to `0.0.0.0` exposes vLLM ports directly to the internet.
- `HF_TOKEN` grants access to your HuggingFace account and any private/gated models — treat it like a password.
- `POSTGRES_PASSWORD` and `REDIS_URL` should use strong, unique passwords in production.
