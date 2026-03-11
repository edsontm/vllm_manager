# backend/app/models/vllm_instance.py

## Purpose
SQLAlchemy ORM model for the `vllm_instances` table. Represents a managed vLLM Docker container — its configuration, current state, and runtime parameters.

## Table: `vllm_instances`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `Integer` | PK | |
| `slug` | `String(64)` | UNIQUE, NOT NULL | URL-safe name used in proxy path: `/v1/{slug}/...` |
| `display_name` | `String(128)` | NOT NULL | Human label shown in UI |
| `model_id` | `String(255)` | NOT NULL | HuggingFace model ID, e.g. `mistralai/Mistral-7B-Instruct-v0.2` |
| `container_id` | `String(128)` | nullable | Docker container ID when running |
| `internal_port` | `Integer` | UNIQUE, NOT NULL | Internal port (127.0.0.1 binding only) |
| `status` | `Enum` | NOT NULL, default `'stopped'` | `stopped`, `starting`, `running`, `error`, `pulling` |
| `gpu_ids` | `ARRAY(Integer)` | NOT NULL, default `[]` | CUDA device IDs to expose to the container |
| `max_model_len` | `Integer` | nullable | `--max-model-len` |
| `gpu_memory_utilization` | `Float` | NOT NULL, default `0.9` | `--gpu-memory-utilization` |
| `tensor_parallel_size` | `Integer` | NOT NULL, default `1` | `--tensor-parallel-size` |
| `dtype` | `String(16)` | NOT NULL, default `"auto"` | `--dtype` (e.g. `auto`, `bfloat16`, `float16`) |
| `quantization` | `String(32)` | nullable | `--quantization` (e.g. `awq`, `gptq`) |
| `extra_args` | `JSONB` | NOT NULL, default `{}` | Arbitrary additional CLI args passed to vLLM |
| `description` | `Text` | nullable | Optional notes |
| `created_at` | `DateTime(tz=True)` | server_default `now()` | |
| `updated_at` | `DateTime(tz=True)` | onupdate `now()` | |

## Relationships
- `request_logs`: one-to-many → `RequestLog`

## Contracts
- `internal_port` is always bound to `127.0.0.1` only — see `services.vllm_service` for enforcement.
- `slug` must match `^[a-z0-9-]+$` (validated at schema level).
- A running instance has a non-null `container_id`.
