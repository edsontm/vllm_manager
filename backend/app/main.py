from __future__ import annotations

import socket
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import (
    http_exception_handler,
    unhandled_exception_handler,
    VllmError,
)
from app.core.exceptions import NotFoundError, UnauthorizedError, ForbiddenError, ConflictError, QueueFullError, HuggingFaceError
from app.core.logging import RequestIDMiddleware, configure_logging
from app.routers import (
    auth_router,
    instances_router,
    metrics_router,
    models_router,
    policies_router,
    proxy_router,
    queue_router,
    tokens_router,
    users_router,
)

configure_logging()
log = structlog.get_logger()


def _check_port(host: str, port: int, label: str) -> None:
    """Raise RuntimeError if *host:port* is not reachable within 3 s."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    try:
        result = sock.connect_ex((host, port))
        if result != 0:
            raise RuntimeError(f"Startup check failed: {label} ({host}:{port}) is not reachable")
    finally:
        sock.close()


def _host_port_from_url(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    return parsed.hostname or "localhost", parsed.port or 5432


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup: connectivity checks ─────────────────────────────────────────
    db_host, db_port = _host_port_from_url(settings.database_url)
    redis_host, redis_port = _host_port_from_url(settings.redis_url)
    log.info("startup.port_check.begin", db=f"{db_host}:{db_port}", redis=f"{redis_host}:{redis_port}")
    _check_port(db_host, db_port, "PostgreSQL")
    _check_port(redis_host, redis_port, "Redis")
    log.info("startup.port_check.ok", postgres="up", redis="up")

    yield
    # ── Shutdown ─────────────────────────────────────────────────────────────
    log.info("shutdown.complete")


app = FastAPI(
    title="vLLM Manager",
    version="1.0.0",
    description="Manage vLLM instances, tokens, and metrics.",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ────────────────────────────────────────────────────────
from fastapi import HTTPException as FastAPIHTTPException

for exc_cls in (
    NotFoundError,
    UnauthorizedError,
    ForbiddenError,
    ConflictError,
    VllmError,
    QueueFullError,
    HuggingFaceError,
):
    app.add_exception_handler(exc_cls, http_exception_handler)  # type: ignore[arg-type]

app.add_exception_handler(FastAPIHTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, unhandled_exception_handler)  # type: ignore[arg-type]

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(tokens_router, prefix="/api")
app.include_router(instances_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(queue_router, prefix="/api")
app.include_router(policies_router, prefix="/api")
# Proxy lives at /v1/{slug}/... — no /api prefix so nginx can route it separately
app.include_router(proxy_router)
