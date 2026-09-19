"""Revenue Exchange read intelligence plus governed observation ingest."""
from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from empire_os.revenue_exchange import normalise_exchange_snapshot
from empire_os.revenue_exchange_analysis import assess_exchange_market
from empire_os.revenue_exchange_ingest import build_exchange_observation


class RevenueExchangeRepository(Protocol):
    def observations(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...


class RevenueExchangeIngestRepository(Protocol):
    def append(self, item):
        ...


class ExchangeObservationIngestRequest(BaseModel):
    observation_key: str
    row: dict[str, Any]
    evidence: dict[str, Any] = Field(default_factory=dict)


def create_revenue_exchange_router(
    repository: RevenueExchangeRepository | None = None,
    ingest_repository: RevenueExchangeIngestRepository | None = None,
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
            "ingest_available": ingest_repository is not None,
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

    @router.post("/observations/ingest")
    def ingest(req: ExchangeObservationIngestRequest):
        if ingest_repository is None:
            raise HTTPException(
                status_code=503,
                detail="revenue_exchange_ingest_not_activated",
            )
        try:
            item = build_exchange_observation(
                observation_key=req.observation_key,
                row=req.row,
                evidence=req.evidence,
            )
            result = ingest_repository.append(item)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        status = str(result.get("status") or "").strip()
        if status not in {"recorded", "existing"}:
            raise HTTPException(
                status_code=502,
                detail="revenue_exchange_ingest_invalid_repository_result",
            )
        return {
            "mode": "OBSERVE",
            "status": status,
            "observation_id": result.get("observation_id"),
            "observation_key": item.observation_key,
            "allocation_authority": "none",
            "settlement_authority": "none",
            "pricing_authority": "none",
        }

    return router
