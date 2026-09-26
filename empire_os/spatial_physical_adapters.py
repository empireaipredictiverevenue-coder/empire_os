"""Adapters from existing Empire sensors into spatial/physical contracts.

Adapters fail closed: weather exposure is not damage, heuristic satellite
scoring is not accepted as physical-condition evidence, and flat imagery does
not become volumetric evidence.
"""
from __future__ import annotations

from empire_os.satellite_scanner import SatelliteScanResult
from empire_os.spatial_physical_intelligence import PhysicalObservation
from empire_os.storm_predictor import StormEvent


_CERTAINTY_CONFIDENCE = {
    "observed": 0.95,
    "likely": 0.80,
    "possible": 0.60,
    "unlikely": 0.35,
}


def physical_from_storm_event(
    event: StormEvent,
) -> PhysicalObservation:
    if not str(event.event_id or "").strip():
        raise ValueError("storm event requires event_id")
    if not str(event.area_description or "").strip():
        raise ValueError("storm event requires area_description")
    if not str(event.occurred_at or "").strip():
        raise ValueError("storm event requires occurred_at")

    if not 1 <= int(event.severity) <= 5:
        raise ValueError("storm severity must be 1..5")
    certainty = str((event.raw or {}).get("certainty") or "").strip().lower()
    confidence = _CERTAINTY_CONFIDENCE.get(certainty)

    return PhysicalObservation(
        subject_ref=f"territory:{event.area_description.strip()}",
        source="nws_alert",
        observed_at=event.occurred_at,
        phenomenon="storm_exposure",
        evidence_refs=(event.event_id.strip(),),
        measurements={"severity_index": float(event.severity)},
        units={"severity_index": "ordinal_1_5"},
        confidence=confidence,
        evidence_class="observed",
    )


def physical_from_satellite_vision(
    result: SatelliteScanResult,
    *,
    subject_ref: str,
    evidence_ref: str,
) -> PhysicalObservation:
    if result.method != "llm_vision":
        raise ValueError(
            "only llm_vision satellite results may enter physical intelligence"
        )
    if not str(subject_ref or "").strip():
        raise ValueError("satellite physical observation requires subject_ref")
    if not str(evidence_ref or "").strip():
        raise ValueError("satellite physical observation requires evidence_ref")
    if not str(result.scanned_at or "").strip():
        raise ValueError("satellite result requires scanned_at")

    dominant = str(result.dominant_damage or "").strip().lower()
    if dominant not in {"hail", "wind", "tornado", "flood"}:
        raise ValueError("satellite vision result lacks explicit damage class")
    if result.damage_score <= 0:
        raise ValueError("satellite vision result lacks positive damage evidence")

    confidence = (
        float(result.confidence)
        if result.confidence is not None and result.confidence > 0
        else None
    )

    return PhysicalObservation(
        subject_ref=str(subject_ref).strip(),
        source="satellite_vision",
        observed_at=result.scanned_at,
        phenomenon="storm_damage",
        evidence_refs=(str(evidence_ref).strip(),),
        measurements={
            "damage_score": float(result.damage_score),
            "warehouses_detected": float(result.warehouses_detected),
        },
        units={
            "damage_score": "score_0_100",
            "warehouses_detected": "count",
        },
        confidence=confidence,
        evidence_class="model_inference",
    )
