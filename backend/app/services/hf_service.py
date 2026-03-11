from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import AsyncIterator

import structlog
from huggingface_hub import HfApi, snapshot_download
from huggingface_hub.utils import HfHubHTTPError

from app.config import settings
from app.core.exceptions import HuggingFaceError
from app.schemas.model import HFModelInfo, LocalModelInfo, ModelPrefill

logger = structlog.get_logger()


def _estimate_vram_gb(siblings) -> float | None:
    """Sum .safetensors shard sizes and add ~20 % overhead for KV cache + activations."""
    total_bytes = sum(
        getattr(s, "size", 0) or 0
        for s in (siblings or [])
        if getattr(s, "rfilename", "").endswith(".safetensors")
    )
    if total_bytes == 0:
        return None
    return round((total_bytes / 1e9) * 1.2, 1)


def _estimate_vram_from_name(model_id: str) -> float | None:
    """
    Estimate VRAM from the parameter count embedded in the model name.
    Matches patterns like 7B, 8b, 1.5B, 70B, 405B in the model id tail.
    Formula: params_in_billions * 2 bytes (BF16) * 1.2 overhead → GB.
    """
    import re
    tail = model_id.split("/")[-1]
    # Match e.g. "7B", "8b", "1.5B", "70B", "0.5b", "405B"
    m = re.search(r"(\d+(?:\.\d+)?)\s*[Bb](?:[^a-zA-Z]|$)", tail)
    if not m:
        return None
    params_b = float(m.group(1))
    # 2 bytes per param (BF16) + 20% overhead for KV cache / activations
    vram_gb = params_b * 2 * 1.2
    return round(vram_gb, 1)


def _model_id_to_slug(model_id: str) -> str:
    tail = model_id.split("/")[-1]
    slug = tail.lower().replace("_", "-").replace(" ", "-")
    import re
    slug = re.sub(r"[^a-z0-9-]", "", slug)[:48]
    return slug.strip("-")


def _slug_to_display(model_id: str) -> str:
    tail = model_id.split("/")[-1]
    return tail.replace("-", " ").replace("_", " ").title()

_hf_api: HfApi | None = None


def _get_api() -> HfApi:
    global _hf_api
    if _hf_api is None:
        _hf_api = HfApi(token=settings.hf_token or None)
    return _hf_api


async def list_models(query: str = "", limit: int = 20, sort: str = "downloads") -> list[HFModelInfo]:
    try:
        models = list(_get_api().list_models(
            search=query or None,
            task="text-generation",
            limit=limit,
            sort=sort if sort in ("downloads", "trending", "likes", "created_at") else "downloads",
        ))
    except HfHubHTTPError as exc:
        raise HuggingFaceError(str(exc)) from exc

    return [
        HFModelInfo(
            model_id=m.id,
            author=m.author,
            pipeline_tag=m.pipeline_tag,
            downloads=m.downloads or 0,
            likes=m.likes or 0,
            tags=list(m.tags or []),
            last_modified=str(m.last_modified) if m.last_modified else None,
            vram_required_gb=(
                _estimate_vram_gb(getattr(m, "siblings", None))
                or _estimate_vram_from_name(m.id)
            ),
        )
        for m in models
    ]


async def model_info(model_id: str) -> HFModelInfo:
    try:
        info = _get_api().model_info(model_id)
    except HfHubHTTPError as exc:
        raise HuggingFaceError(str(exc)) from exc

    return HFModelInfo(
        model_id=info.id,
        author=info.author,
        pipeline_tag=info.pipeline_tag,
        downloads=info.downloads or 0,
        likes=info.likes or 0,
        tags=list(info.tags or []),
        last_modified=str(info.last_modified) if info.last_modified else None,
        vram_required_gb=(
            _estimate_vram_gb(getattr(info, "siblings", None))
            or _estimate_vram_from_name(info.id)
        ),
    )


async def download_model(model_id: str, revision: str | None = None) -> AsyncIterator[dict]:
    """Async generator yielding progress events."""
    yield {"status": "downloading", "model_id": model_id}
    try:
        path = snapshot_download(
            model_id,
            revision=revision,
            cache_dir=settings.hf_cache_dir,
            token=settings.hf_token or None,
        )
        yield {"status": "done", "model_id": model_id, "path": path}
    except HfHubHTTPError as exc:
        raise HuggingFaceError(str(exc)) from exc


async def list_local_models() -> list[LocalModelInfo]:
    results: list[LocalModelInfo] = []
    base = Path(settings.hf_cache_dir)
    if not base.exists():
        return results
    for entry in base.glob("models--*"):
        if not entry.is_dir():
            continue
        model_id = entry.name.replace("models--", "").replace("--", "/")
        size_bytes = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
        size_gb = size_bytes / 1024 ** 3
        # Estimate VRAM from local .safetensors file sizes
        safetensors_bytes = sum(
            f.stat().st_size for f in entry.rglob("*.safetensors") if f.is_file()
        )
        vram_gb = round((safetensors_bytes / 1e9) * 1.2, 1) if safetensors_bytes else None
        results.append(LocalModelInfo(
            model_id=model_id,
            cache_path=str(entry),
            size_gb=round(size_gb, 3),
            vram_required_gb=vram_gb,
        ))
    return results

async def model_prefill(model_id: str) -> ModelPrefill:
    """Lightweight metadata fetch for the Create Instance prefill flow."""
    info = await model_info(model_id)
    return ModelPrefill(
        model_id=model_id,
        suggested_slug=_model_id_to_slug(model_id),
        suggested_display_name=_slug_to_display(model_id),
        vram_required_gb=info.vram_required_gb,
    )