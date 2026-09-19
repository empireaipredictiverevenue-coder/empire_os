"""Recommendation-only Demand Genesis readiness API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.demand_readiness import (
    DemandEvidenceSnapshot,
    assess_demand_readiness,
)


class DemandEvidenceRequest(BaseModel):
    plan_id: str
    observed_demand_signals: int = Field(ge=0)
    verified_audience_size: int | None = Field(default=None, ge=0)
    qualified_inbound_events: int = Field(ge=0)
    historical_conversion_rate: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    observed_cost_cents: int | None = Field(default=None, ge=0)
    evidence_refs: list[str] = Field(min_length=1)


def create_demand_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/demand",
        tags=["demand-genesis"],
    )

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_authority": "none",
            "publishing_enabled": False,
            "outbound_enabled": False,
            "ad_spend_enabled": False,
            "provider_activation_enabled": False,
        }

    @router.post("/readiness/preview")
    def readiness_preview(req: DemandEvidenceRequest):
        snapshot = DemandEvidenceSnapshot(
            plan_id=req.plan_id,
            observed_demand_signals=req.observed_demand_signals,
            verified_audience_size=req.verified_audience_size,
            qualified_inbound_events=req.qualified_inbound_events,
            historical_conversion_rate=req.historical_conversion_rate,
            observed_cost_cents=req.observed_cost_cents,
            evidence_refs=tuple(req.evidence_refs),
        )
        try:
            result = assess_demand_readiness(snapshot)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_authority": "none",
            "publishing_enabled": False,
            "outbound_enabled": False,
            "ad_spend_enabled": False,
            "provider_activation_enabled": False,
            "readiness": result.as_dict(),
        }

    return router
