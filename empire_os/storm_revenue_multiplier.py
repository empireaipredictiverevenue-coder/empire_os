"""Evidence-backed storm opportunity multiplier.

This module does not create revenue, send outreach, or mutate CRM state.
It converts fresh weather evidence into a bounded prioritisation multiplier
for storm-sensitive niches. The historical Empire disaster premium capped at
3x is preserved as the maximum modeled multiplier.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

MAX_MULTIPLIER = 3.0

STORM_SENSITIVE_NICHES = {
    "roofing", "roofing restoration", "restoration",
    "water_damage_restoration", "flood_damage", "disaster_recovery",
    "general_contractor", "hvac", "emergency_plumbing",
    "fire_damage_restoration", "structural_repair",
}

EVENT_WEIGHT = {
    "tornado": 1.00,
    "hurricane": 1.00,
    "hail": 0.95,
    "severe thunderstorm": 0.85,
    "wind": 0.75,
    "flash flood": 0.85,
    "flood": 0.75,
    "wildfire": 0.85,
    "ice storm": 0.65,
    "winter storm": 0.55,
    "extreme heat": 0.45,
}

SEVERITY_WEIGHT = {
    "extreme": 1.00,
    "severe": 0.90,
    "moderate": 0.65,
    "minor": 0.35,
    "unknown": 0.45,
}


@dataclass(frozen=True)
class StormOpportunityMultiplier:
    multiplier: float
    priority_boost: float
    relevant: bool
    event_type: str
    severity: str
    evidence_confidence: float
    territory_match: float
    freshness: float
    evidence_refs: tuple[str, ...]
    modeled_only: bool = True
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bounded(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, number))


def _freshness(age_hours: float) -> float:
    age = max(0.0, float(age_hours or 0.0))
    if age <= 24:
        return 1.0
    if age <= 48:
        return 0.82
    if age <= 72:
        return 0.64
    if age <= 120:
        return 0.40
    if age <= 168:
        return 0.22
    return 0.0


def calculate_storm_multiplier(
    *,
    niche: str,
    event_type: str,
    severity: str = "unknown",
    evidence_confidence: float,
    territory_match: float,
    age_hours: float,
    evidence_refs: Iterable[str],
) -> StormOpportunityMultiplier:
    refs = tuple(
        dict.fromkeys(
            str(ref).strip()
            for ref in evidence_refs
            if str(ref).strip()
        )
    )
    if not refs:
        raise ValueError("storm multiplier requires evidence refs")

    niche_key = str(niche or "").strip().lower()
    event_key = str(event_type or "").strip().lower()
    severity_key = str(severity or "unknown").strip().lower()

    confidence = _bounded(evidence_confidence)
    territory = _bounded(territory_match)
    freshness = _freshness(age_hours)
    relevant = (
        niche_key in STORM_SENSITIVE_NICHES
        and event_key in EVENT_WEIGHT
    )

    if not relevant:
        return StormOpportunityMultiplier(
            multiplier=1.0,
            priority_boost=0.0,
            relevant=False,
            event_type=event_key,
            severity=severity_key,
            evidence_confidence=confidence,
            territory_match=territory,
            freshness=freshness,
            evidence_refs=refs,
        )

    event = EVENT_WEIGHT[event_key]
    severity_factor = SEVERITY_WEIGHT.get(
        severity_key,
        SEVERITY_WEIGHT["unknown"],
    )
    signal = (
        event
        * severity_factor
        * confidence
        * territory
        * freshness
    )
    multiplier = round(
        min(MAX_MULTIPLIER, 1.0 + 2.0 * signal),
        3,
    )
    priority_boost = round(
        min(50.0, max(0.0, (multiplier - 1.0) * 25.0)),
        2,
    )

    return StormOpportunityMultiplier(
        multiplier=multiplier,
        priority_boost=priority_boost,
        relevant=True,
        event_type=event_key,
        severity=severity_key,
        evidence_confidence=confidence,
        territory_match=territory,
        freshness=freshness,
        evidence_refs=refs,
    )
