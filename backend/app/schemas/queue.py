from __future__ import annotations

from pydantic import BaseModel


class QueueStatus(BaseModel):
    instance_id: int
    slug: str
    depth: int


class QueueJob(BaseModel):
    job_id: str
    instance_slug: str
    method: str
    path: str
    priority: str
    enqueue_time: float
    model: str | None = None
    prompt_preview: str | None = None
    max_tokens: int | None = None
    stream: bool = False


class QueueConfig(BaseModel):
    batch_size: int | None = None
    batch_timeout_ms: int | None = None
