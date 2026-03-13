from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class GpuInfo(BaseModel):
    index: int
    name: str
    memory_total_mb: int
    memory_used_mb: int
    memory_free_mb: int
    utilization_pct: int | None = None


class GpuSummary(BaseModel):
    gpus: list[GpuInfo]
    system_memory_total_mb: float | None = None
    system_memory_used_mb: float | None = None
    system_memory_free_mb: float | None = None


class InstanceMetrics(BaseModel):
    instance_id: int
    slug: str
    status: str
    gpu_utilization_pct: float | None = None
    gpu_memory_used_mb: float | None = None
    gpu_memory_total_mb: float | None = None
    gpu_memory_by_index_mb: dict[int, float] | None = None
    tokens_per_second: float | None = None
    avg_latency_ms: float | None = None
    queue_depth: int = 0
    requests_total_1h: int = 0
    avg_context_length: float | None = None
    system_memory_used_mb: float | None = None
    system_memory_total_mb: float | None = None


class MetricsSummary(BaseModel):
    instances: list[InstanceMetrics]
    total_requests_1h: int
    total_instance_gpu_memory_used_mb: float = 0
    total_instance_system_memory_used_mb: float = 0


class ContextLengthSuggestion(BaseModel):
    instance_id: int
    avg_context_length: float
    current_max_model_len: int | None
    suggested_max_model_len: int | None
    suggestion: str  # "increase" | "decrease" | "ok"
    suggestion_text: str


class MetricPoint(BaseModel):
    timestamp: datetime
    tokens_per_second: float | None = None
    avg_latency_ms: float | None = None
    queue_depth: int = 0
    gpu_utilization_pct: float | None = None
