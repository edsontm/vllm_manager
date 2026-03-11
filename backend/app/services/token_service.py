from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import generate_api_token, verify_api_token
from app.models.access_token import AccessToken
from app.models.request_log import RequestLog
from app.models.user import User
from app.schemas.token import TokenCreate, TokenUpdate

# How many leading characters of the raw token to store for display.
_TOKEN_PREFIX_LEN = 8


async def create_token(db: AsyncSession, user_id: int, data: TokenCreate) -> tuple[AccessToken, str]:
    raw, hashed = generate_api_token()
    token = AccessToken(
        user_id=user_id,
        name=data.name,
        hashed_token=hashed,
        raw_token=raw,
        token_prefix=raw[:_TOKEN_PREFIX_LEN],
        is_enabled=True,
        scoped_instance_ids=data.scoped_instance_ids or [],
        scoped_model_ids=data.scoped_model_ids or [],
        expires_at=data.expires_at,
    )
    db.add(token)
    await db.flush()
    await db.refresh(token)
    return token, raw


async def list_tokens(db: AsyncSession, user_id: int, is_admin: bool = False) -> list[AccessToken]:
    """Return tokens with the owner User eagerly loaded.

    Admins receive all tokens system-wide; regular users only see their own.
    """
    stmt = select(AccessToken).options(joinedload(AccessToken.user))
    if not is_admin:
        stmt = stmt.where(AccessToken.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_token(db: AsyncSession, token_id: int) -> AccessToken:
    result = await db.execute(select(AccessToken).where(AccessToken.id == token_id))
    token = result.scalar_one_or_none()
    if token is None:
        raise NotFoundError(f"Token {token_id} not found")
    return token


async def update_token(
    db: AsyncSession,
    token_id: int,
    data: TokenUpdate,
    requesting_user: User,
) -> AccessToken:
    token = await get_token(db, token_id)

    if requesting_user.role != "admin" and token.user_id != requesting_user.id:
        raise ForbiddenError("Cannot modify another user's token")

    if data.name is not None:
        token.name = data.name
    if data.is_enabled is not None:
        token.is_enabled = data.is_enabled
    if data.scoped_instance_ids is not None:
        token.scoped_instance_ids = data.scoped_instance_ids
    if data.scoped_model_ids is not None:
        token.scoped_model_ids = data.scoped_model_ids

    await db.flush()
    await db.refresh(token)
    return token


async def validate_token(db: AsyncSession, raw: str) -> AccessToken:
    result = await db.execute(select(AccessToken))
    tokens = result.scalars().all()
    for t in tokens:
        if verify_api_token(raw, t.hashed_token):
            if not t.is_enabled:
                raise UnauthorizedError("API token is disabled")
            if t.expires_at and t.expires_at < datetime.now(timezone.utc):
                raise UnauthorizedError("API token expired")
            return t
    raise UnauthorizedError("Invalid API token")


async def validate_token_scope(token: AccessToken, instance_id: int) -> None:
    if token.scoped_instance_ids and instance_id not in token.scoped_instance_ids:
        raise ForbiddenError("Token not scoped for this instance")


async def validate_model_scope(token: AccessToken, model_id: str) -> None:
    """Raise if the token is scoped to specific models and `model_id` is not in the list."""
    if token.scoped_model_ids and model_id not in token.scoped_model_ids:
        raise ForbiddenError(f"Token not allowed for model '{model_id}'")


async def revoke_token(db: AsyncSession, token_id: int, requesting_user: User) -> None:
    token = await get_token(db, token_id)
    if requesting_user.role != "admin" and token.user_id != requesting_user.id:
        raise ForbiddenError("Cannot revoke another user's token")
    await db.execute(
        update(RequestLog)
        .where(RequestLog.token_id == token.id)
        .values(token_id=None)
    )
    await db.delete(token)
    await db.commit()


async def revoke_all_user_tokens(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(AccessToken).where(AccessToken.user_id == user_id)
    )
    tokens = result.scalars().all()
    for t in tokens:
        await db.delete(t)
    await db.commit()
    return len(tokens)

