# backend/app/services/vllm_service.py

## Purpose
Manages the lifecycle of vLLM Docker containers using the Docker Python SDK. This is the only module that interacts with the Docker daemon. All functions are module-level (no class).

## Exported Functions

### `async list_instances(db) -> list[VllmInstance]`
Returns all instances ordered by `created_at`.

### `async get_instance(db, instance_id) -> VllmInstance`
Returns instance by ID; raises `NotFoundError` if missing.

### `async get_instance_by_slug(db, slug) -> VllmInstance`
Returns instance by slug; raises `NotFoundError` if missing.

### `async create_instance(db, body: InstanceCreate) -> VllmInstance`
Validates slug uniqueness, allocates a free port, persists and returns the new instance.

### `async update_instance(db, instance_id, body: InstanceUpdate) -> VllmInstance`
Partial update of any config field.

### `async delete_instance(db, instance_id) -> None`
Stops running container if necessary, then deletes the DB row.

### `async start_instance(db, instance_id) -> VllmInstance`
Sets status to `starting`, removes any stale container with the same name, launches a new Docker container. GPU device files and NVIDIA driver libraries are bind-mounted from the host. Returns the instance with updated status.

### `async stop_instance(db, instance_id) -> VllmInstance`
Stops and removes the container; sets status to `stopped`.

### `async get_container_status(db, instance_id) -> InstanceStatusRead`
Inspects the Docker container and returns the live status.

### `async stream_logs(db, instance_id, tail) -> AsyncIterator[str]`
Streams container log lines as SSE frames.

## Port Allocation (`allocate_port`)
1. Query `vllm_instances` table for ports already in use.
2. Scan `vllm_base_port` → `vllm_base_port + vllm_port_range` for first unused.
3. Confirm the port is truly free at the OS level with a socket probe.
4. Raise `QueueFullError` if no port is available.

## vLLM CLI Args Built from Instance Config

| Instance field | vLLM arg |
|---|---|
| `model_id` | `--model` |
| `internal_port` | `--port` |
| `tensor_parallel_size` | `--tensor-parallel-size` |
| `max_model_len` | `--max-model-len` |
| `quantization` | `--quantization` |
| `dtype` | `--dtype` |
| `extra_args` | merged verbatim (dict keys are flags; boolean/true values have no positional arg) |

## Container Networking
The worker connects to vLLM containers by:
1. Resolving the container's IP within the Docker network (`settings.docker_network`).
2. Falling back to the container name `vllm_{slug}` if IP resolution fails.

## Security Constraints
- Port bindings **always** use `127.0.0.1:<port>:<port>`. The service raises `ValueError` if `settings.vllm_bind_host != "127.0.0.1"`.
- GPU device files (`/dev/nvidia*`, `/dev/nvidiactl`, etc.) are mounted directly; NVML driver `.so` files are bind-mounted from the host to match the running kernel module.

## Environment Variables Consumed
- `VLLM_DOCKER_IMAGE` (default: `vllm/vllm-openai:latest`)
- `VLLM_BASE_PORT`, `VLLM_PORT_RANGE`, `VLLM_BIND_HOST`
- `DOCKER_NETWORK`
- `HF_CACHE_DIR` (mounted as a volume into vLLM containers)
