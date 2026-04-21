"""HF catalog service — pre-warmed Postgres cache of HuggingFace model metadata.

Populated by `app.workers.catalog_worker`. The request path (hf_service.list_models)
queries this cache first and only falls back to the live HF API when results are
missing, which trades freshness (bounded by CATALOG_REFRESH_INTERVAL_S) for
near-instant search latency.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Iterable

import structlog
from huggingface_hub.utils import HfHubHTTPError
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.hf_model import HFModel
from app.schemas.model import HFModelInfo
from app.services import hf_service

log = structlog.get_logger(__name__)


# ───────────────────── internal engine for worker ─────────────────────────────
_engine = None
_Session: async_sessionmaker | None = None


def _get_session_factory() -> async_sessionmaker:
    global _engine, _Session
    if _Session is None:
        _engine = create_async_engine(settings.database_url)
        _Session = async_sessionmaker(_engine, expire_on_commit=False)
    return _Session


# ───────────────────── data mapping ───────────────────────────────────────────
def _row_to_schema(row: HFModel) -> HFModelInfo:
    return HFModelInfo(
        model_id=row.model_id,
        author=row.author,
        pipeline_tag=row.pipeline_tag,
        downloads=row.downloads,
        likes=row.likes,
        tags=list(row.tags or []),
        last_modified=row.last_modified,
        parameter_count_b=row.parameter_count_b,
        vram_required_gb=row.vram_required_gb,
        supports_image=row.supports_image,
        capabilities=list(row.capabilities or []),
    )


def _build_search_text(info_schema: HFModelInfo) -> str:
    parts: list[str] = [info_schema.model_id]
    if info_schema.author:
        parts.append(info_schema.author)
    if info_schema.pipeline_tag:
        parts.append(info_schema.pipeline_tag)
    parts.extend(info_schema.tags or [])
    parts.extend(info_schema.capabilities or [])
    return " ".join(parts).lower()


# ───────────────────── read path (search) ─────────────────────────────────────
async def search_catalog(
    session: AsyncSession,
    query: str = "",
    limit: int = 20,
    sort: str = "downloads",
    task: str = "all",
) -> list[HFModelInfo]:
    stmt = select(HFModel).where(HFModel.is_compatible.is_(True))

    q = (query or "").strip().lower()
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(HFModel.search_text.ilike(pattern))

    task_filter = (task or "all").strip().lower()
    if task_filter and task_filter != "all":
        stmt = stmt.where(HFModel.pipeline_tag == task_filter)

    if sort == "likes":
        stmt = stmt.order_by(desc(HFModel.likes), desc(HFModel.downloads))
    else:
        stmt = stmt.order_by(desc(HFModel.downloads), desc(HFModel.likes))

    stmt = stmt.limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [_row_to_schema(r) for r in rows]


async def catalog_status(session: AsyncSession) -> dict:
    total = (await session.execute(select(func.count(HFModel.model_id)))).scalar_one()
    compatible = (
        await session.execute(
            select(func.count(HFModel.model_id)).where(HFModel.is_compatible.is_(True))
        )
    ).scalar_one()
    last = (
        await session.execute(select(func.max(HFModel.refreshed_at)))
    ).scalar_one()
    return {
        "total_models": int(total or 0),
        "compatible_models": int(compatible or 0),
        "last_refreshed_at": last.isoformat() if last else None,
    }


# ───────────────────── upsert ─────────────────────────────────────────────────
async def upsert_models(session: AsyncSession, models: Iterable[HFModelInfo], is_compatible_map: dict[str, bool]) -> int:
    now = datetime.now(timezone.utc)
    rows: list[dict] = []
    for m in models:
        rows.append({
            "model_id": m.model_id,
            "author": m.author,
            "pipeline_tag": m.pipeline_tag,
            "downloads": m.downloads,
            "likes": m.likes,
            "tags": list(m.tags or []),
            "last_modified": m.last_modified,
            "parameter_count_b": m.parameter_count_b,
            "vram_required_gb": m.vram_required_gb,
            "supports_image": m.supports_image,
            "capabilities": list(m.capabilities or []),
            "is_compatible": is_compatible_map.get(m.model_id, True),
            "search_text": _build_search_text(m),
            "refreshed_at": now,
        })
    if not rows:
        return 0

    stmt = insert(HFModel).values(rows)
    update_cols = {c: getattr(stmt.excluded, c) for c in rows[0].keys() if c != "model_id"}
    stmt = stmt.on_conflict_do_update(index_elements=["model_id"], set_=update_cols)
    await session.execute(stmt)
    await session.commit()
    return len(rows)


# ───────────────────── refresh (worker entry) ─────────────────────────────────
_POPULAR_TASKS = (
    "text-generation",
    "image-text-to-text",
    "image-to-text",
    "visual-question-answering",
    "feature-extraction",
    "text-classification",
)


async def _fetch_candidate_model_ids(api, popular_limit: int, per_task_limit: int) -> list[str]:
    """Run the lightweight list_models on the HF API thread, deduplicated."""
    loop = asyncio.get_running_loop()

    def _list(task: str | None, limit: int, sort: str):
        return list(api.list_models(task=task, limit=limit, sort=sort))

    buckets: list[list] = []
    buckets.append(await loop.run_in_executor(None, _list, None, popular_limit, "downloads"))
    buckets.append(await loop.run_in_executor(None, _list, None, popular_limit, "likes"))
    for task in _POPULAR_TASKS:
        buckets.append(await loop.run_in_executor(None, _list, task, per_task_limit, "downloads"))

    seen: set[str] = set()
    ordered: list[str] = []
    for bucket in buckets:
        for m in bucket:
            if m.id not in seen:
                seen.add(m.id)
                ordered.append(m.id)
    return ordered


async def _fetch_model_info_parallel(model_ids: list[str], concurrency: int):
    """Fetch full model_info for each id via a bounded thread pool."""
    api = hf_service.get_hf_api()
    loop = asyncio.get_running_loop()
    sem = asyncio.Semaphore(concurrency)

    async def _fetch(mid: str):
        async with sem:
            try:
                return await loop.run_in_executor(None, lambda: api.model_info(mid, files_metadata=True))
            except HfHubHTTPError:
                return None
            except Exception:
                return None

    return await asyncio.gather(*[_fetch(m) for m in model_ids])


async def refresh_catalog(
    popular_limit: int | None = None,
    per_task_limit: int | None = None,
    concurrency: int | None = None,
) -> dict:
    """Fetch popular models from HF, classify compatibility, upsert into Postgres."""
    popular_limit = popular_limit or settings.catalog_popular_limit
    per_task_limit = per_task_limit or settings.catalog_per_task_limit
    concurrency = concurrency or settings.catalog_max_concurrency

    api = hf_service.get_hf_api()
    started = datetime.now(timezone.utc)

    model_ids = await _fetch_candidate_model_ids(api, popular_limit, per_task_limit)
    log.info("catalog_refresh_candidates", count=len(model_ids))

    infos = await _fetch_model_info_parallel(model_ids, concurrency)
    tokenizer_cache: dict[str, bool] = {}

    schemas: list[HFModelInfo] = []
    compat_map: dict[str, bool] = {}
    for info in infos:
        if info is None:
            continue
        try:
            compatible = hf_service.is_model_compatible(info, api=api, tokenizer_repo_cache=tokenizer_cache)
            schema = hf_service.hf_info_to_schema(info)
        except Exception as exc:
            log.debug("catalog_refresh_skip", error=str(exc))
            continue
        schemas.append(schema)
        compat_map[schema.model_id] = compatible

    Session = _get_session_factory()
    async with Session() as session:
        upserted = await upsert_models(session, schemas, compat_map)

    took_s = (datetime.now(timezone.utc) - started).total_seconds()
    log.info(
        "catalog_refresh_done",
        upserted=upserted,
        took_s=round(took_s, 1),
        compatible=sum(1 for v in compat_map.values() if v),
    )
    return {
        "upserted": upserted,
        "took_seconds": round(took_s, 1),
        "candidates": len(model_ids),
        "compatible": sum(1 for v in compat_map.values() if v),
    }


async def upsert_from_live_search(models_with_info) -> None:
    """Opportunistic upsert invoked by the request-path live fallback.

    Accepts an iterable of (HFModelInfo schema, is_compatible: bool) tuples.
    Failures are silent — the request should never block on catalog writes.
    """
    schemas: list[HFModelInfo] = []
    compat_map: dict[str, bool] = {}
    for schema, compatible in models_with_info:
        schemas.append(schema)
        compat_map[schema.model_id] = compatible
    if not schemas:
        return
    try:
        Session = _get_session_factory()
        async with Session() as session:
            await upsert_models(session, schemas, compat_map)
    except Exception as exc:
        log.debug("catalog_live_upsert_failed", error=str(exc))
