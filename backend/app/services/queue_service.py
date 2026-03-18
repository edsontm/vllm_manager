from __future__ import annotations

import json
import time
import uuid

import redis.asyncio as aioredis


PRIORITY_ORDER = ("high_priority", "medium_priority", "low_priority")


def _normalize_priority_role(priority_role: str | None) -> str:
    if priority_role in PRIORITY_ORDER:
        return priority_role
    return "medium_priority"


def _queue_key(instance_id: int, priority_role: str) -> str:
    return f"queue:instance:{instance_id}:{priority_role}"


def _queue_keys_by_priority(instance_id: int) -> list[str]:
    return [_queue_key(instance_id, priority) for priority in PRIORITY_ORDER]


def _result_channel(job_id: str) -> str:
    return f"result:{job_id}"


async def enqueue(instance_id: int, payload: dict, redis: aioredis.Redis) -> tuple[str, int]:
    job_id = payload.get("job_id") or str(uuid.uuid4())
    payload["job_id"] = job_id
    payload["enqueue_time"] = time.time()
    priority_role = _normalize_priority_role(payload.get("queue_priority_role"))
    await redis.lpush(_queue_key(instance_id, priority_role), json.dumps(payload))
    depths = await redis.pipeline().llen(_queue_key(instance_id, "high_priority")).llen(
        _queue_key(instance_id, "medium_priority")
    ).llen(_queue_key(instance_id, "low_priority")).execute()
    depth = sum(depths)
    return job_id, depth


async def dequeue_batch(
    instance_id: int, batch_size: int, timeout_ms: int, redis: aioredis.Redis
) -> list[dict]:
    batch: list[dict] = []
    keys = _queue_keys_by_priority(instance_id)
    timeout_s = max(timeout_ms / 1000, 0.05)

    raw = await redis.brpop(keys, timeout=timeout_s)
    if raw:
        batch.append(json.loads(raw[1]))

    for _ in range(batch_size - 1):
        item = None
        for key in keys:
            item = await redis.rpop(key)
            if item is not None:
                break
        if item is None:
            break
        batch.append(json.loads(item))

    return batch


async def get_depth(instance_id: int, redis: aioredis.Redis) -> int:
    pipe = redis.pipeline()
    for key in _queue_keys_by_priority(instance_id):
        pipe.llen(key)
    return sum(await pipe.execute())


async def get_all_depths(instance_ids: list[int], redis: aioredis.Redis) -> dict[int, int]:
    pipe = redis.pipeline()
    for iid in instance_ids:
        for key in _queue_keys_by_priority(iid):
            pipe.llen(key)
    results = await pipe.execute()
    grouped: dict[int, int] = {}
    idx = 0
    for iid in instance_ids:
        grouped[iid] = sum(results[idx : idx + len(PRIORITY_ORDER)])
        idx += len(PRIORITY_ORDER)
    return grouped


async def peek_jobs(instance_id: int, limit: int, redis: aioredis.Redis) -> list[dict]:
    """Peek at the most recent jobs in the queue without removing them."""
    jobs: list[dict] = []
    for key in _queue_keys_by_priority(instance_id):
        raw_items = await redis.lrange(key, 0, -1)
        for raw in raw_items:
            job = json.loads(raw)
            job["_priority"] = key.rsplit(":", 1)[-1]
            jobs.append(job)
    jobs.sort(key=lambda j: j.get("enqueue_time", 0), reverse=True)
    return jobs[:limit]


async def drain_all(instance_id: int, redis: aioredis.Redis) -> list[dict]:
    """Non-blocking drain of all jobs from an instance's priority queues."""
    jobs: list[dict] = []
    for key in _queue_keys_by_priority(instance_id):
        while True:
            raw = await redis.rpop(key)
            if raw is None:
                break
            jobs.append(json.loads(raw))
    return jobs


async def publish_result(job_id: str, result: dict, redis: aioredis.Redis) -> None:
    await redis.publish(_result_channel(job_id), json.dumps(result))


async def subscribe_result(job_id: str, redis: aioredis.Redis, timeout_s: int = 60) -> dict:
    import asyncio

    pubsub = redis.pubsub()
    await pubsub.subscribe(_result_channel(job_id))
    try:
        deadline = asyncio.get_event_loop().time() + timeout_s
        async for message in pubsub.listen():
            if asyncio.get_event_loop().time() > deadline:
                raise asyncio.TimeoutError
            if message["type"] == "message":
                return json.loads(message["data"])
        raise asyncio.TimeoutError
    finally:
        await pubsub.unsubscribe(_result_channel(job_id))
        await pubsub.aclose()
