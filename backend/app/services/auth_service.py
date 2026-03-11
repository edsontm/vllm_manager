from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError
from app.core.security import verify_password
from app.models.user import User


async def authenticate_user(username: str, password: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Incorrect username or password")
    if not user.is_active:
        raise UnauthorizedError("User is inactive")
    return user
