# backend/app/services/hf_service.py

## Purpose
Wraps the `huggingface_hub` Python library to provide model discovery, info lookup, and download capabilities. Results are cached in Redis to avoid repeated API calls.

## Exported Class: `HuggingFaceService`

### `async list_models(search: str, limit: int, offset: int) -> list[HFModelInfo]`
- Calls `HfApi.list_models(search=search, task="text-generation", limit=limit)`.
- Result cached in Redis under `hf:models:{hash(search+limit+offset)}` with 10 min TTL.
- Returns list of `HFModelInfo` (id, downloads, likes, tags, pipeline_tag, private, **vram_required_gb**).
- `vram_required_gb` is estimated from the `safetensors` total size reported in sibling file metadata (sum of all `.safetensors` shard sizes); falls back to `None` when not determinable without a full download.

### `async model_info(model_id: str) -> HFModelInfo`
- Calls `HfApi.model_info(model_id)`.
- Cached under `hf:info:{model_id}` with 10 min TTL.
- Includes: parameter count (from config.json), model card excerpt, file list, license, **vram_required_gb**.

### VRAM Estimation Formula
VRAM is estimated inside `_estimate_vram_gb(model_info: ModelInfo) -> float | None`:

```python
def _estimate_vram_gb(info) -> float | None:
    """Sum .safetensors shard sizes → add ~20 % overhead for KV cache + activations."""
    total_bytes = sum(
        s.size for s in info.siblings
        if s.rfilename.endswith('.safetensors')
    )
    if total_bytes == 0:
        return None
    return round((total_bytes / 1e9) * 1.2, 1)   # GB, 20 % overhead
```

- If no `.safetensors` files are present (e.g. PyTorch `.bin` only), returns `None`.
- Overhead factor (1.2) accounts for KV cache and activation memory at typical batch sizes.
- Result is attached to every `HFModelInfo` and `LocalModelInfo` response.

### `async download(model_id: str, cache_dir: str, progress_callback) -> str`
- Calls `snapshot_download(model_id, cache_dir=cache_dir, token=settings.hf_token)`.
- `progress_callback(percent: float, file: str)` is invoked periodically by a background thread; used to push SSE events to the client.
- Returns the local path of the downloaded snapshot.

### `async list_local_models(cache_dir: str) -> list[LocalModelInfo]`
- Scans `cache_dir` for downloaded HF model directories.
- Returns id, local path, disk size, last-modified timestamp, **vram_required_gb** (estimated from the sum of local `.safetensors` file sizes × 1.2 overhead factor).

## Caching Strategy
- All HF API responses cached in Redis with short TTL (10 min) since model metadata changes infrequently.
- Cache is invalidated on explicit `POST /models/update/{instance_id}`.

## Environment Variables Consumed
- `HF_TOKEN` — required for gated/private models
- `HF_CACHE_DIR` — local model storage path (default: `/home/vllm/.cache/huggingface`)

## Contracts
- Download progress events are emitted as `data: {"percent": 42.5, "file": "model.safetensors"}` SSE lines.
- Network errors from the HF API raise `HuggingFaceError` (502) — never propagate raw `requests` exceptions.
