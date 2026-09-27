"""Read-only Founder Objectives API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.founder_objectives import (
    CURRENT_FOUNDER_OBJECTIVES,
    LEGACY_RECOVERED_OBJECTIVES,
    MetricEvidence,
    evaluate_objectives,
)


class MetricEvidenceRequest(BaseModel):
    value: float | int | None = None
    observed_at: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    source: str
    state: str = "observed"


class ObjectivesPreviewRequest(BaseModel):
    cycle: str
    evidence: dict[str, MetricEvidenceRequest] = Field(default_factory=dict)


def _catalog_payload(scope: str) -> dict[str, Any]:
    if scope == "current":
        definitions = CURRENT_FOUNDER_OBJECTIVES
    elif scope == "legacy":
        definitions = LEGACY_RECOVERED_OBJECTIVES
    else:
        raise ValueError("scope must be current or legacy")

    return {
        "schema_version": "empire.founder-objectives.catalog.v1",
        "scope": scope,
        "mode": "OBSERVE",
        "execution_allowed": False,
        "objectives": [
            {
                "key": objective.key,
                "label": objective.label,
                "owner": objective.owner,
                "source": objective.source,
                "key_results": [
                    {
                        "key": kr.key,
                        "label": kr.label,
                        "metric": kr.metric,
                        "target": kr.target,
                        "weight": kr.weight,
                        "target_origin": kr.target_origin,
                        "target_confirmed": kr.target_confirmed,
                        "direction": kr.direction,
                    }
                    for kr in objective.key_results
                ],
            }
            for objective in definitions
        ],
    }


def create_founder_objectives_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/founder-objectives",
        tags=["founder-objectives"],
    )

    @router.get("/catalog")
    def catalog(scope: str = "current"):
        try:
            return _catalog_payload(scope)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/preview")
    def preview(req: ObjectivesPreviewRequest, scope: str = "current"):
        if scope == "current":
            definitions = CURRENT_FOUNDER_OBJECTIVES
        elif scope == "legacy":
            definitions = LEGACY_RECOVERED_OBJECTIVES
        else:
            raise HTTPException(
                status_code=422,
                detail="scope must be current or legacy",
            )

        try:
            evidence = {
                key: MetricEvidence(
                    metric=key,
                    value=item.value,
                    observed_at=item.observed_at,
                    evidence_refs=tuple(item.evidence_refs),
                    source=item.source,
                    state=item.state,
                )
                for key, item in req.evidence.items()
            }
            return evaluate_objectives(
                definitions,
                evidence,
                cycle=req.cycle,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return router
