"""Read-only enterprise control and SLO status API."""
from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from fastapi import APIRouter, HTTPException, Query

from empire_os.enterprise_controls import ControlEvidence, SloObservation
from empire_os.enterprise_review import review_enterprise_readiness


class EnterpriseEvidenceRepository(Protocol):
    def controls(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def slos(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...


def create_enterprise_router(
    repository: EnterpriseEvidenceRepository | None = None,
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

    return router
