"""Adapters from existing Empire sensors into spatial/physical contracts.

Adapters fail closed: weather exposure is not damage, heuristic satellite
scoring is not accepted as physical-condition evidence, and flat imagery does
not become volumetric evidence.
"""
from __future__ import annotations

from empire_os.satellite_scanner import SatelliteScanResult
from empire_os.spatial_physical_intelligence import PhysicalObservation
from empire_os.storm_predictor import StormEvent


def event_evidence_from_storm_event(event: StormEvent, *, retrieved_at=None):
    """Normalize allowlisted NWS properties; source severity is not damage."""
    from empire_os.real_world_event_intelligence import SourceEvidence, canonical_evidence_hash, source_timestamp
    raw = getattr(event, "raw", {})
    if not isinstance(raw, dict):
        raise ValueError("source_record_invalid")

    def text(value):
        if value is None:
            return None
        if not isinstance(value, str) or len(value) > 4096:
            raise ValueError("source_field_invalid")
        return value.strip() or None

    record_id = text(event.event_id)
    if not record_id:
        raise ValueError("source_record_id_missing")
    values = {}
    for target, key in (("issued_at", "sent"), ("effective_at", "effective"),
                        ("onset_at", "onset"), ("expires_at", "expires"), ("ends_at", "ends")):
        fallback = getattr(event, "occurred_at", None) if key == "sent" else (getattr(event, "expires_at", None) if key == "expires" else None)
        values[target] = source_timestamp(raw.get(key, fallback), required=key == "sent")
    for target, key in (("status", "status"), ("message_type", "messageType"),
                        ("category", "category"), ("source_severity", "severity"),
                        ("certainty", "certainty"), ("urgency", "urgency"),
                        ("response", "response"), ("sender_name", "senderName")):
        values[target] = text(raw.get(key))
    values["phenomenon"] = text(raw.get("event", event.event_type))
    values["geographic_scope"] = text(raw.get("areaDesc", event.area_description))
    params = raw.get("parameters") or {}
    if not isinstance(params, dict):
        raise ValueError("source_parameters_invalid")
    headlines = params.get("NWSheadline", [])
    refs = params.get("VTEC", [])
    if not isinstance(headlines, list) or not isinstance(refs, list) or len(refs) > 32 or len(headlines) > 16:
        raise ValueError("source_references_invalid")
    values["nws_headline"] = text("; ".join(text(v) or "" for v in headlines))
    refs = tuple(sorted({record_id, *(text(v) for v in refs if text(v))}))
    # Hash the bounded source evidence projection, excluding retrieval time.
    payload = {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in values.items()}
    payload.update(source="nws_alert", source_record_id=record_id, evidence_refs=refs)
    return SourceEvidence(source="nws_alert", source_record_id=record_id,
        retrieved_at=source_timestamp(retrieved_at or getattr(event, "retrieved_at", None)),
        evidence_refs=refs, raw_evidence_hash=canonical_evidence_hash(payload), **values)


def physical_from_storm_event(event: StormEvent) -> PhysicalObservation:
    # This compatibility projection is a derived territory alert signal only.
    from datetime import datetime, timezone
    from empire_os.real_world_event_intelligence import assertion_truth_from_source
    evidence = event_evidence_from_storm_event(event, retrieved_at=getattr(event, "retrieved_at", None) or datetime.now(timezone.utc))
    issued = evidence.issued_at
    if not event.event_id or not event.area_description:
        raise ValueError("storm identity and geographic scope required")
    return PhysicalObservation(
        subject_ref=f"territory:{event.area_description.strip()}", source="nws_alert",
        observed_at=issued.isoformat(), phenomenon="storm_exposure",
        evidence_refs=(event.event_id.strip(),), measurements={}, units={},
        confidence=None, evidence_class="derived_signal",
        source_truth=evidence.source_truth.value,
        assertion_truth=assertion_truth_from_source(certainty=evidence.certainty, message_type=evidence.message_type).value,
        physical_truth="UNKNOWN",
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
        physical_truth="INFERRED",
    )


def footprint_from_storm_event(event: StormEvent, *, tenant_id: str, evidence=None):
    """Preserve genuine NWS geometry; areaDesc never becomes a polygon."""
    import json
    from empire_os.real_world_event_intelligence import normalized_event_evidence
    from empire_os.real_world_exposure_graph import (
        FootprintEvidence, GeographicFootprint, SpatialLocation, SpatialPrecision,
    )
    evidence = evidence or event_evidence_from_storm_event(event)
    raw = getattr(event, "raw", {})
    geometry = raw.get("geometry")
    area = evidence.geographic_scope
    if geometry is None:
        location = SpatialLocation(SpatialPrecision.TEXT_AREA_ONLY if area else SpatialPrecision.UNKNOWN,
                                   "None", (), area)
    else:
        if not isinstance(geometry, dict):
            raise ValueError("invalid_source_geometry")
        location = SpatialLocation(SpatialPrecision.SOURCE_GEOMETRY,
                                   geometry.get("type"), geometry.get("coordinates"), area)
    retained = normalized_event_evidence(evidence)
    return GeographicFootprint(
        tenant_id, evidence.source_record_id, location,
        FootprintEvidence(evidence.source, evidence.source_record_id,
                          evidence.issued_at or evidence.retrieved_at, evidence.evidence_refs,
                          evidence.source_truth.value, json.dumps(retained)),
        evidence.onset_at or evidence.effective_at or evidence.issued_at or evidence.retrieved_at,
        evidence.ends_at or evidence.expires_at, "NWS_SOURCE_GEOMETRY" if geometry is not None else "NWS_AREA_DESCRIPTION",
    )
