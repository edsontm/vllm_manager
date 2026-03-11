from __future__ import annotations

from datetime import timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import create_access_token, decode_access_token
from app.dependencies import get_current_user, get_db, get_redis
from app.schemas.token import LoginRequest, LoginResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.authenticate_user(body.username, body.password, db)
    expires = timedelta(minutes=settings.access_token_expire_minutes)
    token = create_access_token({"sub": str(user.id), "role": user.role}, expires)
    return LoginResponse(
        access_token=token,
        expires_in=int(expires.total_seconds()),
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh(user=Depends(get_current_user)):
    expires = timedelta(minutes=settings.access_token_expire_minutes)
    token = create_access_token({"sub": str(user.id), "role": user.role}, expires)
    return LoginResponse(access_token=token, expires_in=int(expires.total_seconds()))


@router.post("/logout", status_code=204)
async def logout(
    user=Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
):
    # blocklist the jti for the remaining TTL (use full expire window as upper bound)
    # Blocklist the user's subject for the remaining TTL
    jti = getattr(user, "id", str(user))
    await redis.setex(
        f"blocklist:{jti}",
        settings.access_token_expire_minutes * 60,
        "1",
    )
