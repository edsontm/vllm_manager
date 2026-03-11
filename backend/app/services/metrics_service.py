from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request_log import RequestLog
from app.models.vllm_instance import VllmInstance
from app.schemas.metrics import ContextLengthSuggestion, GpuInfo, GpuSummary, InstanceMetrics, MetricsSummary, MetricPoint


def _live_key(instance_id: int) -> str:
    return f"metrics:live:{instance_id}"


async def write_live_metrics(instance_id: int, data: dict, redis: aioredis.Redis) -> None:
    await redis.setex(_live_key(instance_id), 120, json.dumps(data))


async def read_live_metrics(instance_id: int, redis: aioredis.Redis) -> dict:
    raw = await redis.get(_live_key(instance_id))
    return json.loads(raw) if raw else {}


async def _build_instance_metrics(
    instance: VllmInstance,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> InstanceMetrics:
    from app.services.queue_service import get_depth

    live = await read_live_metrics(instance.id, redis)
    depth = await get_depth(instance.id, redis)

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    total_q = select(func.count(RequestLog.id)).where(
        RequestLog.instance_id == instance.id,
        RequestLog.created_at >= one_hour_ago,
    )
    avg_ctx_q = select(func.avg(RequestLog.context_length)).where(
        RequestLog.instance_id == instance.id,
        RequestLog.context_length.isnot(None),
    )
    total = (await db.execute(total_q)).scalar_one() or 0
    avg_ctx = (await db.execute(avg_ctx_q)).scalar_one()

    return InstanceMetrics(
        instance_id=instance.id,
        slug=instance.slug,
        status=instance.status,
        gpu_utilization_pct=live.get("gpu_utilization_pct"),
        gpu_memory_used_mb=live.get("gpu_memory_used_mb"),
        gpu_memory_total_mb=live.get("gpu_memory_total_mb"),
        tokens_per_second=live.get("tokens_per_second"),
        avg_latency_ms=live.get("avg_latency_ms"),
        queue_depth=depth,
        requests_total_1h=total,
        avg_context_length=float(avg_ctx) if avg_ctx else None,
    )


async def get_gpu_summary() -> GpuSummary:
    """Return per-GPU VRAM and utilization — tries pynvml first, falls back to nvidia-smi."""
    import asyncio
    import subprocess

    def _via_pynvml() -> list[GpuInfo] | None:
        try:
            import pynvml
            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            gpus: list[GpuInfo] = []
            for i in range(count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode()
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                try:
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
                except Exception:
                    util = None
                gpus.append(GpuInfo(
                    index=i,
                    name=name,
                    memory_total_mb=int(mem.total / 1024 / 1024),
                    memory_used_mb=int(mem.used / 1024 / 1024),
                    memory_free_mb=int(mem.free / 1024 / 1024),
                    utilization_pct=util,
                ))
            return gpus
        except Exception:
            return None

    def _via_nvidiasmi() -> list[GpuInfo]:
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True, text=True, timeout=5,
            )
            gpus: list[GpuInfo] = []
            for line in result.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 6:
                    continue
                idx, name, total, used, free, util_str = parts
                try:
                    util: int | None = int(util_str)
                except (ValueError, TypeError):
                    util = None
                gpus.append(GpuInfo(
                    index=int(idx),
                    name=name,
                    memory_total_mb=int(total),
                    memory_used_mb=int(used),
                    memory_free_mb=int(free),
                    utilization_pct=util,
                ))
            return gpus
        except Exception:
            return []

    def _collect() -> list[GpuInfo]:
        gpus = _via_pynvml()
        if gpus is not None:
            return gpus
        return _via_nvidiasmi()

    loop = asyncio.get_event_loop()
    gpus = await loop.run_in_executor(None, _collect)
    return GpuSummary(gpus=gpus)


async def get_summary(db: AsyncSession, redis: aioredis.Redis) -> MetricsSummary:
    result = await db.execute(select(VllmInstance).order_by(VllmInstance.created_at))
    instances = list(result.scalars().all())

    metrics = [await _build_instance_metrics(inst, db, redis) for inst in instances]
    total = sum(m.requests_total_1h for m in metrics)
    return MetricsSummary(instances=metrics, total_requests_1h=total)


async def get_instance_metrics(
    db: AsyncSession, redis: aioredis.Redis, instance_id: int
) -> InstanceMetrics:
    result = await db.execute(select(VllmInstance).where(VllmInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Instance {instance_id} not found")
    return await _build_instance_metrics(instance, db, redis)


async def get_context_suggestion(
    db: AsyncSession, instance_id: int
) -> ContextLengthSuggestion:
    result = await db.execute(select(VllmInstance).where(VllmInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Instance {instance_id} not found")

    avg_result = await db.execute(
        select(func.avg(RequestLog.context_length)).where(
            RequestLog.instance_id == instance.id,
            RequestLog.context_length.isnot(None),
        )
    )
    avg = avg_result.scalar_one()
    avg_float = float(avg) if avg else 0.0
    current = instance.max_model_len

    if current is None:
        return ContextLengthSuggestion(
            instance_id=instance_id,
            avg_context_length=avg_float,
            current_max_model_len=None,
            suggested_max_model_len=None,
            suggestion="ok",
            suggestion_text="No max_model_len configured.",
        )

    if avg_float > 0.8 * current:
        suggested = int(current * 1.5)
        return ContextLengthSuggestion(
            instance_id=instance_id,
            avg_context_length=avg_float,
            current_max_model_len=current,
            suggested_max_model_len=suggested,
            suggestion="increase",
            suggestion_text=f"Average context ({avg_float:.0f}) > 80% of max_model_len ({current}). Suggest: {suggested}.",
        )
    elif avg_float > 0 and avg_float < 0.2 * current:
        suggested = max(512, int(avg_float * 2))
        return ContextLengthSuggestion(
            instance_id=instance_id,
            avg_context_length=avg_float,
            current_max_model_len=current,
            suggested_max_model_len=suggested,
            suggestion="decrease",
            suggestion_text=f"Average context ({avg_float:.0f}) < 20% of max_model_len ({current}). Suggest: {suggested}.",
        )
    else:
        return ContextLengthSuggestion(
            instance_id=instance_id,
            avg_context_length=avg_float,
            current_max_model_len=current,
            suggested_max_model_len=current,
            suggestion="ok",
            suggestion_text="Context length is within a healthy range.",
        )


async def get_history(db: AsyncSession, instance_id: int) -> list[MetricPoint]:
    """Return per-hour bucketed metrics for the past 24 hours."""
    one_day_ago = datetime.now(timezone.utc) - timedelta(hours=24)

    result = await db.execute(
        select(
            func.date_trunc("hour", RequestLog.created_at).label("hour"),
            func.avg(RequestLog.latency_ms).label("avg_latency"),
            func.count(RequestLog.id).label("count"),
        )
        .where(
            RequestLog.instance_id == instance_id,
            RequestLog.created_at >= one_day_ago,
        )
        .group_by("hour")
        .order_by("hour")
    )
    rows = result.all()
    return [
        MetricPoint(
            timestamp=row.hour,
            avg_latency_ms=float(row.avg_latency) if row.avg_latency else None,
        )
        for row in rows
    ]
