"""Catalog worker — periodically refreshes the hf_models table from HuggingFace.

Runs an immediate refresh on startup, then sleeps CATALOG_REFRESH_INTERVAL_S
between cycles. Failures are logged and retried on the next tick.
"""
from __future__ import annotations

import asyncio

import structlog

from app.config import settings
from app.services import hf_catalog_service

log = structlog.get_logger(__name__)


async def run() -> None:
    log.info("catalog_worker_started", interval_s=settings.catalog_refresh_interval_s)
    while True:
        try:
            result = await hf_catalog_service.refresh_catalog()
            log.info("catalog_worker_refresh_ok", **result)
        except Exception as exc:
            log.error("catalog_worker_refresh_failed", error=str(exc))
        await asyncio.sleep(settings.catalog_refresh_interval_s)


if __name__ == "__main__":
    asyncio.run(run())
