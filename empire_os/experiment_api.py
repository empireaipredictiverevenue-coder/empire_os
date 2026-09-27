"""Read-only experiment analysis preview API."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.experiment_business_impact import (
    ExperimentBusinessImpactEvidence,
    review_experiment_business_impact,
)
from empire_os.experiment_analysis import analyze_observed_experiment
from empire_os.experiment_conclusion import (
    ExperimentConclusionRecord,
    build_causal_conclusion,
)
from empire_os.experiment_conclusion_freshness import (
    assess_conclusion_freshness,
)
from empire_os.experiment_registry import ExperimentRegistryRecord




class ExperimentRegistryRequest(BaseModel):
    experiment_key: str
    hypothesis: str
    metric: str
    control_variant: str
    treatment_variants: list[str] = Field(min_length=1)
    assignment_integrity_verified: bool = False
    exposure_integrity_verified: bool = False
    outcome_window_closed: bool = False
    evidence: dict = Field(default_factory=dict)

class ExperimentAnalysisRequest(BaseModel):
    experiment_key: str
    metric: str
    control_values: list[float]
    treatment_values: list[float]
    evidence_refs: list[str] = Field(min_length=1)
    assignment_integrity_verified: bool = False
    exposure_integrity_verified: bool = False
    outcome_window_closed: bool = False
    minimum_per_arm: int = Field(default=5, ge=1, le=100000)


class ExperimentConclusionRequest(ExperimentAnalysisRequest):
    conclusion_key: str
    evidence: dict = Field(default_factory=dict)


class ExperimentBusinessImpactRequest(ExperimentConclusionRequest):
    experiment_observed_at: str
    outcome_window_closed_at: str
    now_utc: str
    max_age_seconds: int = Field(default=86400, gt=0)
    commercial_outcome_ref: str | None = None
    recognized_revenue_ref: str | None = None
    realized_gp_ref: str | None = None
    realized_gp_cents: int | None = None


class ExperimentConclusionFreshnessRequest(ExperimentConclusionRequest):
    experiment_observed_at: str
    outcome_window_closed_at: str
    now_utc: str
    max_age_seconds: int = Field(default=86400, gt=0)


def create_experiment_router(registry=None) -> APIRouter:
    router = APIRouter(
        prefix="/v1/experiments",
        tags=["experiments"],
    )

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "traffic_mutation": False,
            "rollout_enabled": False,
            "pricing_mutation": False,
            "registry_available": registry is not None,
        }

    @router.post("/analysis/preview")
    def analysis_preview(req: ExperimentAnalysisRequest):
        try:
            result = analyze_observed_experiment(
                experiment_key=req.experiment_key,
                metric=req.metric,
                control_values=req.control_values,
                treatment_values=req.treatment_values,
                evidence_refs=tuple(req.evidence_refs),
                assignment_integrity_verified=(
                    req.assignment_integrity_verified
                ),
                exposure_integrity_verified=(
                    req.exposure_integrity_verified
                ),
                outcome_window_closed=req.outcome_window_closed,
                minimum_per_arm=req.minimum_per_arm,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "traffic_mutation": False,
            "rollout_enabled": False,
            "pricing_mutation": False,
            "analysis": result.as_dict(),
        }

    def build_conclusion(req: ExperimentConclusionRequest):
        analysis = analyze_observed_experiment(
            experiment_key=req.experiment_key,
            metric=req.metric,
            control_values=req.control_values,
            treatment_values=req.treatment_values,
            evidence_refs=tuple(req.evidence_refs),
            assignment_integrity_verified=(
                req.assignment_integrity_verified
            ),
            exposure_integrity_verified=(
                req.exposure_integrity_verified
            ),
            outcome_window_closed=req.outcome_window_closed,
            minimum_per_arm=req.minimum_per_arm,
        )
        return analysis, build_causal_conclusion(
            conclusion_key=req.conclusion_key,
            analysis=analysis,
        )

    @router.post("/conclusions/preview")
    def conclusion_preview(req: ExperimentConclusionRequest):
        try:
            analysis, conclusion = build_conclusion(req)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "traffic_mutation": False,
            "rollout_enabled": False,
            "pricing_mutation": False,
            "analysis": analysis.as_dict(),
            "conclusion": conclusion.as_dict(),
        }

    @router.post("/conclusions/freshness/preview")
    def conclusion_freshness_preview(
        req: ExperimentConclusionFreshnessRequest,
    ):
        try:
            _analysis, conclusion = build_conclusion(req)
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            freshness = assess_conclusion_freshness(
                conclusion=conclusion,
                experiment_observed_at=req.experiment_observed_at,
                outcome_window_closed_at=req.outcome_window_closed_at,
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "traffic_mutation": False,
            "rollout_enabled": False,
            "pricing_mutation": False,
            "freshness": freshness.as_dict(),
        }

    @router.post("/conclusions/business-impact/preview")
    def conclusion_business_impact_preview(
        req: ExperimentBusinessImpactRequest,
    ):
        try:
            _analysis, conclusion = build_conclusion(req)
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            freshness = assess_conclusion_freshness(
                conclusion=conclusion,
                experiment_observed_at=req.experiment_observed_at,
                outcome_window_closed_at=req.outcome_window_closed_at,
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
            impact = review_experiment_business_impact(
                conclusion=conclusion,
                freshness=freshness,
                evidence=ExperimentBusinessImpactEvidence(
                    conclusion_key=req.conclusion_key,
                    commercial_outcome_ref=req.commercial_outcome_ref,
                    recognized_revenue_ref=req.recognized_revenue_ref,
                    realized_gp_ref=req.realized_gp_ref,
                    realized_gp_cents=req.realized_gp_cents,
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "traffic_mutation": False,
            "rollout_enabled": False,
            "pricing_mutation": False,
            "revenue_mutation": False,
            "accounting_mutation": False,
            "impact": impact.as_dict(),
        }

    @router.post("/conclusions/register")
    def register_conclusion(req: ExperimentConclusionRequest):
        if registry is None or not hasattr(registry, "record_conclusion"):
            raise HTTPException(
                status_code=503,
                detail="experiment_conclusion_registry_not_activated",
            )
        try:
            _analysis, conclusion = build_conclusion(req)
            item = ExperimentConclusionRecord(
                conclusion=conclusion,
                evidence=dict(req.evidence),
            )
            item.validate()
            row = registry.record_conclusion(item)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "traffic_mutation": False,
            "rollout_enabled": False,
            "pricing_mutation": False,
            "status": str(row.get("status") or "recorded"),
            "conclusion_record": item.as_dict(),
            "result": dict(row),
        }

    @router.get("/conclusions")
    def list_conclusions(limit: int = 100):
        if registry is None or not hasattr(registry, "list_conclusions"):
            raise HTTPException(
                status_code=503,
                detail="experiment_conclusion_registry_not_activated",
            )
        rows = list(registry.list_conclusions(limit=max(1, min(limit, 500))))
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "traffic_mutation": False,
            "rollout_enabled": False,
            "pricing_mutation": False,
            "count": len(rows),
            "items": [dict(row) for row in rows],
        }

    @router.post("/registry")
    def register_experiment(req: ExperimentRegistryRequest):
        if registry is None or not hasattr(registry, "record"):
            raise HTTPException(
                status_code=503,
                detail="experiment_registry_not_activated",
            )
        item = ExperimentRegistryRecord(
            experiment_key=req.experiment_key,
            hypothesis=req.hypothesis,
            metric=req.metric,
            control_variant=req.control_variant,
            treatment_variants=tuple(req.treatment_variants),
            assignment_integrity_verified=req.assignment_integrity_verified,
            exposure_integrity_verified=req.exposure_integrity_verified,
            outcome_window_closed=req.outcome_window_closed,
            evidence=dict(req.evidence),
        )
        try:
            item.validate()
            row = registry.record(item)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "traffic_mutation": False,
            "rollout_enabled": False,
            "pricing_mutation": False,
            "status": str(row.get("status") or "recorded"),
            "registry_record": item.as_dict(),
            "result": dict(row),
        }

    @router.get("/registry")
    def list_registry(limit: int = 100):
        if registry is None or not hasattr(registry, "list_experiments"):
            raise HTTPException(
                status_code=503,
                detail="experiment_registry_not_activated",
            )
        rows = list(registry.list_experiments(limit=max(1, min(limit, 500))))
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "traffic_mutation": False,
            "rollout_enabled": False,
            "pricing_mutation": False,
            "count": len(rows),
            "items": [dict(row) for row in rows],
        }

    return router
