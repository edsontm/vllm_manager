from __future__ import annotations

from pydantic import BaseModel


class QueueStatus(BaseModel):
    instance_id: int
    slug: str
    depth: int


class QueueConfig(BaseModel):
    batch_size: int | None = None
    batch_timeout_ms: int | None = None
