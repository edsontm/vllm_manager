from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from functools import partial

import docker
import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request_log import RequestLog
from app.models.vllm_instance import VllmInstance
from app.schemas.metrics import ContextLengthSuggestion, GpuInfo, GpuSummary, InstanceMetrics, MetricsSummary, MetricPoint

_docker_client: docker.DockerClient | None = None


def _get_docker() -> docker.DockerClient:
    global _docker_client
    if _docker_client is None:
        _docker_client = docker.from_env()
    return _docker_client


def _parse_gpu_csv_output(text: str) -> list[GpuInfo]:
    gpus: list[GpuInfo] = []
    for line in text.strip().splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 6:
            continue
        idx, name, total, used, free, util_str = parts[:6]
        try:
            utilization = int(util_str)
        except (TypeError, ValueError):
            utilization = None

        try:
            gpus.append(
                GpuInfo(
                    index=int(idx),
                    name=name,
                    memory_total_mb=int(float(total)),
                    memory_used_mb=int(float(used)),
                    memory_free_mb=int(float(free)),
                    utilization_pct=utilization,
                )
            )
        except ValueError:
            continue
    return gpus


def _read_gpu_summary_via_container_exec() -> list[GpuInfo]:
    try:
        containers = _get_docker().containers.list(filters={"status": "running"})
    except Exception:
        return []

    preferred = sorted(
        containers,
        key=lambda container: 0 if any(name.startswith("/vllm_") for name in getattr(container, "attrs", {}).get("Name", "") and [getattr(container, "attrs", {}).get("Name", "")]) else 1,
    )

    for container in preferred:
        try:
            exec_result = container.exec_run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ]
            )
        except Exception:
            continue

        if exec_result.exit_code != 0:
            continue

        output = exec_result.output.decode("utf-8", errors="replace") if isinstance(exec_result.output, bytes) else str(exec_result.output)
        parsed = _parse_gpu_csv_output(output)
        if parsed:
            return parsed

    return []


def _read_container_gpu_stats(container_id: str | None) -> dict[str, object] | None:
    if not container_id:
        return None

    try:
        container = _get_docker().containers.get(container_id)
    except Exception:
        return None

    try:
        # Get host PIDs belonging to this container.
        top_data = container.top(ps_args="-eo pid")
        rows = top_data.get("Processes", []) if isinstance(top_data, dict) else []
        container_pids: set[int] = set()
        for row in rows:
            if not row:
                continue
            try:
                container_pids.add(int(str(row[0]).strip()))
            except (TypeError, ValueError):
                continue

        if not container_pids:
            return None

        import subprocess

        # Host-level process table: pid,gpu_uuid,used_gpu_memory(MiB)
        proc_cmd = [
            "nvidia-smi",
            "--query-compute-apps=pid,gpu_uuid,used_gpu_memory",
            "--format=csv,noheader,nounits",
        ]
        proc_result = subprocess.run(proc_cmd, capture_output=True, text=True, timeout=5)
        if proc_result.returncode != 0:
            return None

        used_mb = 0.0
        selected_gpu_uuids: set[str] = set()
        used_by_gpu_uuid: dict[str, float] = {}
        for line in proc_result.stdout.strip().splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) < 3:
                continue
            pid_raw, gpu_uuid, mem_raw = parts[:3]
            try:
                pid = int(pid_raw)
            except ValueError:
                continue
            if pid not in container_pids:
                continue
            try:
                mem_value = float(mem_raw)
                used_mb += mem_value
                selected_gpu_uuids.add(gpu_uuid)
                used_by_gpu_uuid[gpu_uuid] = used_by_gpu_uuid.get(gpu_uuid, 0.0) + mem_value
            except ValueError:
                continue

        if not selected_gpu_uuids:
            return None

        # Host-level GPU table: index,gpu_uuid,memory.total(MiB),utilization.gpu(%)
        gpu_cmd = [
            "nvidia-smi",
            "--query-gpu=index,gpu_uuid,memory.total,utilization.gpu",
            "--format=csv,noheader,nounits",
        ]
        gpu_result = subprocess.run(gpu_cmd, capture_output=True, text=True, timeout=5)
        if gpu_result.returncode != 0:
            return None

        total_mb = 0.0
        util_values: list[float] = []
        used_by_gpu_index: dict[int, float] = {}
        for line in gpu_result.stdout.strip().splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) < 4:
                continue
            idx_raw, gpu_uuid, total_raw, util_raw = parts[:4]
            if gpu_uuid not in selected_gpu_uuids:
                continue
            try:
                gpu_index = int(idx_raw)
                used_by_gpu_index[gpu_index] = round(used_by_gpu_uuid.get(gpu_uuid, 0.0), 1)
            except ValueError:
                pass
            try:
                total_mb += float(total_raw)
            except ValueError:
                pass
            try:
                util_values.append(float(util_raw))
            except ValueError:
                pass

        return {
            "gpu_memory_used_mb": round(used_mb, 1),
            "gpu_memory_total_mb": round(total_mb, 1) if total_mb > 0 else None,
            "gpu_utilization_pct": round(sum(util_values) / len(util_values), 1) if util_values else None,
            "gpu_memory_by_index_mb": used_by_gpu_index,
        }
    except Exception:
        return None


def _read_assigned_gpu_stats(gpu_ids: list[int] | None) -> dict[str, float] | None:
    if not gpu_ids:
        return None

    gpus = _read_gpu_summary_via_container_exec()
    if not gpus:
        return None

    selected = [gpu for gpu in gpus if gpu.index in set(gpu_ids)]
    if not selected:
        return None

    return {
        "gpu_memory_used_mb": round(float(sum(gpu.memory_used_mb for gpu in selected)), 1),
        "gpu_memory_total_mb": round(float(sum(gpu.memory_total_mb for gpu in selected)), 1),
        "gpu_utilization_pct": round(
            sum(gpu.utilization_pct or 0 for gpu in selected) / len(selected),
            1,
        ) if selected else None,
    }

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
    memory_stats: dict[str, float] = {}
    gpu_stats: dict[str, object] = {}
    if instance.status == "running":
        memory_stats = await _get_container_memory_stats(instance.container_id)
        gpu_stats = await _get_container_gpu_metrics(instance.container_id)

    gpu_memory_by_index_mb = gpu_stats.get("gpu_memory_by_index_mb")
    if not isinstance(gpu_memory_by_index_mb, dict):
        gpu_memory_by_index_mb = None

    return InstanceMetrics(
        instance_id=instance.id,
        slug=instance.slug,
        status=instance.status,
        gpu_utilization_pct=gpu_stats.get("gpu_utilization_pct", live.get("gpu_utilization_pct")),
        gpu_memory_used_mb=gpu_stats.get("gpu_memory_used_mb", live.get("gpu_memory_used_mb")),
        gpu_memory_total_mb=gpu_stats.get("gpu_memory_total_mb", live.get("gpu_memory_total_mb")),
        gpu_memory_by_index_mb=gpu_memory_by_index_mb,
        tokens_per_second=live.get("tokens_per_second"),
        avg_latency_ms=live.get("avg_latency_ms"),
        queue_depth=depth,
        requests_total_1h=total,
        avg_context_length=float(avg_ctx) if avg_ctx else None,
        system_memory_used_mb=memory_stats.get("system_memory_used_mb"),
        system_memory_total_mb=memory_stats.get("system_memory_total_mb"),
    )


def _read_system_memory_snapshot() -> dict[str, float] | None:
    try:
        values_kb: dict[str, float] = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                key, raw_value = line.split(":", 1)
                parts = raw_value.strip().split()
                if not parts:
                    continue
                values_kb[key] = float(parts[0])

        total_mb = values_kb.get("MemTotal", 0.0) / 1024
        available_mb = values_kb.get("MemAvailable", 0.0) / 1024
        if total_mb <= 0:
            return None
        used_mb = max(total_mb - available_mb, 0.0)
        return {
            "system_memory_total_mb": round(total_mb, 1),
            "system_memory_used_mb": round(used_mb, 1),
            "system_memory_free_mb": round(available_mb, 1),
        }
    except Exception:
        return None


def _read_container_memory_stats(container_id: str | None) -> dict[str, float] | None:
    if not container_id:
        return None

    try:
        container = _get_docker().containers.get(container_id)
        stats = container.stats(stream=False)
    except Exception:
        return None

    memory_stats = stats.get("memory_stats") or {}
    usage_bytes = float(memory_stats.get("usage") or 0)
    stats_details = memory_stats.get("stats") or {}
    cache_bytes = float(
        stats_details.get("cache")
        or stats_details.get("inactive_file")
        or stats_details.get("total_inactive_file")
        or 0
    )
    limit_bytes = float(memory_stats.get("limit") or 0)

    used_mb = max((usage_bytes - cache_bytes) / 1024 / 1024, 0.0)
    total_mb = limit_bytes / 1024 / 1024 if limit_bytes > 0 else None
    return {
        "system_memory_used_mb": round(used_mb, 1),
        "system_memory_total_mb": round(total_mb, 1) if total_mb is not None else None,
    }


async def _get_container_memory_stats(container_id: str | None) -> dict[str, float]:
    if not container_id:
        return {}
    import asyncio

    loop = asyncio.get_event_loop()
    stats = await loop.run_in_executor(None, partial(_read_container_memory_stats, container_id))
    return stats or {}


async def _get_container_gpu_metrics(container_id: str | None) -> dict[str, object]:
    if not container_id:
        return {}
    import asyncio

    loop = asyncio.get_event_loop()
    stats = await loop.run_in_executor(None, partial(_read_container_gpu_stats, container_id))
    return stats or {}


async def _get_assigned_gpu_metrics(gpu_ids: list[int]) -> dict[str, float]:
    if not gpu_ids:
        return {}
    import asyncio

    loop = asyncio.get_event_loop()
    stats = await loop.run_in_executor(None, partial(_read_assigned_gpu_stats, gpu_ids))
    return stats or {}


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
        gpus = _via_nvidiasmi()
        if gpus:
            return gpus
        return _read_gpu_summary_via_container_exec()

    loop = asyncio.get_event_loop()
    gpus = await loop.run_in_executor(None, _collect)
    system_memory = await loop.run_in_executor(None, _read_system_memory_snapshot)
    return GpuSummary(
        gpus=gpus,
        system_memory_total_mb=system_memory.get("system_memory_total_mb") if system_memory else None,
        system_memory_used_mb=system_memory.get("system_memory_used_mb") if system_memory else None,
        system_memory_free_mb=system_memory.get("system_memory_free_mb") if system_memory else None,
    )


async def get_summary(db: AsyncSession, redis: aioredis.Redis) -> MetricsSummary:
    result = await db.execute(select(VllmInstance).order_by(VllmInstance.created_at))
    instances = list(result.scalars().all())

    metrics = [await _build_instance_metrics(inst, db, redis) for inst in instances]
    total = sum(m.requests_total_1h for m in metrics)
    total_instance_gpu_memory_used_mb = sum((m.gpu_memory_used_mb or 0) for m in metrics)
    total_instance_system_memory_used_mb = sum((m.system_memory_used_mb or 0) for m in metrics)
    return MetricsSummary(
        instances=metrics,
        total_requests_1h=total,
        total_instance_gpu_memory_used_mb=round(total_instance_gpu_memory_used_mb, 1),
        total_instance_system_memory_used_mb=round(total_instance_system_memory_used_mb, 1),
    )


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
    """Return 15-minute bucketed metrics for the past 6 hours."""
    from sqlalchemy import text

    six_hours_ago = datetime.now(timezone.utc) - timedelta(hours=6)

    bucket = (
        func.date_trunc("hour", RequestLog.created_at)
        + func.floor(func.extract("minute", RequestLog.created_at) / 15)
        * text("interval '15 minutes'")
    ).label("bucket")

    result = await db.execute(
        select(
            bucket,
            func.avg(RequestLog.latency_ms).label("avg_latency"),
            func.count(RequestLog.id).label("count"),
        )
        .where(
            RequestLog.instance_id == instance_id,
            RequestLog.created_at >= six_hours_ago,
        )
        .group_by("bucket")
        .order_by("bucket")
    )
    rows = result.all()
    return [
        MetricPoint(
            timestamp=row.bucket,
            count=row.count,
            avg_latency_ms=float(row.avg_latency) if row.avg_latency else None,
        )
        for row in rows
    ]
