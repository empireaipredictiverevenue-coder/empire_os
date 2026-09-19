"""Recommendation-only Demand Genesis readiness API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.demand_genesis import DemandPlan
from empire_os.demand_outcome import (
    DemandOutcomeEvidence,
    review_demand_outcome,
)
from empire_os.demand_registry import DemandRegistryRecord
from empire_os.demand_readiness import (
    DemandEvidenceSnapshot,
    assess_demand_readiness,
)




class DemandPlanRegistryRequest(BaseModel):
    plan_id: str
    channel: str
    objective: str
    audience: str
    evidence_refs: list[str] = Field(min_length=1)
    success_metric: str
    observed_demand_signals: int = Field(ge=0)
    verified_audience_size: int | None = Field(default=None, ge=0)
    qualified_inbound_events: int = Field(ge=0)
    historical_conversion_rate: float | None = Field(default=None, ge=0, le=1)
    observed_cost_cents: int | None = Field(default=None, ge=0)
    evidence: dict = Field(default_factory=dict)

class DemandOutcomeRequest(BaseModel):
    plan_id: str
    success_metric: str
    baseline_value: float | None = None
    observed_value: float | None = None
    observed_cost_cents: int | None = Field(default=None, ge=0)
    observed_at: str
    evidence_refs: list[str] = Field(min_length=1)


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


def create_demand_router(registry=None) -> APIRouter:
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
            "registry_available": registry is not None,
        }

    @router.post("/outcome/preview")
    def outcome_preview(req: DemandOutcomeRequest):
        try:
            review = review_demand_outcome(
                DemandOutcomeEvidence(
                    plan_id=req.plan_id,
                    success_metric=req.success_metric,
                    baseline_value=req.baseline_value,
                    observed_value=req.observed_value,
                    observed_cost_cents=req.observed_cost_cents,
                    observed_at=req.observed_at,
                    evidence_refs=tuple(req.evidence_refs),
                )
            )
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
            "outcome_review": review.as_dict(),
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


    @router.post("/plans/register")
    def register_plan(req: DemandPlanRegistryRequest):
        if registry is None:
            raise HTTPException(
                status_code=503,
                detail="demand_registry_not_activated",
            )
        plan = DemandPlan(
            plan_id=req.plan_id,
            channel=req.channel,
            objective=req.objective,
            audience=req.audience,
            evidence_refs=tuple(req.evidence_refs),
            success_metric=req.success_metric,
        )
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
            readiness = assess_demand_readiness(snapshot)
            item = DemandRegistryRecord(
                plan=plan,
                readiness=readiness,
                evidence=dict(req.evidence),
            )
            item.validate()
            row = registry.record(item)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "publishing_enabled": False,
            "outbound_enabled": False,
            "ad_spend_enabled": False,
            "provider_activation_enabled": False,
            "status": str(row.get("status") or "recorded"),
            "registry_record": item.as_dict(),
            "result": dict(row),
        }

    @router.get("/plans")
    def list_plans(limit: int = 100):
        if registry is None or not hasattr(registry, "list_plans"):
            raise HTTPException(
                status_code=503,
                detail="demand_registry_not_activated",
            )
        rows = list(registry.list_plans(limit=max(1, min(limit, 500))))
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "publishing_enabled": False,
            "outbound_enabled": False,
            "ad_spend_enabled": False,
            "provider_activation_enabled": False,
            "count": len(rows),
            "items": [dict(row) for row in rows],
        }

    return router
