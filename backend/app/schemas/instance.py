from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class InstanceCreate(BaseModel):
    slug: str
    display_name: str
    model_id: str
    gpu_ids: list[int]
    max_model_len: int | None = None
    gpu_memory_utilization: float = 0.9
    tensor_parallel_size: int = 1
    dtype: str = "auto"
    quantization: str | None = None
    description: str | None = None
    extra_args: dict[str, str] | None = None

    @field_validator("slug")
    @classmethod
    def slug_pattern(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z0-9-]+", v):
            raise ValueError("slug must match ^[a-z0-9-]+$")
        return v


class InstanceUpdate(BaseModel):
    display_name: str | None = None
    model_id: str | None = None
    gpu_ids: list[int] | None = None
    max_model_len: int | None = None
    gpu_memory_utilization: float | None = None
    tensor_parallel_size: int | None = None
    dtype: str | None = None
    quantization: str | None = None
    description: str | None = None
    extra_args: dict[str, str] | None = None


class InstanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    display_name: str
    model_id: str
    container_id: str | None
    internal_port: int
    status: str
    error_message: str | None = None
    gpu_ids: list[int]
    max_model_len: int | None
    gpu_memory_utilization: float
    tensor_parallel_size: int
    dtype: str
    quantization: str | None
    description: str | None
    extra_args: dict[str, str] | None
    created_at: datetime
    updated_at: datetime


class InstanceStatusRead(BaseModel):
    id: int
    slug: str
    status: str
    container_id: str | None
    docker_status: str | None = None


class ConnectionExamples(BaseModel):
    python: str
    curl: str
    javascript: str
    openai_url: str
