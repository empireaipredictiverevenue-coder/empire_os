"""Read-only Capital Allocator review API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Protocol, Sequence

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from empire_os.capital_allocator import CapitalCandidate
from empire_os.capital_freshness import review_capital_outcome_calibration
from empire_os.capital_outcome import (
    CapitalOutcomeEvidence,
    review_capital_outcome,
)
from empire_os.capital_registry import CapitalReviewRecord
from empire_os.capital_review import CapitalReviewPolicy, review_capital_candidate




class CapitalOutcomeRequest(BaseModel):
    candidate_id: str
    expected_return_cents: int = Field(ge=0)
    required_capital_cents: int = Field(gt=0)
    recognized_revenue_cents: int | None = Field(default=None, ge=0)
    observed_cost_cents: int | None = Field(default=None, ge=0)
    observed_at: str
    evidence_refs: list[str] = Field(min_length=1)


class CapitalOutcomeCalibrationRequest(CapitalOutcomeRequest):
    recommendation_recorded_at: str
    now_utc: str
    max_age_seconds: int = Field(default=604800, gt=0)


class CapitalReviewRegisterRequest(BaseModel):
    review_key: str
    candidate_id: str
    expected_return_cents: int = Field(ge=0)
    required_capital_cents: int = Field(gt=0)
    downside_loss_cents: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    time_to_revenue_days: int = Field(ge=0)
    evidence_refs: list[str] = Field(min_length=1)
    minimum_confidence: float = Field(default=0.5, ge=0, le=1)
    maximum_downside_ratio: float = Field(default=1.0, ge=0)
    minimum_risk_adjusted_score: float = 0.0
    evidence: dict = Field(default_factory=dict)

class CapitalReviewRepository(Protocol):
    def recommendations(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def recommendation(self, candidate_key: str) -> Mapping[str, Any] | None:
        ...


def create_capital_router(
    repository: CapitalReviewRepository | None = None,
    registry=None,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/capital",
        tags=["capital-review"],
    )

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_authority": "none",
            "funds_movement": False,
            "budget_mutation": False,
            "repository_available": repository is not None,
            "registry_available": registry is not None,
        }

    @router.get("/recommendations")
    def recommendations(
        limit: int = Query(default=100, ge=1, le=500),
    ):
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="capital_review_repository_not_activated",
            )
        rows = [dict(row) for row in repository.recommendations(limit=limit)]
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_authority": "none",
            "funds_movement": False,
            "budget_mutation": False,
            "count": len(rows),
            "limit": limit,
            "items": rows,
        }

    @router.get("/recommendations/{candidate_key}")
    def recommendation(candidate_key: str):
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="capital_review_repository_not_activated",
            )
        row = repository.recommendation(candidate_key)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail="capital_recommendation_not_found",
            )
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_authority": "none",
            "funds_movement": False,
            "budget_mutation": False,
            "recommendation": dict(row),
        }


    @router.post("/outcome/preview")
    def outcome_preview(req: CapitalOutcomeRequest):
        try:
            review = review_capital_outcome(
                CapitalOutcomeEvidence(
                    candidate_id=req.candidate_id,
                    expected_return_cents=req.expected_return_cents,
                    required_capital_cents=req.required_capital_cents,
                    recognized_revenue_cents=req.recognized_revenue_cents,
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
            "funds_movement": False,
            "budget_mutation": False,
            "outcome_review": review.as_dict(),
        }

    @router.post("/outcome/calibration/preview")
    def outcome_calibration_preview(req: CapitalOutcomeCalibrationRequest):
        try:
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            evidence = CapitalOutcomeEvidence(
                candidate_id=req.candidate_id,
                expected_return_cents=req.expected_return_cents,
                required_capital_cents=req.required_capital_cents,
                recognized_revenue_cents=req.recognized_revenue_cents,
                observed_cost_cents=req.observed_cost_cents,
                observed_at=req.observed_at,
                evidence_refs=tuple(req.evidence_refs),
            )
            calibration = review_capital_outcome_calibration(
                evidence,
                recommendation_recorded_at=req.recommendation_recorded_at,
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_authority": "none",
            "funds_movement": False,
            "budget_mutation": False,
            "recommendation_mutation": False,
            "calibration": calibration.as_dict(),
        }

    @router.post("/reviews/register")
    def register_review(req: CapitalReviewRegisterRequest):
        if registry is None:
            raise HTTPException(
                status_code=503,
                detail="capital_registry_not_activated",
            )
        candidate = CapitalCandidate(
            candidate_id=req.candidate_id,
            expected_return_cents=req.expected_return_cents,
            required_capital_cents=req.required_capital_cents,
            downside_loss_cents=req.downside_loss_cents,
            confidence=req.confidence,
            time_to_revenue_days=req.time_to_revenue_days,
            evidence_refs=tuple(req.evidence_refs),
        )
        policy = CapitalReviewPolicy(
            minimum_confidence=req.minimum_confidence,
            maximum_downside_ratio=req.maximum_downside_ratio,
            minimum_risk_adjusted_score=req.minimum_risk_adjusted_score,
        )
        try:
            review = review_capital_candidate(candidate, policy=policy)
            item = CapitalReviewRecord(
                review_key=req.review_key,
                candidate=candidate,
                policy=policy,
                review=review,
                evidence=dict(req.evidence),
            )
            item.validate()
            row = registry.record(item)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "recommendation_only": True,
            "execution_authority": "none",
            "funds_movement": False,
            "budget_mutation": False,
            "status": str(row.get("status") or "recorded"),
            "review_record": item.as_dict(),
            "result": dict(row),
        }

    @router.get("/reviews")
    def list_reviews(limit: int = Query(default=100, ge=1, le=500)):
        if registry is None or not hasattr(registry, "list_reviews"):
            raise HTTPException(
                status_code=503,
                detail="capital_registry_not_activated",
            )
        rows = list(registry.list_reviews(limit=limit))
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "recommendation_only": True,
            "execution_authority": "none",
            "funds_movement": False,
            "budget_mutation": False,
            "count": len(rows),
            "limit": limit,
            "items": [dict(row) for row in rows],
        }

    return router
