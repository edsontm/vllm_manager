"""Queue worker — drains per-instance Redis queues and forwards to vLLM."""
from __future__ import annotations

import asyncio
import base64
import json
import time

import docker
import httpx
import redis.asyncio as aioredis
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models.vllm_instance import VllmInstance
from app.services.queue_service import dequeue_batch, drain_all, publish_result

log = structlog.get_logger(__name__)

_docker_client: docker.DockerClient | None = None


def _get_docker() -> docker.DockerClient:
    global _docker_client
    if _docker_client is None:
        _docker_client = docker.from_env()
    return _docker_client


def _resolve_container_ip(container_id: str | None) -> str | None:
    if not container_id:
        return None
    try:
        container = _get_docker().containers.get(container_id)
    except Exception:
        return None

    networks = (container.attrs.get("NetworkSettings", {}) or {}).get("Networks", {}) or {}
    preferred = networks.get(settings.docker_network, {})
    ip = preferred.get("IPAddress")
    if ip:
        return ip

    for net in networks.values():
        ip = (net or {}).get("IPAddress")
        if ip:
            return ip
    return None


def _candidate_base_urls(instance: VllmInstance) -> list[str]:
    urls: list[str] = []
    container_ip = _resolve_container_ip(instance.container_id)
    if container_ip:
        urls.append(f"http://{container_ip}:{instance.internal_port}")
    urls.append(f"http://vllm_{instance.slug}:{instance.internal_port}")
    return list(dict.fromkeys(urls))


def _decode_job_body(job: dict) -> bytes:
    body_b64 = job.get("body_b64")
    if isinstance(body_b64, str) and body_b64:
        try:
            return base64.b64decode(body_b64)
        except Exception:
            pass

    # Backward compatibility with older queued jobs.
    legacy_body = job.get("body", "")
    if isinstance(legacy_body, bytes):
        return legacy_body
    if isinstance(legacy_body, str):
        return legacy_body.encode("utf-8")
    return b""


def _strip_stream_from_json_body(body: bytes, content_type: str) -> bytes:
    if not body:
        return body

    lowered_content_type = (content_type or "").lower()
    should_try_json = "application/json" in lowered_content_type or body.lstrip().startswith((b"{", b"["))
    if not should_try_json:
        return body

    try:
        parsed = json.loads(body.decode("utf-8"))
    except Exception:
        return body

    if not isinstance(parsed, dict):
        return body

    parsed.pop("stream", None)
    return json.dumps(parsed).encode("utf-8")


async def _process_job(
    job: dict,
    base_urls: list[str],
    client: httpx.AsyncClient,
    redis: aioredis.Redis,
    instance: VllmInstance,
) -> None:
    """Process a single queued job by forwarding it to vLLM."""
    job_id = job.pop("job_id", None)
    enqueue_time = job.pop("enqueue_time", None)
    queue_wait_ms = round((time.time() - enqueue_time) * 1000) if enqueue_time else None
    try:
        method = job.get("method", "POST")
        path = str(job.get("path", "chat/completions")).lstrip("/")
        query = str(job.get("query", ""))
        inbound_headers = job.get("headers", {}) or {}
        body = _decode_job_body(job)
        headers = {
            k: v
            for k, v in inbound_headers.items()
            if k.lower() not in ("host", "content-length", "authorization")
        }

        # Strip "stream" from the forwarded body so vLLM always returns a
        # complete JSON response that can be published to Redis. The proxy
        # re-wraps the result as SSE for clients that originally requested
        # streaming.
        body = _strip_stream_from_json_body(body, headers.get("content-type", ""))

        url_path = f"/v1/{path}"
        if query:
            url_path = f"{url_path}?{query}"

        resp = None
        last_exc: Exception | None = None

        for base_url in base_urls:
            for attempt in range(4):
                try:
                    resp = await client.request(
                        method,
                        f"{base_url}{url_path}",
                        headers=headers,
                        content=body,
                    )
                    break
                except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                    last_exc = exc
                    if attempt < 3:
                        await asyncio.sleep(1)
            if resp is not None:
                break

        if resp is None:
            log.warning(
                "vllm_unreachable",
                instance_id=instance.id,
                slug=instance.slug,
                container_id=instance.container_id,
                base_urls=base_urls,
                error=str(last_exc) if last_exc else "unknown",
            )
            result = {
                "status_code": 503,
                "body": {
                    "error": "vLLM instance is unreachable or still starting; please retry in a few seconds"
                },
                "queue_wait_ms": queue_wait_ms,
            }
        else:
            try:
                body_content = resp.json()
            except Exception:
                body_content = {"raw": resp.text}
            result = {"status_code": resp.status_code, "body": body_content, "queue_wait_ms": queue_wait_ms}
    except Exception as exc:
        result = {"status_code": 500, "body": {"error": str(exc)}, "queue_wait_ms": queue_wait_ms}

    if job_id:
        await publish_result(job_id, result, redis)


async def _process_instance(instance: VllmInstance, redis: aioredis.Redis) -> None:
    base_urls = _candidate_base_urls(instance)
    batch = await dequeue_batch(
        instance.id,
        batch_size=settings.queue_batch_size,
        timeout_ms=settings.queue_batch_timeout_ms,
        redis=redis,
    )
    if not batch:
        return

    async with httpx.AsyncClient(timeout=660) as client:
        tasks = [_process_job(job, base_urls, client, redis, instance) for job in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, BaseException):
            log.error(
                "job_processing_error",
                instance_id=instance.id,
                slug=instance.slug,
                error=str(r),
            )


async def _drain_dead_instance(instance: VllmInstance, redis: aioredis.Redis) -> None:
    """Drain all jobs from a dead instance's queues and publish 503 results."""
    jobs = await drain_all(instance.id, redis)
    if not jobs:
        return
    log.info("draining_dead_instance", slug=instance.slug, count=len(jobs))
    for job in jobs:
        job_id = job.get("job_id")
        if job_id:
            await publish_result(job_id, {
                "status_code": 503,
                "body": {"error": f"Instance '{instance.slug}' is {instance.status}; request cannot be served"},
            }, redis)


async def run(redis: aioredis.Redis) -> None:
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    log.info("queue_worker started")
    while True:
        try:
            async with Session() as db:
                result = await db.execute(
                    select(VllmInstance).where(VllmInstance.status == "running")
                )
                running_instances = result.scalars().all()

                result = await db.execute(
                    select(VllmInstance).where(VllmInstance.status.in_(("error", "stopped")))
                )
                dead_instances = result.scalars().all()

            # Drain dead instance queues first (fast, non-blocking).
            for inst in dead_instances:
                try:
                    await _drain_dead_instance(inst, redis)
                except Exception as exc:
                    log.error("drain_error", slug=inst.slug, error=str(exc))

            if not running_instances:
                await asyncio.sleep(1)
                continue

            results = await asyncio.gather(
                *[_process_instance(inst, redis) for inst in running_instances],
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, BaseException):
                    log.error(
                        "instance_processing_error",
                        error=str(r),
                    )
        except Exception as exc:
            log.error("queue_worker error", error=str(exc))
            await asyncio.sleep(2)


async def _main() -> None:
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await run(redis)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(_main())
