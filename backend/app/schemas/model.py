from __future__ import annotations

from pydantic import BaseModel


class HFModelInfo(BaseModel):
    model_id: str
    author: str | None = None
    pipeline_tag: str | None = None
    downloads: int = 0
    likes: int = 0
    tags: list[str] = []
    last_modified: str | None = None
    vram_required_gb: float | None = None
    supports_image: bool = False
    capabilities: list[str] = []


class LocalModelInfo(BaseModel):
    model_id: str
    cache_path: str
    size_gb: float
    vram_required_gb: float | None = None


class ModelPrefill(BaseModel):
    """Populated by GET /models/prefill/{model_id} — fed into the Create Instance drawer."""
    model_id: str
    suggested_slug: str
    suggested_display_name: str
    vram_required_gb: float | None = None


class DeployModelRequest(BaseModel):
    model_id: str
    revision: str | None = None


class SwitchModelRequest(BaseModel):
    model_id: str


class DeployProgress(BaseModel):
    status: str
    model_id: str
    path: str | None = None
