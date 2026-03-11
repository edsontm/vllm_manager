from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_admin_user, get_db, get_redis
from app.schemas.policy import (
    AbacPolicyCreate,
    AbacPolicyList,
    AbacPolicyRead,
    AbacPolicyUpdate,
)
from app.services import abac_service

router = APIRouter(prefix="/policies", tags=["Policies"])


@router.get("", response_model=AbacPolicyList)
async def list_policies(
    user_id: int | None = Query(None),
    role: str | None = Query(None),
    resource_type: str | None = Query(None),
    action: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    policies, total = await abac_service.get_policies(
        db, user_id=user_id, role=role, resource_type=resource_type, action=action,
        page=page, size=size,
    )
    return AbacPolicyList(items=policies, total=total, page=page, size=size)


@router.post("", response_model=AbacPolicyRead, status_code=201)
async def create_policy(
    body: AbacPolicyCreate,
    admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    return await abac_service.create_policy(db, body, created_by=admin, redis=redis)


@router.get("/{policy_id}", response_model=AbacPolicyRead)
async def get_policy(
    policy_id: int,
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    policies, _ = await abac_service.get_policies(db, page=1, size=1)
    # Direct fetch
    from sqlalchemy import select
    from app.models.abac_policy import AbacPolicy
    from app.core.exceptions import NotFoundError

    result = await db.execute(select(AbacPolicy).where(AbacPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if policy is None:
        raise NotFoundError(f"Policy {policy_id} not found")
    return policy


@router.patch("/{policy_id}", response_model=AbacPolicyRead)
async def update_policy(
    policy_id: int,
    body: AbacPolicyUpdate,
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    return await abac_service.update_policy(db, policy_id, body, redis=redis)


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: int,
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    await abac_service.delete_policy(db, policy_id, redis=redis)
