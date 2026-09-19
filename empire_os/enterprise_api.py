"""Read-only enterprise control and SLO status API."""
from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from empire_os.enterprise_controls import ControlEvidence, SloObservation
from empire_os.enterprise_review import review_enterprise_readiness
from empire_os.enterprise_registry import EnterpriseReadinessRecord




class EnterpriseControlRequest(BaseModel):
    control_key: str
    family: str
    tenant_key: str | None = None
    status: str
    evidence_refs: list[str] = Field(min_length=1)
    observed_at: str
    source: str


class EnterpriseSloRequest(BaseModel):
    service_key: str
    metric: str
    target: float
    observed: float | None = None
    window: str
    observed_at: str
    source: str


class EnterpriseReadinessRegisterRequest(BaseModel):
    readiness_key: str
    controls: list[EnterpriseControlRequest] = Field(min_length=1)
    slos: list[EnterpriseSloRequest] = Field(min_length=1)
    evidence: dict = Field(default_factory=dict)

class EnterpriseEvidenceRepository(Protocol):
    def controls(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def slos(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...


def create_enterprise_router(
    repository: EnterpriseEvidenceRepository | None = None,
    registry=None,
) -> APIRouter:
    router = APIRouter(
        prefix="/v1/enterprise",
        tags=["enterprise-controls"],
    )

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "repository_available": repository is not None,
            "registry_available": registry is not None,
        }

    @router.get("/readiness")
    def readiness(limit: int = Query(default=200, ge=1, le=500)):
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="enterprise_evidence_repository_not_activated",
            )

        controls = tuple(
            ControlEvidence(
                control_key=str(row.get("control_key") or ""),
                family=str(row.get("family") or ""),
                tenant_key=(
                    str(row["tenant_key"])
                    if row.get("tenant_key") is not None
                    else None
                ),
                status=str(row.get("status") or ""),
                evidence_refs=tuple(row.get("evidence_refs") or ()),
                observed_at=str(row.get("observed_at") or ""),
                source=str(row.get("source") or ""),
            )
            for row in repository.controls(limit=limit)
        )

        slos = tuple(
            SloObservation(
                service_key=str(row.get("service_key") or ""),
                metric=str(row.get("metric") or ""),
                target=float(row.get("target")),
                observed=(
                    float(row["observed"])
                    if row.get("observed") is not None
                    else None
                ),
                window=str(row.get("window") or ""),
                observed_at=str(row.get("observed_at") or ""),
                source=str(row.get("source") or ""),
            )
            for row in repository.slos(limit=limit)
        )

        result = review_enterprise_readiness(
            controls=controls,
            slos=slos,
        )
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "readiness": result.as_dict(),
        }


    @router.post("/readiness/register")
    def register_readiness(req: EnterpriseReadinessRegisterRequest):
        if registry is None:
            raise HTTPException(503, "enterprise_registry_not_activated")
        controls = tuple(ControlEvidence(**row.model_dump()) for row in req.controls)
        slos = tuple(SloObservation(**row.model_dump()) for row in req.slos)
        try:
            review = review_enterprise_readiness(controls=controls, slos=slos)
            item = EnterpriseReadinessRecord(
                readiness_key=req.readiness_key,
                controls=controls,
                slos=slos,
                review=review,
                evidence=dict(req.evidence),
            )
            item.validate()
            row = registry.record(item)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "control_mutation": False,
            "infrastructure_mutation": False,
            "identity_mutation": False,
            "backup_mutation": False,
            "slo_target_mutation": False,
            "compliance_mutation": False,
            "status": str(row.get("status") or "recorded"),
            "readiness_record": item.as_dict(),
            "result": dict(row),
        }

    @router.get("/readiness/history")
    def readiness_history(limit: int = Query(default=100, ge=1, le=500)):
        if registry is None or not hasattr(registry, "list_readiness"):
            raise HTTPException(503, "enterprise_registry_not_activated")
        rows = list(registry.list_readiness(limit=limit))
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "count": len(rows),
            "items": [dict(row) for row in rows],
        }

    return router
