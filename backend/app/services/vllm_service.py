from __future__ import annotations

import socket
from typing import AsyncIterator

import docker
import structlog
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
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) != 0


async def allocate_port(db: AsyncSession) -> int:
    result = await db.execute(select(VllmInstance.internal_port))
    used = {row[0] for row in result.all()}

    for port in range(settings.vllm_base_port, settings.vllm_base_port + settings.vllm_port_range):
        if port not in used and _port_is_free(port):
            return port

    raise QueueFullError("No free vLLM port available in configured range")


def _build_vllm_args(instance: VllmInstance) -> list[str]:
    args = ["--model", instance.model_id, "--host", "0.0.0.0", "--port", str(instance.internal_port)]
    args += ["--tensor-parallel-size", str(instance.tensor_parallel_size)]
    args += ["--gpu-memory-utilization", str(instance.gpu_memory_utilization)]
    if instance.max_model_len:
        args += ["--max-model-len", str(instance.max_model_len)]
    if instance.quantization:
        args += ["--quantization", instance.quantization]
    args += ["--dtype", instance.dtype]
    if instance.extra_args:
        for k, v in instance.extra_args.items():
            args.append(k)
            # Boolean flags (value is true/True/null/"") have no positional arg
            if v is not None and str(v).lower() not in ("true", "", "1", "yes"):
                args.append(str(v))
    return args


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

    vllm_cmd = _build_vllm_args(instance)
    logger.info(
        "vllm_command",
        instance_id=instance.id,
        slug=instance.slug,
        command=" ".join(["vllm", "serve"] + vllm_cmd),
    )

    try:
        container = client.containers.run(
            image=settings.vllm_docker_image,
            command=vllm_cmd,
            detach=True,
            name=f"vllm_{instance.slug}",
            devices=nvidia_devices,
            environment={
                "NVIDIA_VISIBLE_DEVICES": gpu_str,
                "CUDA_VISIBLE_DEVICES": gpu_str,
            },
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
