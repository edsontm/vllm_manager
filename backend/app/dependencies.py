from __future__ import annotations

from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token

# ── Database ──────────────────────────────────────────────────────────────────
_engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
    pool_timeout=30,
)
_SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Redis ─────────────────────────────────────────────────────────────────────
_redis_pool = aioredis.from_url(settings.redis_url, decode_responses=True)


async def get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    return _redis_pool


# ── Auth ──────────────────────────────────────────────────────────────────────
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

DbDep = Depends(get_db)
RedisDep = Depends(get_redis)


async def get_current_user(
    token: str = Depends(_oauth2_scheme),
    db: AsyncSession = DbDep,
):
    from app.models.user import User  # local import to avoid circular
    from sqlalchemy import select

    try:
        payload = decode_access_token(token)
        user_id: int = int(payload["sub"])
    except (ValueError, KeyError):
        raise UnauthorizedError("Invalid or expired token")

    # check JWT blocklist
    redis = _redis_pool
    if await redis.get(f"blocklist:{payload.get('jti', '')}"):
        raise UnauthorizedError("Token has been revoked")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedError("User not found")
    return user


async def get_current_active_user(user=Depends(get_current_user)):
    if not user.is_active:
        raise ForbiddenError("Inactive user")
    return user


async def get_admin_user(user=Depends(get_current_active_user)):
    if user.role != "admin":
        raise ForbiddenError("Admin access required")
    return user


async def get_vllm_token(
    authorization: str = Header(...),
):
    """Validate a static Bearer API token for the vLLM proxy endpoints."""
    from app.models.access_token import AccessToken
    from app.core.security import verify_api_token
    from sqlalchemy import select

    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("Bearer token required")
    raw = authorization.removeprefix("Bearer ").strip()
    token_prefix = raw[:8]
    if not token_prefix:
        raise UnauthorizedError("Invalid API token")

    async with _SessionLocal() as db:
        result = await db.execute(
            select(AccessToken).where(AccessToken.token_prefix == token_prefix)
        )
        tokens = result.scalars().all()

    matched: AccessToken | None = None
    for t in tokens:
        if verify_api_token(raw, t.hashed_token):
            matched = t
            break

    if matched is None:
        raise UnauthorizedError("Invalid API token")

    if not matched.is_enabled:
        raise UnauthorizedError("API token is disabled")

    from datetime import datetime, timezone

    if matched.expires_at and matched.expires_at < datetime.now(timezone.utc):
        raise UnauthorizedError("API token expired")

    return matched
