from __future__ import annotations

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_active_user, get_db, get_redis
from app.schemas.metrics import ContextLengthSuggestion, GpuSummary, InstanceMetrics, MetricsSummary
from app.services import metrics_service

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/gpus", response_model=GpuSummary)
async def gpu_summary(_user=Depends(get_current_active_user)):
    return await metrics_service.get_gpu_summary()


@router.get("", response_model=MetricsSummary)
async def summary(
    _user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    return await metrics_service.get_summary(db, redis)


@router.get("/{instance_id}", response_model=InstanceMetrics)
async def instance_metrics(
    instance_id: int,
    _user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    return await metrics_service.get_instance_metrics(db, redis, instance_id)


@router.get("/{instance_id}/context-suggestion", response_model=ContextLengthSuggestion)
async def context_suggestion(
    instance_id: int,
    _user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await metrics_service.get_context_suggestion(db, instance_id)


@router.get("/{instance_id}/history", response_model=list)
async def metrics_history(
    instance_id: int,
    _user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await metrics_service.get_history(db, instance_id)
