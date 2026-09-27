"""Read-only Founder Directive visibility for the Founder Console."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query

from empire_os.founder_directives import FounderDirectiveStore

ROOT = Path("/srv/empire_os")


def create_founder_directives_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/founder-directives",
        tags=["founder-directives"],
    )

    @router.get("/status")
    def status() -> dict:
        return FounderDirectiveStore(ROOT).summary()

    @router.get("/latest")
    def latest(limit: int = Query(default=20, ge=1, le=100)) -> dict:
        rows = FounderDirectiveStore(ROOT).list()
        rows = sorted(
            rows,
            key=lambda row: row.updated_at,
            reverse=True,
        )[:limit]
        return {
            "read_only": True,
            "items": [row.as_dict() for row in rows],
        }

    return router
