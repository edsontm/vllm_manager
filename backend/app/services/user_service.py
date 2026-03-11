from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import AdminPasswordReset, PasswordChange, UserCreate, UserUpdate


def _default_queue_priority_for_role(role: str) -> str:
    if role == "admin":
        return "high_priority"
    if role == "user":
        return "low_priority"
    return "medium_priority"


async def list_users(db: AsyncSession, page: int = 1, size: int = 20, search: str = "") -> tuple[list[User], int]:
    q = select(User)
    if search:
        q = q.where(User.username.ilike(f"{search}%") | User.email.ilike(f"{search}%"))
    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar_one()
    q = q.offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    return result.scalars().all(), total


async def get_user(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError(f"User {user_id} not found")
    return user


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    existing = await db.execute(
        select(User).where((User.username == data.username) | (User.email == data.email))
    )
    if existing.scalar_one_or_none():
        raise ConflictError("Username or email already exists")
    queue_priority_role = data.queue_priority_role or _default_queue_priority_for_role(data.role)
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=data.role,
        queue_priority_role=queue_priority_role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user_id: int, data: UserUpdate) -> User:
    user = await get_user(db, user_id)
    if data.email is not None:
        user.email = data.email
    if data.password is not None:
        user.hashed_password = hash_password(data.password)
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.role is not None:
        user.role = data.role
    if data.queue_priority_role is not None:
        user.queue_priority_role = data.queue_priority_role
    await db.flush()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: int) -> None:
    user = await get_user(db, user_id)
    user.is_active = False  # soft delete


async def change_own_password(db: AsyncSession, user, data: PasswordChange) -> None:
    """Self-service: validates current_password before changing."""
    if not verify_password(data.current_password, user.hashed_password):
        raise ForbiddenError("Current password is incorrect")
    if len(data.new_password) < 8:
        raise ConflictError("New password must be at least 8 characters")
    user.hashed_password = hash_password(data.new_password)
    await db.flush()


async def admin_reset_password(db: AsyncSession, user_id: int, data: AdminPasswordReset) -> None:
    """Admin resets any user's password without knowing the current one."""
    user = await get_user(db, user_id)
    if len(data.new_password) < 8:
        raise ConflictError("New password must be at least 8 characters")
    user.hashed_password = hash_password(data.new_password)
    await db.flush()
