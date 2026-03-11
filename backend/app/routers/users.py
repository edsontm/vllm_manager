from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.dependencies import get_admin_user, get_current_active_user, get_db, get_redis
from app.schemas.policy import AbacPolicyCreate, AbacPolicyList, AbacPolicyRead
from app.schemas.user import (
    AdminPasswordReset,
    PasswordChange,
    UserCreate,
    UserList,
    UserRead,
    UserUpdate,
)
from app.services import abac_service, user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=UserList)
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    users, total = await user_service.list_users(db, page, size, search)
    return UserList(items=users, total=total, page=page, size=size)


@router.get("/me", response_model=UserRead)
async def get_me(current_user=Depends(get_current_active_user)):
    return current_user


@router.patch("/me/password", status_code=204)
async def change_own_password(
    body: PasswordChange,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await user_service.change_own_password(db, current_user, body)
    from app.services import token_service
    await token_service.revoke_all_user_tokens(db, current_user.id)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, _admin=Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    return await user_service.get_user(db, user_id)


@router.post("", response_model=UserRead, status_code=201)
async def create_user(
    body: UserCreate, _admin=Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    return await user_service.create_user(db, body)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    body: UserUpdate,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin" and current_user.id != user_id:
        raise ForbiddenError("Cannot update another user's profile")
    if current_user.role != "admin" and body.role is not None:
        raise ForbiddenError("Cannot change your own role")
    return await user_service.update_user(db, user_id, body)


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: int, _admin=Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    await user_service.delete_user(db, user_id)


@router.patch("/{user_id}/password", status_code=204)
async def admin_reset_password(
    user_id: int,
    body: AdminPasswordReset,
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    await user_service.admin_reset_password(db, user_id, body)
    from app.services import token_service
    await token_service.revoke_all_user_tokens(db, user_id)


@router.get("/{user_id}/policies", response_model=AbacPolicyList)
async def list_user_policies(
    user_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    target = await user_service.get_user(db, user_id)
    policies = await abac_service.get_policies_for_user(target, db)
    start = (page - 1) * size
    page_items = policies[start: start + size]
    return AbacPolicyList(items=page_items, total=len(policies), page=page, size=size)


@router.delete("/{user_id}/policies", status_code=204)
async def clear_user_policies(
    user_id: int,
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    await abac_service.delete_all_for_user(db, user_id, redis)
