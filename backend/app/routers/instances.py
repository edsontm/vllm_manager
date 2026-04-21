from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_admin_user, get_current_active_user, get_db, get_redis
from app.schemas.instance import (
    ConnectionExamples,
    InstanceCreate,
    InstanceRead,
    InstanceStatusRead,
    InstanceUpdate,
)
from app.services import vllm_service

router = APIRouter(prefix="/instances", tags=["Instances"])


def _connection_examples(slug: str, model_id: str) -> ConnectionExamples:
    base = f"{settings.base_url.rstrip('/')}/v1/{slug}"
    python_model = repr(model_id)
    js_model = json.dumps(model_id)
    curl_payload = json.dumps(
        {
            "model": model_id,
            "messages": [{"role": "user", "content": "Hi"}],
        }
    )
    # Escape single quotes for safe embedding in a single-quoted shell string.
    curl_payload = curl_payload.replace("'", "'\"'\"'")

    return ConnectionExamples(
        curl=(
            f"curl {base}/chat/completions \\\n"
            "  -H 'Content-Type: application/json' \\\n"
            "  -H 'Authorization: Bearer YOUR_TOKEN' \\\n"
            f"  -d '{curl_payload}'"
        ),
        python=(
            "from openai import OpenAI\n\n"
            f"client = OpenAI(base_url='{base}', api_key='YOUR_TOKEN')\n"
            "resp = client.chat.completions.create(\n"
            f"    model={python_model},\n"
            "    messages=[{'role': 'user', 'content': 'Hi'}],\n"
            ")\n"
            "print(resp.choices[0].message.content)"
        ),
        javascript=(
            "import OpenAI from 'openai';\n\n"
            f"const client = new OpenAI({{ baseURL: '{base}', apiKey: 'YOUR_TOKEN' }});\n"
            "const resp = await client.chat.completions.create({{\n"
            f"  model: {js_model},\n"
            "  messages: [{{ role: 'user', content: 'Hi' }}],\n"
            "}});\n"
            "console.log(resp.choices[0].message.content);"
        ),
        openai_url=f"{base}/",
    )


@router.get("", response_model=list[InstanceRead])
async def list_instances(
    _user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    instances = await vllm_service.list_instances(db)
    result: list[InstanceRead] = []
    for inst in instances:
        data = InstanceRead.model_validate(inst)
        if inst.status == "error" and inst.id:
            raw = await redis.get(f"instance:error:{inst.id}")
            if raw:
                data.error_message = raw
        if inst.id:
            warning = await redis.get(f"instance:warning:{inst.id}")
            if warning:
                data.warning_message = warning
        result.append(data)
    return result


@router.post("", response_model=InstanceRead, status_code=201)
async def create_instance(
    body: InstanceCreate,
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await vllm_service.create_instance(db, body)


@router.get("/{instance_id}", response_model=InstanceRead)
async def get_instance(
    instance_id: int,
    _user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    inst = await vllm_service.get_instance(db, instance_id)
    data = InstanceRead.model_validate(inst)
    if inst.status == "error":
        raw = await redis.get(f"instance:error:{inst.id}")
        if raw:
            data.error_message = raw
    warning = await redis.get(f"instance:warning:{inst.id}")
    if warning:
        data.warning_message = warning
    return data


@router.patch("/{instance_id}", response_model=InstanceRead)
async def update_instance(
    instance_id: int,
    body: InstanceUpdate,
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await vllm_service.update_instance(db, instance_id, body)


@router.delete("/{instance_id}", status_code=204)
async def delete_instance(
    instance_id: int,
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    await vllm_service.delete_instance(db, instance_id)


@router.post("/{instance_id}/start", response_model=InstanceStatusRead)
async def start_instance(
    instance_id: int,
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    await redis.delete(f"instance:error:{instance_id}")
    return await vllm_service.start_instance(db, instance_id)


@router.post("/{instance_id}/stop", response_model=InstanceStatusRead)
async def stop_instance(
    instance_id: int,
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await vllm_service.stop_instance(db, instance_id)


@router.post("/{instance_id}/restart", response_model=InstanceStatusRead)
async def restart_instance(
    instance_id: int,
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    await redis.delete(f"instance:error:{instance_id}")
    await vllm_service.stop_instance(db, instance_id)
    await asyncio.sleep(2)
    return await vllm_service.start_instance(db, instance_id)


@router.get("/{instance_id}/status", response_model=InstanceStatusRead)
async def instance_status(
    instance_id: int,
    _user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await vllm_service.get_container_status(db, instance_id)


@router.get("/{instance_id}/logs")
async def stream_logs(
    instance_id: int,
    tail: int = Query(100, ge=1, le=2000),
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    async def _gen() -> AsyncIterator[str]:
        # stream_logs already yields complete "data: …\n\n" SSE frames
        async for frame in vllm_service.stream_logs(db, instance_id, tail):
            yield frame

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{instance_id}/connection-examples", response_model=ConnectionExamples)
async def connection_examples(
    instance_id: int,
    _user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    instance = await vllm_service.get_instance(db, instance_id)
    return _connection_examples(instance.slug, instance.model_id)
