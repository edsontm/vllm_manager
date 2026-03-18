from __future__ import annotations

import base64
import json

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_active_user, get_db, get_redis
from app.schemas.queue import QueueConfig, QueueJob, QueueStatus
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


def _extract_prompt_preview(body: dict) -> str | None:
    """Extract a short preview from the request body."""
    messages = body.get("messages")
    if messages and isinstance(messages, list):
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Handle content blocks (e.g. [{"type": "text", "text": "..."}])
                    for block in content:
                        if isinstance(block, dict) and block.get("text"):
                            content = block["text"]
                            break
                    else:
                        return None
                if isinstance(content, str):
                    return content[:100]
    prompt = body.get("prompt")
    if isinstance(prompt, str):
        return prompt[:100]
    return None


@router.get("/{instance_id}/jobs", response_model=list[QueueJob])
async def list_jobs(
    instance_id: int,
    _user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    instance = await vllm_service.get_instance(db, instance_id)
    raw_jobs = await queue_service.peek_jobs(instance_id, limit=10, redis=redis)
    result: list[QueueJob] = []
    for job in raw_jobs:
        body: dict = {}
        body_b64 = job.get("body_b64")
        if body_b64:
            try:
                body = json.loads(base64.b64decode(body_b64))
            except Exception:
                pass
        result.append(QueueJob(
            job_id=job.get("job_id", ""),
            instance_slug=instance.slug,
            method=job.get("method", ""),
            path=job.get("path", ""),
            priority=job.get("_priority", "medium_priority"),
            enqueue_time=job.get("enqueue_time", 0),
            model=body.get("model"),
            prompt_preview=_extract_prompt_preview(body),
            max_tokens=body.get("max_tokens"),
            stream=body.get("stream", False),
        ))
    return result


@router.delete("/{instance_id}", response_model=dict)
async def clear_queue(
    instance_id: int,
    _user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    instance = await vllm_service.get_instance(db, instance_id)
    jobs = await queue_service.drain_all(instance_id, redis)
    for job in jobs:
        job_id = job.get("job_id")
        if job_id:
            await queue_service.publish_result(job_id, {
                "status_code": 503,
                "body": {"error": f"Queue for '{instance.slug}' was manually cleared"},
            }, redis)
    return {"cleared": len(jobs)}


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
