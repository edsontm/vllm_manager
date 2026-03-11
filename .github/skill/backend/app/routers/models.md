# backend/app/routers/models.py

## Purpose
HuggingFace model discovery and lifecycle management: browse, download, deploy to a vLLM instance, switch, and auto-update.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/models/available` | any authenticated | HF model list (text-generation task); supports `?query=`, `?limit=`, `?sort=` |
| `GET` | `/models/local` | any authenticated | Models already downloaded in `HF_CACHE_DIR`; each item includes `vram_required_gb` |
| `GET` | `/models/{model_id:path}/info` | any authenticated | Single HF model detail (size, tags, license, `vram_required_gb`) |
| `GET` | `/models/prefill/{model_id:path}` | any authenticated | Returns `ModelPrefill`: suggested slug, display name, VRAM estimate — used by the Create Instance drawer |
| `POST` | `/models/deploy` | admin | Download model from HF (SSE progress stream); body: `{model_id, revision?}` |
| `POST` | `/models/switch/{instance_id}` | admin | Stop instance, swap `model_id`, restart |
| `POST` | `/models/update/{instance_id}` | admin | Re-download latest revision of the instance's model then restart (SSE progress stream) |

## HuggingFace Integration
- Uses `services.hf_service.list_models()` with HF Hub API.
- `?query=` and `?limit=` forwarded to HF API. `?sort=` accepts `downloads` (default), `trending`, `likes`, `created_at`.
- `HF_TOKEN` env var required for gated models.

## Deploy Flow (`POST /models/deploy`)
1. Returns an SSE stream immediately.
2. Calls `hf_service.download_model(model_id, revision)` — an async generator.
3. Streams `data: {"status": "downloading", "model_id": "..."}` during download.
4. On completion: `data: {"status": "done", "model_id": "...", "path": "..."}`.
5. The frontend is expected to create the instance separately via `POST /instances`.

## Model Switch Flow (`POST /models/switch/{instance_id}`)
1. `stop_instance()` — graceful container stop.
2. 2-second delay.
3. `update_instance_model()` — updates `VllmInstance.model_id`.
4. `start_instance()` — starts container with new model.
5. Returns the `InstanceStatusRead` from start.

## Contracts
- Model files are stored in `HF_CACHE_DIR` (env var, default `/home/vllm/.cache/huggingface`).
- `GET /models/prefill/{model_id:path}` never triggers a download; it reads HF metadata only.
- `vram_required_gb` is estimated from `.safetensors` shard sizes (×1.2 overhead) or from the parameter count in the model name; `null` when not determinable.
