"""Read-only operator board API for Phase 18 Revenue OS."""
from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from fastapi import APIRouter, HTTPException, Query


class RevenueOsRepository(Protocol):
    def packets(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def packet(self, packet_key: str) -> Mapping[str, Any] | None:
        ...


def create_revenue_os_router(
    repository: RevenueOsRepository | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/revenue-os",
        tags=["revenue-os"],
    )

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "side_effects": "none",
            "execution_authority": "none",
            "repository_available": repository is not None,
        }

    @router.get("/board")
    def board(limit: int = Query(default=50, ge=1, le=200)):
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="revenue_os_repository_not_activated",
            )
        rows = [dict(row) for row in repository.packets(limit=limit)]
        return {
            "mode": "OBSERVE",
            "side_effects": "none",
            "execution_authority": "none",
            "count": len(rows),
            "limit": limit,
            "items": rows,
        }

    @router.get("/packets/{packet_key}")
    def packet(packet_key: str):
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="revenue_os_repository_not_activated",
            )
        row = repository.packet(packet_key)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail="revenue_os_packet_not_found",
            )
        return {
            "mode": "OBSERVE",
            "side_effects": "none",
            "execution_authority": "none",
            "packet": dict(row),
        }

    return router
