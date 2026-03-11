from __future__ import annotations

import json
import time
import uuid

import docker
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import VllmError
from app.core.logging import log_inference_request
from app.dependencies import _SessionLocal, get_db, get_redis, get_vllm_token
from app.models.access_token import AccessToken
from app.models.user import User
from app.services import queue_service, vllm_service

router = APIRouter(prefix="/v1", tags=["Proxy"])

# Timeout forwarding a single request to vLLM (seconds).
_VLLM_TIMEOUT = 660.0


def _resolve_container_ip(container_id: str | None) -> str | None:
    if not container_id:
        return None
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
    except Exception:
        return None

    networks = (container.attrs.get("NetworkSettings", {}) or {}).get("Networks", {}) or {}
    for net in networks.values():
        ip = (net or {}).get("IPAddress")
        if ip:
            return ip
    return None


def _candidate_base_urls(instance) -> list[str]:
    urls: list[str] = []
    container_ip = _resolve_container_ip(instance.container_id)
    if container_ip:
        urls.append(f"http://{container_ip}:{instance.internal_port}")
    urls.append(f"http://vllm_{instance.slug}:{instance.internal_port}")
    return list(dict.fromkeys(urls))


@router.api_route(
    "/{slug}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
async def proxy(
    slug: str,
    path: str,
    request: Request,
    token: AccessToken = Depends(get_vllm_token),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    async with _SessionLocal() as lookup_db:
        instance = await vllm_service.get_instance_by_slug(lookup_db, slug)

    # Validate token scope if token is scoped to specific instances.
    if token.scoped_instance_ids and instance.id not in token.scoped_instance_ids:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("Token not scoped to this instance")

    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    body = await request.body()

    try:
        payload = json.loads(body) if body else {}
    except Exception:
        payload = {}

    # Validate model scope if the token restricts which models can be called.
    requested_model: str | None = payload.get("model")
    if token.scoped_model_ids and requested_model:
        if requested_model not in token.scoped_model_ids:
            from app.core.exceptions import ForbiddenError
            raise ForbiddenError(f"Token not allowed for model '{requested_model}'")

    is_stream = bool(payload.get("stream"))

    # All requests — streaming and non-streaming — are routed through the
    # priority queue so that the requesting user's queue_priority_role is
    # enforced before any vLLM work begins.
    depth = await queue_service.get_depth(instance.id, redis)
    start = time.perf_counter()

    result = await db.execute(select(User).where(User.id == token.user_id))
    request_user = result.scalar_one_or_none()
    if request_user is None:
        from app.core.exceptions import UnauthorizedError
        raise UnauthorizedError("Token user not found")

    # Enqueue request and await result.
    job_id, _ = await queue_service.enqueue(instance.id, {
        "job_id": str(uuid.uuid4()),
        "instance_slug": instance.slug,
        "method": request.method,
        "path": path,
        "query": str(request.query_params),
        "headers": dict(request.headers),
        "body": body.decode("utf-8", errors="replace"),
        "queue_priority_role": request_user.queue_priority_role,
        "stream": is_stream,
    }, redis)

    result = await queue_service.subscribe_result(job_id, redis, timeout_s=int(_VLLM_TIMEOUT))
    latency = int((time.perf_counter() - start) * 1000)

    if result is None:
        raise VllmError("Queue result timeout — vLLM did not respond in time")

    ctx = payload.get("max_tokens") or payload.get("max_new_tokens") or 0
    log_inference_request(
        instance_id=instance.id,
        user_id=request_user.id,
        context_length=int(ctx),
        latency_ms=latency,
        status_code=result.get("status_code", 200),
    )

    status_code = result.get("status_code", 200)
    body_content = result.get("body", {})

    # If the original request asked for streaming, wrap the complete response
    # as a single SSE event so clients using an EventSource / SSE parser still
    # receive valid data even though the actual transmission is non-streaming.
    if is_stream and status_code < 400:
        sse_body = json.dumps(body_content)
        sse_payload = f"data: {sse_body}\n\ndata: [DONE]\n\n"
        return StreamingResponse(
            iter([sse_payload.encode()]),
            status_code=200,
            media_type="text/event-stream",
            headers={"X-Request-ID": request_id, "Cache-Control": "no-cache", "X-Queue-Depth": str(depth)},
        )

    return JSONResponse(
        content=body_content,
        status_code=status_code,
        headers={"X-Request-ID": request_id, "X-Queue-Depth": str(depth)},
    )
