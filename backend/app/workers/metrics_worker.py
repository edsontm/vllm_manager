"""Metrics worker — polls vLLM /metrics endpoints and caches results in Redis."""
from __future__ import annotations

import asyncio

import docker
import httpx
import pynvml
import redis.asyncio as aioredis
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models.vllm_instance import VllmInstance
from app.services.metrics_service import write_live_metrics

log = structlog.get_logger(__name__)

# Initialise pynvml once at startup
try:
    pynvml.nvmlInit()
    _NVML_OK = True
except Exception:
    _NVML_OK = False

# Prometheus metric names we care about
_INTERESTING = {
    "vllm:num_requests_running",
    "vllm:num_requests_waiting",
    "vllm:gpu_cache_usage_perc",
    "vllm:cpu_cache_usage_perc",
    "vllm:num_preemptions_total",
    "vllm:prompt_tokens_total",
    "vllm:generation_tokens_total",
    "vllm:request_success_total",
    "vllm:time_to_first_token_seconds_sum",
    "vllm:time_to_first_token_seconds_count",
    "vllm:e2e_request_latency_seconds_sum",
    "vllm:e2e_request_latency_seconds_count",
}


def _parse_prometheus(text: str) -> dict:
    """Parse plain Prometheus text format into {metric_name: value}."""
    out: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[0].split("{")[0]
        if name in _INTERESTING:
            try:
                out[name] = float(parts[-1])
            except ValueError:
                pass
    return out


def _gpu_memory_for_ids(gpu_ids: list[int]) -> dict:
    """Return aggregated used/total VRAM (MB) for the given GPU indices."""
    if not gpu_ids:
        return {}

    # Try pynvml first
    if _NVML_OK:
        try:
            total_mb = 0
            used_mb = 0
            for idx in gpu_ids:
                handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_mb += mem.total // (1024 * 1024)
                used_mb += mem.used // (1024 * 1024)
            return {"gpu_memory_total_mb": total_mb, "gpu_memory_used_mb": used_mb}
        except Exception:
            pass

    # Fallback: nvidia-smi subprocess
    try:
        import subprocess
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,memory.total,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        total_mb = 0
        used_mb = 0
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                continue
            idx = int(parts[0])
            if idx in gpu_ids:
                total_mb += int(parts[1])
                used_mb += int(parts[2])
        if total_mb > 0:
            return {"gpu_memory_total_mb": total_mb, "gpu_memory_used_mb": used_mb}
    except Exception:
        pass

    return {}


async def _poll_instance(instance: VllmInstance, redis: aioredis.Redis) -> None:
    url = f"http://{settings.vllm_bind_host}:{instance.internal_port}/metrics"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url)
        if resp.status_code == 200:
            metrics = _parse_prometheus(resp.text)
            # Enrich with live VRAM from nvidia-smi
            gpu_ids = list(instance.gpu_ids or [0])
            metrics.update(_gpu_memory_for_ids(gpu_ids))
            await write_live_metrics(instance.id, metrics, redis)
        else:
            log.warning("metrics poll non-200", instance_id=instance.id, status=resp.status_code)
    except Exception as exc:
        log.debug("metrics poll failed", instance_id=instance.id, error=str(exc))


async def run(redis: aioredis.Redis) -> None:
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    log.info("metrics_worker started", poll_interval=settings.metrics_poll_interval_s)
    while True:
        try:
            async with Session() as db:
                result = await db.execute(
                    select(VllmInstance).where(
                        VllmInstance.status.in_(["running", "starting"])
                    )
                )
                instances = list(result.scalars().all())

            # Reconcile: detect containers that have crashed / exited
            await _reconcile_container_statuses(instances, redis, Session)

            # Poll vLLM metrics only for running instances
            running = [i for i in instances if i.status == "running"]
            await asyncio.gather(
                *[_poll_instance(inst, redis) for inst in running],
                return_exceptions=True,
            )
        except Exception as exc:
            log.error("metrics_worker loop error", error=str(exc))

        await asyncio.sleep(settings.metrics_poll_interval_s)


def _get_docker() -> docker.DockerClient:
    return docker.from_env()


def _error_key(instance_id: int) -> str:
    return f"instance:error:{instance_id}"


_CRASH_LOOP_THRESHOLD = 3  # restarts within a single vLLM session = crash loop


async def _reconcile_container_statuses(
    instances: list[VllmInstance],
    redis: aioredis.Redis,
    Session: async_sessionmaker,
) -> None:
    """Check every starting/running instance against Docker; flip to error if container exited or crash-looping."""
    if not instances:
        return
    try:
        client = await asyncio.get_event_loop().run_in_executor(None, _get_docker)
    except Exception as exc:
        log.warning("reconcile: cannot connect to docker", error=str(exc))
        return

    for instance in instances:
        if not instance.container_id:
            continue
        try:
            container = await asyncio.get_event_loop().run_in_executor(
                None, client.containers.get, instance.container_id
            )
            state = container.attrs.get("State", {})
            docker_status: str = state.get("Status", "unknown")
            restart_count: int = container.attrs.get("RestartCount", 0)

            is_crashed = docker_status in ("exited", "dead", "removing")
            is_crash_loop = (
                docker_status == "running"
                and restart_count >= _CRASH_LOOP_THRESHOLD
            )

            if is_crashed or is_crash_loop:
                # Grab the last lines of logs as the error message
                try:
                    tail_bytes: bytes = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: container.logs(tail=40)
                    )
                    error_msg = tail_bytes.decode("utf-8", errors="replace").strip()
                except Exception:
                    error_msg = f"Container {docker_status} (restarts: {restart_count})"

                # Persist error message in Redis (TTL 1 hour)
                await redis.setex(_error_key(instance.id), 3600, error_msg)

                # Stop the crash-looping container so Docker stops restarting it
                if is_crash_loop:
                    try:
                        await asyncio.get_event_loop().run_in_executor(
                            None, lambda: container.stop(timeout=5)
                        )
                        log.warning(
                            "instance_crash_loop_stopped",
                            instance_id=instance.id,
                            slug=instance.slug,
                            restart_count=restart_count,
                        )
                    except Exception:
                        pass

                # Update DB status
                async with Session() as db:
                    result = await db.execute(
                        select(VllmInstance).where(VllmInstance.id == instance.id)
                    )
                    inst = result.scalar_one_or_none()
                    if inst and inst.status in ("running", "starting"):
                        inst.status = "error"
                        await db.commit()
                        log.warning(
                            "instance_crashed",
                            instance_id=instance.id,
                            slug=instance.slug,
                            docker_status=docker_status,
                            restart_count=restart_count,
                        )
        except docker.errors.NotFound:
            # Container was removed; mark as error too
            async with Session() as db:
                result = await db.execute(
                    select(VllmInstance).where(VllmInstance.id == instance.id)
                )
                inst = result.scalar_one_or_none()
                if inst and inst.status in ("running", "starting"):
                    inst.status = "error"
                    await db.commit()
        except Exception as exc:
            log.debug("reconcile check failed", instance_id=instance.id, error=str(exc))


async def _main() -> None:
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await run(redis)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(_main())
