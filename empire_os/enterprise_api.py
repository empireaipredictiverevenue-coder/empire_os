"""Read-only enterprise control and SLO status API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Protocol, Sequence

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from empire_os.enterprise_controls import ControlEvidence, SloObservation
from empire_os.enterprise_drift import review_enterprise_drift
from empire_os.enterprise_freshness import review_enterprise_evidence
from empire_os.enterprise_review import review_enterprise_readiness
from empire_os.enterprise_remediation import review_enterprise_remediation
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


class EnterpriseFreshnessRequest(BaseModel):
    now_utc: str
    max_age_seconds: int = Field(default=21600, gt=0)
    controls: list[EnterpriseControlRequest] = Field(min_length=1)
    slos: list[EnterpriseSloRequest] = Field(min_length=1)


class EnterpriseDriftRequest(BaseModel):
    now_utc: str
    max_age_seconds: int = Field(default=21600, gt=0)
    baseline_controls: list[EnterpriseControlRequest] = Field(min_length=1)
    current_controls: list[EnterpriseControlRequest] = Field(min_length=1)
    baseline_slos: list[EnterpriseSloRequest] = Field(min_length=1)
    current_slos: list[EnterpriseSloRequest] = Field(min_length=1)


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

    @router.post("/freshness/preview")
    def freshness_preview(req: EnterpriseFreshnessRequest):
        try:
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            controls = tuple(
                ControlEvidence(**row.model_dump()) for row in req.controls
            )
            slos = tuple(
                SloObservation(**row.model_dump()) for row in req.slos
            )
            review = review_enterprise_evidence(
                controls=controls,
                slos=slos,
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "side_effects": "none",
            "execution_authority": "none",
            "control_mutation": False,
            "infrastructure_mutation": False,
            "identity_mutation": False,
            "backup_mutation": False,
            "slo_target_mutation": False,
            "compliance_mutation": False,
            "review": review.as_dict(),
        }

    @router.post("/remediation/preview")
    def remediation_preview(req: EnterpriseFreshnessRequest):
        try:
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            controls = tuple(
                ControlEvidence(**row.model_dump()) for row in req.controls
            )
            slos = tuple(
                SloObservation(**row.model_dump()) for row in req.slos
            )
            freshness = review_enterprise_evidence(
                controls=controls,
                slos=slos,
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
            review = review_enterprise_remediation(
                controls=controls,
                slos=slos,
                freshness=freshness,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "side_effects": "none",
            "execution_authority": "none",
            "control_mutation": False,
            "infrastructure_mutation": False,
            "identity_mutation": False,
            "backup_mutation": False,
            "slo_target_mutation": False,
            "compliance_mutation": False,
            "deployment_execution": False,
            "review": review.as_dict(),
        }

    @router.post("/drift/preview")
    def drift_preview(req: EnterpriseDriftRequest):
        try:
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            review = review_enterprise_drift(
                baseline_controls=tuple(
                    ControlEvidence(**row.model_dump())
                    for row in req.baseline_controls
                ),
                current_controls=tuple(
                    ControlEvidence(**row.model_dump())
                    for row in req.current_controls
                ),
                baseline_slos=tuple(
                    SloObservation(**row.model_dump())
                    for row in req.baseline_slos
                ),
                current_slos=tuple(
                    SloObservation(**row.model_dump())
                    for row in req.current_slos
                ),
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {
            "mode": "OBSERVE",
            "side_effects": "none",
            "execution_authority": "none",
            "control_mutation": False,
            "infrastructure_mutation": False,
            "identity_mutation": False,
            "backup_mutation": False,
            "slo_target_mutation": False,
            "compliance_mutation": False,
            "drift": review.as_dict(),
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
