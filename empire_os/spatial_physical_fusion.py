"""Evidence-backed fusion of storm, volumetric and physical intelligence.

This module ranks modeled opportunities for spatial/physical verticals. It
never creates observed measurements, revenue truth, or execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.digital_twin import MarketScenario
from empire_os.spatial_physical_intelligence import (
    PhysicalObservation,
    VolumetricObservation,
)
from empire_os.storm_revenue_multiplier import StormOpportunityMultiplier


VERTICAL_PHENOMENA: dict[str, frozenset[str]] = {
    "roofing": frozenset({
        "storm_damage",
        "roof_condition",
        "surface_change",
        "material_degradation",
        "solar_exposure",
    }),
    "roofing restoration": frozenset({
        "storm_damage",
        "roof_condition",
        "surface_change",
        "material_degradation",
        "flood_exposure",
    }),
    "restoration": frozenset({
        "storm_damage",
        "flood_exposure",
        "surface_change",
        "material_degradation",
    }),
    "solar": frozenset({
        "solar_exposure",
        "roof_condition",
        "surface_change",
        "material_degradation",
    }),
    "solar_energy": frozenset({
        "solar_exposure",
        "roof_condition",
        "surface_change",
        "material_degradation",
    }),
    "hvac": frozenset({
        "thermal_loss",
        "hvac_load",
        "material_degradation",
        "extreme_heat",
    }),
    "property": frozenset({
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
    }),
    "structural_repair": frozenset({
        "storm_damage",
        "structural_load",
        "asset_motion",
        "surface_change",
        "material_degradation",
    }),
}


@dataclass(frozen=True)
class SpatialPhysicalPriority:
    subject_ref: str
    vertical: str
    spatial_confidence: float | None
    physical_confidence: float | None
    physical_phenomenon: str | None
    physical_relevant: bool
    storm_multiplier: float | None
    storm_priority_boost: float
    spatial_physical_priority_boost: float
    combined_priority_boost: float
    demand_multiplier_hint: float
    evidence_refs: tuple[str, ...]
    modeled_only: bool = True
    execution_authority: str = "none"

    def validate(self) -> None:
        if not self.subject_ref.strip():
            raise ValueError("fusion requires subject_ref")
        if not self.vertical.strip():
            raise ValueError("fusion requires vertical")
        if not self.evidence_refs:
            raise ValueError("fusion requires evidence refs")
        if self.spatial_confidence is not None and not 0 <= self.spatial_confidence <= 1:
            raise ValueError("spatial confidence must be 0..1")
        if self.physical_confidence is not None and not 0 <= self.physical_confidence <= 1:
            raise ValueError("physical confidence must be 0..1")
        if self.storm_priority_boost < 0:
            raise ValueError("storm priority boost must be nonnegative")
        if not 0 <= self.spatial_physical_priority_boost <= 20:
            raise ValueError("spatial/physical priority boost must be 0..20")
        if not 0 <= self.combined_priority_boost <= 60:
            raise ValueError("combined priority boost must be 0..60")
        if not 1 <= self.demand_multiplier_hint <= 3:
            raise ValueError("demand multiplier hint must be 1..3")
        if self.modeled_only is not True:
            raise ValueError("fusion must remain modeled_only")
        if self.execution_authority != "none":
            raise ValueError("fusion cannot grant execution")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def _confidence(value: float | None) -> float:
    return float(value) if value is not None else 0.0


def fuse_spatial_physical_priority(
    *,
    vertical: str,
    volumetric: VolumetricObservation | None = None,
    physical: PhysicalObservation | None = None,
    storm: StormOpportunityMultiplier | None = None,
) -> SpatialPhysicalPriority:
    if volumetric is None and physical is None:
        raise ValueError("fusion requires volumetric or physical evidence")

    subject_refs = {
        row.subject_ref
        for row in (volumetric, physical)
        if row is not None
    }
    if len(subject_refs) != 1:
        raise ValueError("spatial/physical subject identity mismatch")
    subject_ref = next(iter(subject_refs))

    vertical_key = str(vertical or "").strip().lower()
    supported = VERTICAL_PHENOMENA.get(vertical_key, frozenset())
    physical_relevant = (
        physical is not None
        and physical.phenomenon in supported
    )

    spatial_confidence = (
        volumetric.confidence
        if volumetric is not None
        else None
    )
    physical_confidence = (
        physical.confidence
        if physical_relevant and physical is not None
        else None
    )

    # Volumetric confirmation may add up to 8 priority points. Relevant
    # physical-condition evidence may add up to 12. Unknown confidence adds 0.
    spatial_boost = 8.0 * _confidence(spatial_confidence)
    physical_boost = 12.0 * _confidence(physical_confidence)
    spatial_physical_boost = round(
        min(20.0, spatial_boost + physical_boost),
        2,
    )

    storm_priority = (
        storm.priority_boost
        if storm is not None and storm.relevant
        else 0.0
    )
    combined = round(
        min(60.0, storm_priority + spatial_physical_boost),
        2,
    )

    base_demand_multiplier = (
        storm.multiplier
        if storm is not None and storm.relevant
        else 1.0
    )
    demand_multiplier = round(
        min(
            3.0,
            base_demand_multiplier * (1.0 + spatial_physical_boost / 100.0),
        ),
        3,
    )

    refs: list[str] = []
    if volumetric is not None:
        refs.extend(volumetric.evidence_refs)
    if physical is not None:
        refs.extend(physical.evidence_refs)
    if storm is not None:
        refs.extend(storm.evidence_refs)

    result = SpatialPhysicalPriority(
        subject_ref=subject_ref,
        vertical=vertical_key,
        spatial_confidence=spatial_confidence,
        physical_confidence=physical_confidence,
        physical_phenomenon=(
            physical.phenomenon
            if physical is not None
            else None
        ),
        physical_relevant=physical_relevant,
        storm_multiplier=(
            storm.multiplier
            if storm is not None and storm.relevant
            else None
        ),
        storm_priority_boost=round(storm_priority, 2),
        spatial_physical_priority_boost=spatial_physical_boost,
        combined_priority_boost=combined,
        demand_multiplier_hint=demand_multiplier,
        evidence_refs=tuple(dict.fromkeys(refs)),
    )
    result.validate()
    return result


def digital_twin_demand_scenario(
    *,
    scenario_id: str,
    priority: SpatialPhysicalPriority,
) -> MarketScenario:
    priority.validate()
    if not str(scenario_id or "").strip():
        raise ValueError("scenario_id required")
    return MarketScenario(
        scenario_id=str(scenario_id).strip(),
        demand_multiplier=priority.demand_multiplier_hint,
        capacity_multiplier=1.0,
        price_multiplier=1.0,
    )


def digital_twin_evidence(
    priority: SpatialPhysicalPriority,
) -> dict[str, Any]:
    priority.validate()
    return {
        "source": "spatial_physical_fusion",
        "subject_ref": priority.subject_ref,
        "vertical": priority.vertical,
        "physical_phenomenon": priority.physical_phenomenon,
        "physical_relevant": priority.physical_relevant,
        "combined_priority_boost": priority.combined_priority_boost,
        "demand_multiplier_hint": priority.demand_multiplier_hint,
        "evidence_refs": list(priority.evidence_refs),
        "modeled_only": True,
        "actual_revenue": False,
        "execution_authority": "none",
    }
