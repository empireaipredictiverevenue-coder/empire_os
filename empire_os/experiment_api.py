"""Read-only experiment analysis preview API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.experiment_analysis import analyze_observed_experiment


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


def create_experiment_router() -> APIRouter:
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

    return router
