from __future__ import annotations

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_active_user, get_db, get_redis
from app.schemas.queue import QueueConfig, QueueStatus
from app.services import queue_service, vllm_service

router = APIRouter(prefix="/queue", tags=["Queue"])


@router.get("", response_model=list[QueueStatus])
async def all_depths(
    _user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    instances = await vllm_service.list_instances(db)
    if not instances:
        return []
    instance_ids = [i.id for i in instances]
    depths = await queue_service.get_all_depths(instance_ids, redis)
    slug_map = {i.id: i.slug for i in instances}
    return [
        QueueStatus(instance_id=iid, slug=slug_map[iid], depth=depths.get(iid, 0))
        for iid in instance_ids
    ]


@router.get("/{instance_id}", response_model=QueueStatus)
async def instance_depth(
    instance_id: int,
    _user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    instance = await vllm_service.get_instance(db, instance_id)
    depth = await queue_service.get_depth(instance_id, redis)
    return QueueStatus(instance_id=instance_id, slug=instance.slug, depth=depth)
