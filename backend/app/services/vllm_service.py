from __future__ import annotations

import re
import shlex
import socket
from typing import AsyncIterator

import docker
import structlog
from huggingface_hub import HfApi
from huggingface_hub.utils import HfHubHTTPError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ConflictError, NotFoundError, QueueFullError, VllmError
from app.models.vllm_instance import VllmInstance
from app.schemas.instance import InstanceCreate, InstanceStatusRead, InstanceUpdate

logger = structlog.get_logger()

_docker_client: docker.DockerClient | None = None


def _get_docker() -> docker.DockerClient:
    global _docker_client
    if _docker_client is None:
        _docker_client = docker.from_env()
    return _docker_client


def _port_is_free(port: int) -> bool:
    # Binding verifies the port can actually be reserved on the host.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((settings.vllm_bind_host, port))
            return True
        except OSError:
            return False


def _docker_reserved_ports() -> set[int]:
    try:
        client = _get_docker()
        reserved: set[int] = set()
        containers = client.containers.list(all=True)

        for container in containers:
            attrs = getattr(container, "attrs", {}) or {}
            port_map = attrs.get("NetworkSettings", {}).get("Ports", {})
            if not isinstance(port_map, dict):
                continue

            for bindings in port_map.values():
                if not bindings:
                    continue
                for binding in bindings:
                    if not isinstance(binding, dict):
                        continue
                    host_port = binding.get("HostPort")
                    if isinstance(host_port, str) and host_port.isdigit():
                        reserved.add(int(host_port))

        return reserved
    except Exception as exc:
        logger.warning("docker_reserved_ports_probe_failed", error=str(exc))
        return set()


async def allocate_port(db: AsyncSession) -> int:
    result = await db.execute(select(VllmInstance.internal_port))
    used = {row[0] for row in result.all()}
    docker_reserved = _docker_reserved_ports()

    for port in range(settings.vllm_base_port, settings.vllm_base_port + settings.vllm_port_range):
        if port in used or port in docker_reserved:
            continue
        if _port_is_free(port):
            return port

    raise QueueFullError("No free vLLM port available in configured range")


def _normalize_flag_name(flag: str) -> str:
    return flag.strip().lstrip("-").lower()


def _get_extra_arg(extra_args: dict[str, str], flag_name: str) -> str | None:
    wanted = _normalize_flag_name(flag_name)
    for key, value in extra_args.items():
        if _normalize_flag_name(str(key)) == wanted:
            return None if value is None else str(value)
    return None


def _set_extra_arg(extra_args: dict[str, str], flag_name: str, value: str) -> None:
    wanted = _normalize_flag_name(flag_name)
    for key in list(extra_args.keys()):
        if _normalize_flag_name(str(key)) == wanted:
            extra_args[key] = value
            return
    extra_args[f"--{wanted}"] = value


def _looks_like_gguf_model(model_id: str, extra_args: dict[str, str]) -> bool:
    lowered = model_id.lower()
    if lowered.endswith(".gguf"):
        return True
    if "gguf" in lowered.split("/")[-1]:
        return True
    return (_get_extra_arg(extra_args, "load-format") or "").lower() == "gguf"


def _extract_base_model_candidates_from_card_data(card_data: object) -> list[str]:
    if not isinstance(card_data, dict):
        return []

    base = card_data.get("base_model")
    if isinstance(base, str) and base.strip():
        return [base.strip()]
    if isinstance(base, list):
        return [str(item).strip() for item in base if str(item).strip()]
    return []


def _guess_same_author_base_model(model_id: str) -> str | None:
    if "/" not in model_id:
        return None
    author, repo = model_id.split("/", 1)
    base_repo = re.sub(r"(?i)[-_\.]*gguf$", "", repo).strip("-_.")
    if not base_repo or base_repo == repo:
        return None
    return f"{author}/{base_repo}"


def _repo_has_tokenizer_files(api: HfApi, repo_id: str) -> bool:
    try:
        info = api.model_info(repo_id)
    except HfHubHTTPError:
        return False
    except Exception:
        return False

    siblings = getattr(info, "siblings", None) or []
    tokenizer_markers = (
        "tokenizer.json",
        "tokenizer.model",
        "tokenizer_config.json",
        "spiece.model",
        "vocab.json",
        "merges.txt",
    )
    for item in siblings:
        filename = (getattr(item, "rfilename", "") or "").lower()
        if any(filename.endswith(marker) for marker in tokenizer_markers):
            return True
    return False


def _repo_is_gated(api: HfApi, repo_id: str) -> bool:
    try:
        info = api.model_info(repo_id)
    except Exception:
        return False
    gated = getattr(info, "gated", False)
    return bool(gated)


def _infer_tokenizer_repo_for_gguf(model_id: str) -> str | None:
    api = HfApi(token=settings.hf_token or None)
    candidates: list[str] = []

    same_author = _guess_same_author_base_model(model_id)
    if same_author:
        candidates.append(same_author)

    try:
        info = api.model_info(model_id)
        card_data = getattr(info, "cardData", None)
        candidates.extend(_extract_base_model_candidates_from_card_data(card_data))

        tags = getattr(info, "tags", None) or []
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("base_model:"):
                base = tag.split(":", 1)[1].strip()
                if base:
                    candidates.append(base)
    except Exception:
        pass

    seen: set[str] = set()
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if _repo_has_tokenizer_files(api, candidate):
            return candidate

    return None


def _prepare_extra_args_for_model(model_id: str, raw_extra_args: dict[str, str] | None) -> dict[str, str]:
    extra_args: dict[str, str] = dict(raw_extra_args or {})
    if not _looks_like_gguf_model(model_id, extra_args):
        return extra_args

    if not _get_extra_arg(extra_args, "load-format"):
        _set_extra_arg(extra_args, "load-format", "gguf")

    tokenizer = _get_extra_arg(extra_args, "tokenizer")
    if tokenizer:
        if not _get_extra_arg(extra_args, "hf-config-path"):
            _set_extra_arg(extra_args, "hf-config-path", tokenizer)
        return extra_args

    inferred = _infer_tokenizer_repo_for_gguf(model_id)
    if inferred:
        api = HfApi(token=settings.hf_token or None)
        if _repo_is_gated(api, inferred) and not (settings.hf_token or "").strip():
            raise VllmError(
                f"Tokenizer repo '{inferred}' is gated. Configure HF_TOKEN with access "
                "or set extra_args['--tokenizer'] to a non-gated tokenizer repo."
            )
        _set_extra_arg(extra_args, "tokenizer", inferred)
        if not _get_extra_arg(extra_args, "hf-config-path"):
            _set_extra_arg(extra_args, "hf-config-path", inferred)
        logger.info("gguf_tokenizer_inferred", model_id=model_id, tokenizer=inferred)
        return extra_args

    raise VllmError(
        "GGUF model detected but tokenizer could not be inferred automatically. "
        "Set extra_args with '--tokenizer' (for example: {'--load-format': 'gguf', '--tokenizer': 'google/gemma-3-12b-it'})."
    )


def _apply_startup_stability_defaults(raw_extra_args: dict[str, str] | None) -> dict[str, str]:
    """Apply safe startup defaults unless the user explicitly configured them."""
    extra_args: dict[str, str] = dict(raw_extra_args or {})

    # Avoid long first-start compilation stalls on some setups.
    # Users can override with --enforce-eager=false in extra_args.
    if _get_extra_arg(extra_args, "enforce-eager") is None:
        _set_extra_arg(extra_args, "enforce-eager", "true")

    return extra_args


def _extract_repo_id_for_gguf_reference(model_id: str) -> str | None:
    # Already explicit references accepted by vLLM.
    if model_id.endswith(".gguf") or ":" in model_id:
        return None
    if model_id.count("/") != 1:
        return None
    return model_id


def _select_preferred_gguf_filename(files: list[str]) -> str | None:
    if not files:
        return None

    # Prefer practical defaults first to reduce OOM risk on common single-GPU setups.
    preferred_markers = (
        "q4_k_m",
        "q5_k_m",
        "q4_k_s",
        "q5_k_s",
        "q6_k",
        "q8_0",
        "f16",
        "bf16",
    )

    lowered = [(name, name.lower()) for name in files]
    for marker in preferred_markers:
        for original, candidate in lowered:
            if marker in candidate:
                return original

    # Fallback: deterministic order.
    return sorted(files)[0]


def _prepare_model_reference_for_vllm(model_id: str, extra_args: dict[str, str]) -> str:
    if not _looks_like_gguf_model(model_id, extra_args):
        return model_id

    repo_id = _extract_repo_id_for_gguf_reference(model_id)
    if repo_id is None:
        return model_id

    api = HfApi(token=settings.hf_token or None)
    try:
        info = api.model_info(repo_id)
    except Exception as exc:
        raise VllmError(f"Failed to inspect GGUF repo '{repo_id}': {exc}") from exc

    siblings = getattr(info, "siblings", None) or []
    sibling_names = [str(getattr(item, "rfilename", "")) for item in siblings]
    has_config_json = any(name == "config.json" for name in sibling_names)
    gguf_files = [
        name
        for name in sibling_names
        if name.lower().endswith(".gguf")
    ]

    if not gguf_files:
        raise VllmError(
            f"Model '{repo_id}' was detected as GGUF but no .gguf files were found. "
            "Use a GGUF repo/file reference like '<repo>/<file>.gguf'."
        )

    if not has_config_json:
        hf_config_path = _get_extra_arg(extra_args, "hf-config-path") or ""
        raise VllmError(
            "This GGUF repo does not include config.json, which currently breaks vLLM 0.16 "
            "during startup speculator detection. "
            f"Repo: '{repo_id}'. "
            f"Configured --hf-config-path: '{hf_config_path or 'not set'}'. "
            "Use a GGUF repo that includes config.json or switch to a non-GGUF model/repository."
        )

    chosen = _select_preferred_gguf_filename(gguf_files)
    if not chosen:
        raise VllmError(f"Could not select a GGUF file from repo '{repo_id}'.")

    resolved = f"{repo_id}/{chosen}"
    logger.info("gguf_model_reference_resolved", model_id=model_id, resolved_model_id=resolved)
    return resolved


def _build_vllm_args(
    instance: VllmInstance,
    *,
    model_ref: str | None = None,
    extra_args: dict[str, str] | None = None,
) -> list[str]:
    # vLLM >= 0.16 expects model as positional argument for `vllm serve`.
    args = [model_ref or instance.model_id, "--host", "0.0.0.0", "--port", str(instance.internal_port)]
    args += ["--tensor-parallel-size", str(instance.tensor_parallel_size)]
    args += ["--gpu-memory-utilization", str(instance.gpu_memory_utilization)]
    if instance.max_model_len:
        args += ["--max-model-len", str(instance.max_model_len)]
    if instance.quantization:
        args += ["--quantization", instance.quantization]
    args += ["--dtype", instance.dtype]
    effective_extra_args = extra_args if extra_args is not None else (instance.extra_args or {})
    if effective_extra_args:
        for k, v in effective_extra_args.items():
            args.append(k)
            # Boolean flags (value is true/True/null/"") have no positional arg
            if v is not None and str(v).lower() not in ("true", "", "1", "yes"):
                args.append(str(v))
    return args


def _build_docker_run_equivalent(
    *,
    container_name: str,
    instance: VllmInstance,
    vllm_cmd: list[str],
    nvidia_devices: list[str],
    gpu_str: str,
    driver_lib_volumes: dict[str, dict[str, str]],
) -> str:
    cmd: list[str] = [
        "docker",
        "run",
        "--detach",
        "--name",
        container_name,
        "--network",
        settings.docker_network,
        "--restart",
        "unless-stopped",
    ]

    for dev in nvidia_devices:
        cmd.extend(["--device", dev])

    cmd.extend(["--env", f"NVIDIA_VISIBLE_DEVICES={gpu_str}"])
    cmd.extend(["--env", f"CUDA_VISIBLE_DEVICES={gpu_str}"])
    cmd.extend(
        [
            "--publish",
            f"{settings.vllm_bind_host}:{instance.internal_port}:{instance.internal_port}/tcp",
        ]
    )
    cmd.extend(["--volume", f"{settings.hf_cache_dir}:/root/.cache/huggingface:rw"])

    for host_path, bind_conf in driver_lib_volumes.items():
        bind = bind_conf.get("bind", "")
        mode = bind_conf.get("mode", "rw")
        cmd.extend(["--volume", f"{host_path}:{bind}:{mode}"])

    cmd.append(settings.vllm_docker_image)
    cmd.extend(vllm_cmd)

    return " ".join(shlex.quote(part) for part in cmd)


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def list_instances(db: AsyncSession) -> list[VllmInstance]:
    result = await db.execute(select(VllmInstance).order_by(VllmInstance.created_at))
    return list(result.scalars().all())


async def get_instance(db: AsyncSession, instance_id: int) -> VllmInstance:
    result = await db.execute(select(VllmInstance).where(VllmInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        raise NotFoundError(f"Instance {instance_id} not found")
    return instance


async def get_instance_by_slug(db: AsyncSession, slug: str) -> VllmInstance:
    result = await db.execute(select(VllmInstance).where(VllmInstance.slug == slug))
    instance = result.scalar_one_or_none()
    if instance is None:
        raise NotFoundError(f"Instance '{slug}' not found")
    return instance


async def create_instance(db: AsyncSession, body: InstanceCreate) -> VllmInstance:
    existing = await db.execute(select(VllmInstance).where(VllmInstance.slug == body.slug))
    if existing.scalar_one_or_none():
        raise ConflictError(f"Instance slug '{body.slug}' already exists")

    port = await allocate_port(db)
    instance = VllmInstance(
        slug=body.slug,
        display_name=body.display_name,
        model_id=body.model_id,
        internal_port=port,
        gpu_ids=body.gpu_ids,
        max_model_len=body.max_model_len,
        gpu_memory_utilization=body.gpu_memory_utilization if body.gpu_memory_utilization is not None else 0.9,
        tensor_parallel_size=body.tensor_parallel_size or 1,
        dtype=body.dtype or "auto",
        quantization=body.quantization,
        description=body.description,
        extra_args=body.extra_args or {},
        status="stopped",
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    return instance


async def update_instance(db: AsyncSession, instance_id: int, body: InstanceUpdate) -> VllmInstance:
    instance = await get_instance(db, instance_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(instance, field, value)
    await db.commit()
    await db.refresh(instance)
    return instance


async def update_instance_model(db: AsyncSession, instance_id: int, model_id: str) -> VllmInstance:
    instance = await get_instance(db, instance_id)
    instance.model_id = model_id
    await db.commit()
    await db.refresh(instance)
    return instance


async def delete_instance(db: AsyncSession, instance_id: int) -> None:
    instance = await get_instance(db, instance_id)
    if instance.status == "running":
        await _stop_container(instance)
    await db.delete(instance)
    await db.commit()


# ── Container lifecycle (db-level wrappers) ────────────────────────────────────

async def _stop_container(instance: VllmInstance) -> None:
    if not instance.container_id:
        return
    client = _get_docker()
    try:
        container = client.containers.get(instance.container_id)
        container.stop(timeout=30)
        container.remove()
        logger.info("vllm_stopped", instance_id=instance.id)
    except docker.errors.NotFound:
        logger.warning("vllm_container_not_found", container_id=instance.container_id)
    except Exception as exc:
        raise VllmError(f"Failed to stop vLLM container: {exc}") from exc


async def start_instance(db: AsyncSession, instance_id: int) -> VllmInstance:
    instance = await get_instance(db, instance_id)

    if settings.vllm_bind_host != "127.0.0.1":
        raise ValueError("vllm_bind_host MUST be 127.0.0.1")

    docker_reserved = _docker_reserved_ports()
    if instance.internal_port in docker_reserved or not _port_is_free(instance.internal_port):
        old_port = instance.internal_port
        instance.internal_port = await allocate_port(db)
        logger.warning(
            "vllm_port_reassigned_before_start",
            instance_id=instance.id,
            slug=instance.slug,
            old_port=old_port,
            new_port=instance.internal_port,
        )

    instance.status = "starting"
    await db.commit()

    client = _get_docker()

    # Remove any stale container with the same name (from a previous error/stop)
    container_name = f"vllm_{instance.slug}"
    try:
        old = client.containers.get(container_name)
        old.remove(force=True)
        logger.info("vllm_stale_container_removed", name=container_name)
    except docker.errors.NotFound:
        pass  # nothing to clean up

    # Build device list: always include the control/UVM devices, plus per-GPU nvidia<N>
    gpu_indices: list[int] = list(instance.gpu_ids) if instance.gpu_ids else [0]
    gpu_str = ",".join(str(g) for g in gpu_indices)
    _always_devs = [
        "/dev/nvidiactl:/dev/nvidiactl:rwm",
        "/dev/nvidia-uvm:/dev/nvidia-uvm:rwm",
        "/dev/nvidia-uvm-tools:/dev/nvidia-uvm-tools:rwm",
    ]
    _gpu_devs = [f"/dev/nvidia{i}:/dev/nvidia{i}:rwm" for i in gpu_indices]
    nvidia_devices = _always_devs + _gpu_devs

    # Inject only the CUDA driver interface libraries from the HOST into the
    # container so that libcuda.so.1 / libnvidia-ml.so.1 match the kernel
    # module running on the host.
    #
    # IMPORTANT: paths in `volumes` are HOST paths (interpreted by the Docker
    # daemon via the socket).  The backend itself runs inside a container, so
    # we cannot glob the host filesystem — we enumerate the well-known SO-name
    # symlinks directly.  Docker resolves host-side symlinks when bind-mounting,
    # so .so.1 → .so.<driver-version> is followed automatically.
    _HOST_LIB = "/usr/lib/x86_64-linux-gnu"
    _CTR_LIB  = "/usr/local/nvidia/lib64"
    _driver_so_names = [
        "libcuda.so.1",
        "libnvidia-ml.so.1",
        "libnvidia-ptxjitcompiler.so.1",
    ]
    _driver_lib_volumes: dict[str, dict[str, str]] = {
        f"{_HOST_LIB}/{name}": {"bind": f"{_CTR_LIB}/{name}", "mode": "ro"}
        for name in _driver_so_names
    }

    container_env: dict[str, str] = {
        "NVIDIA_VISIBLE_DEVICES": gpu_str,
        "CUDA_VISIBLE_DEVICES": gpu_str,
    }
    hf_token = (settings.hf_token or "").strip()
    if hf_token:
        # Expose token names commonly read by huggingface_hub/transformers in vLLM runtime.
        container_env["HF_TOKEN"] = hf_token
        container_env["HUGGING_FACE_HUB_TOKEN"] = hf_token

    try:
        prepared_extra_args = _prepare_extra_args_for_model(instance.model_id, instance.extra_args)
        prepared_extra_args = _apply_startup_stability_defaults(prepared_extra_args)
        model_ref = _prepare_model_reference_for_vllm(instance.model_id, prepared_extra_args)
        vllm_cmd = _build_vllm_args(instance, model_ref=model_ref, extra_args=prepared_extra_args)
        serve_command = " ".join(shlex.quote(part) for part in ["vllm", "serve", *vllm_cmd])
        docker_run_command = _build_docker_run_equivalent(
            container_name=container_name,
            instance=instance,
            vllm_cmd=vllm_cmd,
            nvidia_devices=nvidia_devices,
            gpu_str=gpu_str,
            driver_lib_volumes=_driver_lib_volumes,
        )

        logger.info(
            "vllm_command",
            instance_id=instance.id,
            slug=instance.slug,
            serve_command=serve_command,
            docker_run_command=docker_run_command,
        )

        container = client.containers.run(
            image=settings.vllm_docker_image,
            command=vllm_cmd,
            detach=True,
            name=f"vllm_{instance.slug}",
            devices=nvidia_devices,
            environment=container_env,
            ports={f"{instance.internal_port}/tcp": ("127.0.0.1", instance.internal_port)},
            volumes={
                settings.hf_cache_dir: {"bind": "/root/.cache/huggingface", "mode": "rw"},
                **_driver_lib_volumes,
            },
            network=settings.docker_network,
            remove=False,
            restart_policy={"Name": "unless-stopped"},
        )
        instance.container_id = container.id
        instance.status = "running"
        await db.commit()
        await db.refresh(instance)
        logger.info("vllm_started", instance_id=instance.id, container_id=container.id)
        return instance
    except Exception as exc:
        instance.status = "error"
        await db.commit()
        raise VllmError(f"Failed to start vLLM container: {exc}") from exc


async def stop_instance(db: AsyncSession, instance_id: int) -> VllmInstance:
    instance = await get_instance(db, instance_id)
    await _stop_container(instance)
    instance.status = "stopped"
    instance.container_id = None
    await db.commit()
    await db.refresh(instance)
    return instance


async def get_container_status(db: AsyncSession, instance_id: int) -> InstanceStatusRead:
    instance = await get_instance(db, instance_id)
    docker_status: str | None = None
    if instance.container_id:
        docker_status = await _get_docker_status(instance.container_id)
        if docker_status == "running" and instance.status != "running":
            instance.status = "running"
            await db.commit()
        elif docker_status in ("exited", "not_found") and instance.status == "running":
            instance.status = "error"
            await db.commit()
    return InstanceStatusRead(
        id=instance.id,
        slug=instance.slug,
        status=instance.status,
        container_id=instance.container_id,
        docker_status=docker_status,
    )


async def _get_docker_status(container_id: str) -> str:
    client = _get_docker()
    try:
        container = client.containers.get(container_id)
        return container.status
    except docker.errors.NotFound:
        return "not_found"


async def health_check(instance: VllmInstance) -> bool:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"http://127.0.0.1:{instance.internal_port}/health")
            return r.status_code == 200
    except Exception:
        return False


async def stream_logs(db: AsyncSession, instance_id: int, tail: int = 100) -> AsyncIterator[str]:
    import asyncio

    # Wait up to 20 s for the container to be created (start is async on DB side)
    container_id: str | None = None
    for _ in range(20):
        db.expire_all()  # bypass session identity-map cache to read fresh DB data
        instance = await get_instance(db, instance_id)
        if instance.container_id:
            container_id = instance.container_id
            break
        yield "data: [waiting for container…]\n\n"
        await asyncio.sleep(1)

    if not container_id:
        yield "data: [no container after timeout]\n\n"
        return

    client = _get_docker()
    try:
        container = client.containers.get(container_id)
    except docker.errors.NotFound:
        yield "data: [container not found]\n\n"
        return

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def _read() -> None:
        try:
            for raw in container.logs(stream=True, tail=tail, follow=True):
                line = raw.decode("utf-8", errors="replace").rstrip()
                loop.call_soon_threadsafe(queue.put_nowait, f"data: {line}\n\n")
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, f"data: [error: {exc}]\n\n")
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    loop.run_in_executor(None, _read)

    while True:
        item = await queue.get()
        if item is None:
            break
        yield item
