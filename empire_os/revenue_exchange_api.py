"""Read-only Revenue Exchange market intelligence API."""
from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from fastapi import APIRouter, HTTPException, Query

from empire_os.revenue_exchange import normalise_exchange_snapshot
from empire_os.revenue_exchange_analysis import assess_exchange_market


class RevenueExchangeRepository(Protocol):
    def observations(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...


def create_revenue_exchange_router(
    repository: RevenueExchangeRepository | None = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/revenue-exchange",
        tags=["revenue-exchange"],
    )

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "allocation_authority": "none",
            "settlement_authority": "none",
            "pricing_authority": "none",
            "repository_available": repository is not None,
        }

    @router.get("/markets")
    def markets(limit: int = Query(default=100, ge=1, le=500)):
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="revenue_exchange_repository_not_activated",
            )

        items = []
        for row in repository.observations(limit=limit):
            snapshot = normalise_exchange_snapshot(row)
            assessment = assess_exchange_market(snapshot)
            items.append({
                "snapshot": snapshot.as_dict(),
                "assessment": assessment.as_dict(),
            })

        return {
            "mode": "OBSERVE",
            "allocation_authority": "none",
            "settlement_authority": "none",
            "pricing_authority": "none",
            "count": len(items),
            "limit": limit,
            "items": items,
        }

    return router
