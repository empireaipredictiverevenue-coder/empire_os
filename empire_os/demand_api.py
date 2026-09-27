"""Recommendation-only Demand Genesis readiness API."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.demand_commercial_impact import (
    DemandCommercialImpactEvidence,
    review_demand_commercial_impact,
)
from empire_os.demand_comparison import compare_demand_plan_outcomes
from empire_os.demand_freshness import review_demand_outcome_evidence
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


class DemandOutcomeEvidenceReviewRequest(DemandOutcomeRequest):
    plan_registered_at: str
    now_utc: str
    max_age_seconds: int = Field(default=604800, gt=0)


class DemandCommercialImpactRequest(DemandOutcomeEvidenceReviewRequest):
    commercial_attribution_ref: str | None = None
    recognized_revenue_ref: str | None = None
    recognized_revenue_cents: int | None = Field(default=None, ge=0)
    realized_gp_ref: str | None = None
    realized_gp_cents: int | None = Field(default=None, ge=0)


class DemandComparisonRequest(BaseModel):
    left: DemandOutcomeEvidenceReviewRequest
    right: DemandOutcomeEvidenceReviewRequest


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

    @router.post("/outcome/evidence/preview")
    def outcome_evidence_preview(req: DemandOutcomeEvidenceReviewRequest):
        try:
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            evidence = DemandOutcomeEvidence(
                plan_id=req.plan_id,
                success_metric=req.success_metric,
                baseline_value=req.baseline_value,
                observed_value=req.observed_value,
                observed_cost_cents=req.observed_cost_cents,
                observed_at=req.observed_at,
                evidence_refs=tuple(req.evidence_refs),
            )
            review = review_demand_outcome_evidence(
                evidence,
                plan_registered_at=req.plan_registered_at,
                now=now,
                max_age_seconds=req.max_age_seconds,
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
            "review": review.as_dict(),
        }

    @router.post("/outcome/commercial-impact/preview")
    def outcome_commercial_impact_preview(req: DemandCommercialImpactRequest):
        try:
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            outcome = review_demand_outcome_evidence(
                DemandOutcomeEvidence(
                    plan_id=req.plan_id,
                    success_metric=req.success_metric,
                    baseline_value=req.baseline_value,
                    observed_value=req.observed_value,
                    observed_cost_cents=req.observed_cost_cents,
                    observed_at=req.observed_at,
                    evidence_refs=tuple(req.evidence_refs),
                ),
                plan_registered_at=req.plan_registered_at,
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
            impact = review_demand_commercial_impact(
                outcome=outcome,
                evidence=DemandCommercialImpactEvidence(
                    plan_id=req.plan_id,
                    commercial_attribution_ref=req.commercial_attribution_ref,
                    recognized_revenue_ref=req.recognized_revenue_ref,
                    recognized_revenue_cents=req.recognized_revenue_cents,
                    realized_gp_ref=req.realized_gp_ref,
                    realized_gp_cents=req.realized_gp_cents,
                ),
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
            "revenue_mutation": False,
            "accounting_mutation": False,
            "impact": impact.as_dict(),
        }

    @router.post("/outcome/comparison/preview")
    def outcome_comparison_preview(req: DemandComparisonRequest):
        def build(item: DemandOutcomeEvidenceReviewRequest):
            normalized = (
                item.now_utc[:-1] + "+00:00"
                if item.now_utc.endswith("Z")
                else item.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            evidence = DemandOutcomeEvidence(
                plan_id=item.plan_id,
                success_metric=item.success_metric,
                baseline_value=item.baseline_value,
                observed_value=item.observed_value,
                observed_cost_cents=item.observed_cost_cents,
                observed_at=item.observed_at,
                evidence_refs=tuple(item.evidence_refs),
            )
            return review_demand_outcome_evidence(
                evidence,
                plan_registered_at=item.plan_registered_at,
                now=now,
                max_age_seconds=item.max_age_seconds,
            )
        try:
            comparison = compare_demand_plan_outcomes(
                build(req.left),
                build(req.right),
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
            "automatic_plan_selection": False,
            "comparison": comparison.as_dict(),
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
