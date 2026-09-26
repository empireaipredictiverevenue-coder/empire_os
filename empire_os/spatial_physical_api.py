"""Read-only spatial and physical intelligence API."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from empire_os.spatial_physical_fusion import (
    digital_twin_demand_scenario,
    digital_twin_evidence,
    fuse_spatial_physical_priority,
)
from empire_os.spatial_physical_intelligence import (
    PhysicalObservation,
    VolumetricObservation,
)
from empire_os.spatial_physical_runtime import build_spatial_physical_runtime
from empire_os.storm_revenue_multiplier import calculate_storm_multiplier


EvidenceClass = Literal["observed", "model_inference", "derived_signal"]


class VolumetricObservationRequest(BaseModel):
    subject_ref: str
    source: str
    observed_at: str
    representation: str
    evidence_refs: list[str] = Field(min_length=1)
    coordinate_frame: str | None = None
    geometry_ref: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_class: EvidenceClass = "observed"


class PhysicalObservationRequest(BaseModel):
    subject_ref: str
    source: str
    observed_at: str
    phenomenon: str
    evidence_refs: list[str] = Field(min_length=1)
    measurements: dict[str, float] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_class: EvidenceClass = "observed"


class StormEvidenceRequest(BaseModel):
    niche: str
    event_type: str
    severity: str = "unknown"
    evidence_confidence: float = Field(ge=0, le=1)
    territory_match: float = Field(ge=0, le=1)
    age_hours: float = Field(ge=0)
    evidence_refs: list[str] = Field(min_length=1)


class SpatialPhysicalPreviewRequest(BaseModel):
    vertical: str
    volumetric: VolumetricObservationRequest | None = None
    physical: PhysicalObservationRequest | None = None
    storm: StormEvidenceRequest | None = None
    digital_twin_scenario_id: str | None = None


def _volumetric(req: VolumetricObservationRequest | None):
    if req is None:
        return None
    return VolumetricObservation(
        subject_ref=req.subject_ref,
        source=req.source,
        observed_at=req.observed_at,
        representation=req.representation,
        evidence_refs=tuple(req.evidence_refs),
        coordinate_frame=req.coordinate_frame,
        geometry_ref=req.geometry_ref,
        confidence=req.confidence,
        evidence_class=req.evidence_class,
    )


def _physical(req: PhysicalObservationRequest | None):
    if req is None:
        return None
    return PhysicalObservation(
        subject_ref=req.subject_ref,
        source=req.source,
        observed_at=req.observed_at,
        phenomenon=req.phenomenon,
        evidence_refs=tuple(req.evidence_refs),
        measurements=req.measurements,
        units=req.units,
        confidence=req.confidence,
        evidence_class=req.evidence_class,
    )


def _storm(req: StormEvidenceRequest | None):
    if req is None:
        return None
    return calculate_storm_multiplier(
        niche=req.niche,
        event_type=req.event_type,
        severity=req.severity,
        evidence_confidence=req.evidence_confidence,
        territory_match=req.territory_match,
        age_hours=req.age_hours,
        evidence_refs=req.evidence_refs,
    )


def create_spatial_physical_router(
    repo_root: Path | None = None,
) -> APIRouter:
    root = repo_root or Path(__file__).resolve().parents[1]
    router = APIRouter(
        prefix="/v1/spatial-physical",
        tags=["spatial-physical-intelligence"],
    )

    @router.get("/status")
    def status():
        payload = build_spatial_physical_runtime(root)
        return {
            **payload,
            "preview_only": True,
            "revenue_mutation": False,
            "execution_allowed": False,
        }

    @router.post("/preview")
    def preview(req: SpatialPhysicalPreviewRequest):
        try:
            volumetric = _volumetric(req.volumetric)
            physical = _physical(req.physical)
            storm = _storm(req.storm)
            fused = fuse_spatial_physical_priority(
                vertical=req.vertical,
                volumetric=volumetric,
                physical=physical,
                storm=storm,
            )
            result = {
                "schema_version": "empire.spatial-physical-preview.v1",
                "mode": "OBSERVE",
                "preview_only": True,
                "execution_authority": "none",
                "execution_allowed": False,
                "actual_revenue": False,
                "revenue_mutation": False,
                "fusion": fused.as_dict(),
                "digital_twin_scenario": None,
                "digital_twin_evidence": None,
            }
            if req.digital_twin_scenario_id:
                scenario = digital_twin_demand_scenario(
                    scenario_id=req.digital_twin_scenario_id,
                    priority=fused,
                )
                result["digital_twin_scenario"] = {
                    "scenario_id": scenario.scenario_id,
                    "demand_multiplier": scenario.demand_multiplier,
                    "capacity_multiplier": scenario.capacity_multiplier,
                    "price_multiplier": scenario.price_multiplier,
                    "simulation_only": True,
                }
                result["digital_twin_evidence"] = digital_twin_evidence(fused)
            return result
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return router
