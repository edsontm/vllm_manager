from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_admin_user, get_current_active_user, get_db
from app.schemas.model import DeployModelRequest, HFModelInfo, LocalModelInfo, ModelPrefill, SwitchModelRequest
from app.services import hf_service, vllm_service

router = APIRouter(prefix="/models", tags=["Models"])


@router.get("/available", response_model=list[HFModelInfo])
async def list_available_models(
    query: str = Query("", description="Search query for HuggingFace hub"),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("downloads", description="Sort order: 'downloads' or 'trending'"),
    task: str = Query("all", description="Optional HuggingFace task filter, e.g. text-generation or image-to-text"),
    _user=Depends(get_current_active_user),
):
    return await hf_service.list_models(query=query, limit=limit, sort=sort, task=task)


@router.get("/local", response_model=list[LocalModelInfo])
async def list_local_models(_user=Depends(get_current_active_user)):
    return await hf_service.list_local_models()


@router.get("/{model_id:path}/info", response_model=HFModelInfo)
async def model_info(model_id: str, _user=Depends(get_current_active_user)):
    return await hf_service.model_info(model_id)


@router.get("/prefill/{model_id:path}", response_model=ModelPrefill)
async def model_prefill(model_id: str, _user=Depends(get_current_active_user)):
    """Suggested slug, display name and VRAM estimate for the Create Instance drawer."""
    return await hf_service.model_prefill(model_id)


@router.post("/deploy")
async def deploy_model(
    body: DeployModelRequest,
    _admin=Depends(get_admin_user),
):
    """SSE stream of download progress then instance creation."""

    async def _progress() -> AsyncIterator[str]:
        async for event in hf_service.download_model(body.model_id, body.revision):
            yield f"data: {json.dumps(event)}\n\n"
        yield f"data: {json.dumps({'status': 'done', 'model_id': body.model_id})}\n\n"

    return StreamingResponse(_progress(), media_type="text/event-stream")


@router.post("/switch/{instance_id}")
async def switch_model(
    instance_id: int,
    body: SwitchModelRequest,
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Stop instance, change model_id, restart with new model."""
    await vllm_service.stop_instance(db, instance_id)
    await asyncio.sleep(2)
    await vllm_service.update_instance_model(db, instance_id, body.model_id)
    return await vllm_service.start_instance(db, instance_id)


@router.post("/update/{instance_id}")
async def update_model_weights(
    instance_id: int,
    _admin=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Pull latest revision of the instance's model then restart."""
    instance = await vllm_service.get_instance(db, instance_id)

    async def _progress() -> AsyncIterator[str]:
        async for event in hf_service.download_model(instance.model_id):
            yield f"data: {json.dumps(event)}\n\n"
        await vllm_service.stop_instance(db, instance_id)
        await asyncio.sleep(2)
        await vllm_service.start_instance(db, instance_id)
        yield f"data: {json.dumps({'status': 'done', 'model_id': instance.model_id})}\n\n"

    return StreamingResponse(_progress(), media_type="text/event-stream")
