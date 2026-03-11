from __future__ import annotations

import json
from typing import Literal

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.abac_policy import AbacPolicy
from app.schemas.policy import AbacPolicyCreate, AbacPolicyUpdate


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_policy(db: AsyncSession, policy_id: int) -> AbacPolicy:
    result = await db.execute(select(AbacPolicy).where(AbacPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if policy is None:
        raise NotFoundError(f"Policy {policy_id} not found")
    return policy


async def _invalidate_cache(redis, user_id: int | None) -> None:
    if redis is not None and user_id is not None:
        await redis.delete(f"abac:{user_id}")


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def get_policies(
    db: AsyncSession,
    *,
    user_id: int | None = None,
    role: str | None = None,
    resource_type: str | None = None,
    action: str | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[AbacPolicy], int]:
    q = select(AbacPolicy)
    if user_id is not None:
        q = q.where(AbacPolicy.subject_user_id == user_id)
    if role is not None:
        q = q.where(AbacPolicy.subject_role == role)
    if resource_type is not None:
        q = q.where(AbacPolicy.resource_type == resource_type)
    if action is not None:
        q = q.where(AbacPolicy.action == action)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    q = q.offset((page - 1) * size).limit(size)
    rows = (await db.execute(q)).scalars().all()
    return list(rows), total


async def get_policies_for_user(user, db: AsyncSession) -> list[AbacPolicy]:
    """All policies matching a specific user (user-specific OR role-level)."""
    q = select(AbacPolicy).where(
        or_(
            AbacPolicy.subject_user_id == user.id,
            (AbacPolicy.subject_user_id.is_(None)) & (AbacPolicy.subject_role == user.role),
        )
    )
    return list((await db.execute(q)).scalars().all())


async def create_policy(
    db: AsyncSession,
    data: AbacPolicyCreate,
    created_by,
    redis=None,
) -> AbacPolicy:
    policy = AbacPolicy(
        subject_user_id=data.subject_user_id,
        subject_role=data.subject_role,
        resource_type=data.resource_type,
        resource_id=data.resource_id,
        action=data.action,
        effect=data.effect,
        created_by_id=created_by.id,
    )
    db.add(policy)
    await db.flush()
    await db.refresh(policy)
    await _invalidate_cache(redis, data.subject_user_id)
    return policy


async def update_policy(
    db: AsyncSession,
    policy_id: int,
    data: AbacPolicyUpdate,
    redis=None,
) -> AbacPolicy:
    policy = await _get_policy(db, policy_id)
    if data.effect is not None:
        policy.effect = data.effect
    if data.resource_id is not None:
        policy.resource_id = data.resource_id
    await db.flush()
    await db.refresh(policy)
    await _invalidate_cache(redis, policy.subject_user_id)
    return policy


async def delete_policy(db: AsyncSession, policy_id: int, redis=None) -> None:
    policy = await _get_policy(db, policy_id)
    uid = policy.subject_user_id
    await db.delete(policy)
    await db.flush()
    await _invalidate_cache(redis, uid)


async def delete_all_for_user(db: AsyncSession, user_id: int, redis=None) -> int:
    result = await db.execute(
        delete(AbacPolicy).where(AbacPolicy.subject_user_id == user_id)
    )
    await db.flush()
    await _invalidate_cache(redis, user_id)
    return result.rowcount


# ── Evaluation ────────────────────────────────────────────────────────────────

async def evaluate(
    user,
    action: str,
    resource_type: str,
    resource_id: int | None,
    db: AsyncSession,
    redis=None,
) -> Literal["allow", "deny"]:
    """Deny-wins policy evaluation. Admins always get 'allow'."""
    if user.role == "admin":
        return "allow"

    policies = await get_policies_for_user(user, db)

    # Filter to matching (action, resource_type, resource_id-or-wildcard)
    matching = [
        p for p in policies
        if p.action == action
        and p.resource_type == resource_type
        and (p.resource_id is None or p.resource_id == resource_id)
    ]

    if any(p.effect == "deny" for p in matching):
        return "deny"
    if any(p.effect == "allow" for p in matching):
        return "allow"
    return "deny"  # default-deny
