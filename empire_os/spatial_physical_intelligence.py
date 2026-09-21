"""Volumetric and natural-physical intelligence contracts.

These contracts let Empire represent spatial/3D observations and measured
physical-state evidence without granting execution authority or turning
modeled inference into observed truth.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


_ALLOWED_REPRESENTATIONS = {
    "point_cloud",
    "mesh",
    "gaussian_splat",
    "depth_map",
    "voxel_grid",
    "digital_twin_geometry",
    "footprint_3d",
}

_ALLOWED_PHENOMENA = {
    "storm_damage",
    "roof_condition",
    "thermal_loss",
    "hvac_load",
    "flood_exposure",
    "structural_load",
    "material_degradation",
    "solar_exposure",
    "asset_motion",
    "surface_change",
}


def _clean_refs(refs: tuple[str, ...]) -> tuple[str, ...]:
    clean = tuple(str(value).strip() for value in refs if str(value).strip())
    if not clean:
        raise ValueError("spatial/physical intelligence requires evidence refs")
    return clean


@dataclass(frozen=True)
class VolumetricObservation:
    subject_ref: str
    source: str
    observed_at: str
    representation: str
    evidence_refs: tuple[str, ...]
    coordinate_frame: str | None = None
    geometry_ref: str | None = None
    confidence: float | None = None
    execution_authority: str = "none"

    def __post_init__(self) -> None:
        if not self.subject_ref.strip():
            raise ValueError("volumetric observation requires subject_ref")
        if not self.source.strip():
            raise ValueError("volumetric observation requires source")
        if not self.observed_at.strip():
            raise ValueError("volumetric observation requires observed_at")
        if self.representation not in _ALLOWED_REPRESENTATIONS:
            raise ValueError("unsupported volumetric representation")
        object.__setattr__(self, "evidence_refs", _clean_refs(self.evidence_refs))
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.execution_authority != "none":
            raise ValueError("volumetric intelligence cannot grant execution")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PhysicalObservation:
    subject_ref: str
    source: str
    observed_at: str
    phenomenon: str
    evidence_refs: tuple[str, ...]
    measurements: Mapping[str, float] | None = None
    units: Mapping[str, str] | None = None
    confidence: float | None = None
    execution_authority: str = "none"

    def __post_init__(self) -> None:
        if not self.subject_ref.strip():
            raise ValueError("physical observation requires subject_ref")
        if not self.source.strip():
            raise ValueError("physical observation requires source")
        if not self.observed_at.strip():
            raise ValueError("physical observation requires observed_at")
        if self.phenomenon not in _ALLOWED_PHENOMENA:
            raise ValueError("unsupported physical phenomenon")
        object.__setattr__(self, "evidence_refs", _clean_refs(self.evidence_refs))
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.execution_authority != "none":
            raise ValueError("physical intelligence cannot grant execution")

        measurements = dict(self.measurements or {})
        units = dict(self.units or {})
        if units and set(units) - set(measurements):
            raise ValueError("units cannot exist without matching measurements")

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["measurements"] = dict(self.measurements or {})
        data["units"] = dict(self.units or {})
        return data


@dataclass(frozen=True)
class SpatialPhysicalOpportunity:
    subject_ref: str
    opportunity_type: str
    physical_basis: str
    evidence_refs: tuple[str, ...]
    confidence: float | None = None
    modeled_only: bool = True
    execution_authority: str = "none"

    def __post_init__(self) -> None:
        if not self.subject_ref.strip():
            raise ValueError("opportunity requires subject_ref")
        if not self.opportunity_type.strip():
            raise ValueError("opportunity requires opportunity_type")
        if not self.physical_basis.strip():
            raise ValueError("opportunity requires physical_basis")
        object.__setattr__(self, "evidence_refs", _clean_refs(self.evidence_refs))
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.modeled_only is not True:
            raise ValueError("spatial/physical opportunity must remain modeled_only")
        if self.execution_authority != "none":
            raise ValueError("spatial/physical opportunity cannot grant execution")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
