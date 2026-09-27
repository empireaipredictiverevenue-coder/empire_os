"""OBSERVE-only Data Plane architecture/readiness API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.data_plane_readiness import (
    assess_data_contract_readiness,
    assess_data_plane_readiness,
    assess_replay_plan,
)
from empire_os.data_plane_contracts import (
    build_event_envelope,
    build_lineage_run,
    build_point_in_time_feature,
    build_raw_evidence_ref,
)


class DataPlaneReadinessRequest(BaseModel):
    evidence: dict[str, Any] = Field(default_factory=dict)


class DataContractPreviewRequest(BaseModel):
    contract: dict[str, Any] = Field(default_factory=dict)


class ReplayPlanRequest(BaseModel):
    request: dict[str, Any] = Field(default_factory=dict)


class DataArtifactPreviewRequest(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


def create_data_plane_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/data-plane",
        tags=["data-plane"],
    )

    def preview(builder, data):
        try:
            return builder(data)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "execution_authority": "none",
            "canonical_operational_truth": "supabase_postgresql",
            "deployment_enabled": False,
            "provisioning_enabled": False,
            "schema_mutation": False,
            "migration_execution": False,
            "replay_execution": False,
        }

    @router.post("/readiness/preview")
    def readiness(req: DataPlaneReadinessRequest):
        return assess_data_plane_readiness(req.evidence)

    @router.post("/contract/readiness/preview")
    def contract_readiness(req: DataContractPreviewRequest):
        return assess_data_contract_readiness(req.contract)

    @router.post("/replay/plan/preview")
    def replay_plan(req: ReplayPlanRequest):
        return assess_replay_plan(req.request)

    @router.post("/raw-evidence/preview")
    def raw_evidence(req: DataArtifactPreviewRequest):
        return preview(build_raw_evidence_ref, req.data)

    @router.post("/event/preview")
    def event_preview(req: DataArtifactPreviewRequest):
        return preview(build_event_envelope, req.data)

    @router.post("/lineage/preview")
    def lineage_preview(req: DataArtifactPreviewRequest):
        return preview(build_lineage_run, req.data)

    @router.post("/feature/preview")
    def feature_preview(req: DataArtifactPreviewRequest):
        return preview(build_point_in_time_feature, req.data)

    return router
