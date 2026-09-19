"""Read-only operator board API for Phase 18 Revenue OS."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Protocol, Sequence

from empire_os.autonomous_revenue_os import compose_revenue_decision_packet
from empire_os.revenue_os_feedback import (
    RevenueOsOutcomeEvidence,
    review_revenue_os_outcome,
)
from empire_os.revenue_os_freshness import assess_revenue_os_freshness
from empire_os.revenue_os_learning import assess_revenue_os_learning
from empire_os.revenue_os_readiness import assess_revenue_os_readiness
from empire_os.revenue_os_registry import RevenueOsRegistryRecord

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field




class RevenueOsFreshnessRequest(BaseModel):
    now_utc: str
    max_age_seconds: int = Field(default=21600, gt=0)
    astra_observed_at: str | None = None
    predictive_observed_at: str | None = None
    capital_observed_at: str | None = None
    demand_observed_at: str | None = None
    enterprise_observed_at: str | None = None


class RevenueOsFeedbackRequest(BaseModel):
    packet_key: str
    outcome_observed: bool = False
    revenue_recognized: bool = False
    recognized_revenue_cents: int | None = Field(default=None, ge=0)
    observed_cost_cents: int | None = Field(default=None, ge=0)
    observed_at: str
    evidence_refs: list[str] = Field(min_length=1)


class RevenueOsLearningRequest(RevenueOsFeedbackRequest):
    packet_created_at: str
    now_utc: str
    max_age_seconds: int = Field(default=86400, gt=0)


class RevenueOsRegisterRequest(BaseModel):
    packet_key: str
    astra_decision: dict | None = None
    predictive_forecast: dict | None = None
    capital_recommendation: dict | None = None
    demand_plan_ref: str | None = None
    enterprise_blockers: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(min_length=1)
    evidence: dict = Field(default_factory=dict)

class RevenueOsRepository(Protocol):
    def packets(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def packet(self, packet_key: str) -> Mapping[str, Any] | None:
        ...


def create_revenue_os_router(
    repository: RevenueOsRepository | None = None,
    registry=None,
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
            "registry_available": registry is not None,
        }

    @router.post("/freshness/preview")
    def freshness_preview(req: RevenueOsFreshnessRequest):
        try:
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            result = assess_revenue_os_freshness(
                {
                    "astra": req.astra_observed_at,
                    "predictive": req.predictive_observed_at,
                    "capital": req.capital_observed_at,
                    "demand": req.demand_observed_at,
                    "enterprise": req.enterprise_observed_at,
                },
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "side_effects": "none",
            "execution_authority": "none",
            "spend_execution": False,
            "outreach_execution": False,
            "payment_execution": False,
            "allocation_execution": False,
            "deployment_execution": False,
            "freshness": result.as_dict(),
        }

    @router.post("/feedback/preview")
    def feedback_preview(req: RevenueOsFeedbackRequest):
        try:
            evidence = RevenueOsOutcomeEvidence(
                packet_key=req.packet_key,
                outcome_observed=req.outcome_observed,
                revenue_recognized=req.revenue_recognized,
                recognized_revenue_cents=req.recognized_revenue_cents,
                observed_cost_cents=req.observed_cost_cents,
                observed_at=req.observed_at,
                evidence_refs=tuple(req.evidence_refs),
            )
            feedback = review_revenue_os_outcome(evidence)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "side_effects": "none",
            "execution_authority": "none",
            "model_weight_mutation": False,
            "capital_reallocation": False,
            "spend_execution": False,
            "outreach_execution": False,
            "payment_execution": False,
            "allocation_execution": False,
            "deployment_execution": False,
            "feedback": feedback.as_dict(),
        }

    @router.post("/feedback/readiness/preview")
    def feedback_readiness_preview(req: RevenueOsLearningRequest):
        try:
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            evidence = RevenueOsOutcomeEvidence(
                packet_key=req.packet_key,
                outcome_observed=req.outcome_observed,
                revenue_recognized=req.revenue_recognized,
                recognized_revenue_cents=req.recognized_revenue_cents,
                observed_cost_cents=req.observed_cost_cents,
                observed_at=req.observed_at,
                evidence_refs=tuple(req.evidence_refs),
            )
            readiness = assess_revenue_os_learning(
                evidence=evidence,
                packet_created_at=req.packet_created_at,
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "side_effects": "none",
            "execution_authority": "none",
            "model_weight_mutation": False,
            "capital_reallocation": False,
            "spend_execution": False,
            "outreach_execution": False,
            "payment_execution": False,
            "allocation_execution": False,
            "deployment_execution": False,
            "readiness": readiness.as_dict(),
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


    @router.post("/packets/register")
    def register_packet(req: RevenueOsRegisterRequest):
        if registry is None:
            raise HTTPException(503, "revenue_os_registry_not_activated")
        try:
            packet = compose_revenue_decision_packet(
                packet_key=req.packet_key,
                astra_decision=req.astra_decision,
                predictive_forecast=req.predictive_forecast,
                capital_recommendation=req.capital_recommendation,
                demand_plan_ref=req.demand_plan_ref,
                enterprise_blockers=tuple(req.enterprise_blockers),
                evidence_refs=tuple(req.evidence_refs),
            )
            readiness = assess_revenue_os_readiness(packet)
            item = RevenueOsRegistryRecord(
                packet=packet,
                readiness=readiness,
                evidence=dict(req.evidence),
            )
            item.validate()
            row = registry.record(item)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "side_effects": "none",
            "execution_authority": "none",
            "spend_execution": False,
            "outreach_execution": False,
            "payment_execution": False,
            "allocation_execution": False,
            "deployment_execution": False,
            "status": str(row.get("status") or "recorded"),
            "registry_record": item.as_dict(),
            "result": dict(row),
        }

    return router
