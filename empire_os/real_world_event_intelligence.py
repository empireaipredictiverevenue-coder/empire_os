"""Grounded real-world event evidence and truth contracts.

Separates observing a source record from what that source asserts and from
independently established physical truth. This module grants no execution or
commercial authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Mapping


class SourceObservationTruth(str, Enum):
    OBSERVED_SOURCE_RECORD = "OBSERVED_SOURCE_RECORD"


class EventAssertionTruth(str, Enum):
    SOURCE_REPORTS_OBSERVED = "SOURCE_REPORTS_OBSERVED"
    SOURCE_REPORTS_LIKELY = "SOURCE_REPORTS_LIKELY"
    SOURCE_REPORTS_POSSIBLE = "SOURCE_REPORTS_POSSIBLE"
    SOURCE_FORECAST = "SOURCE_FORECAST"
    SOURCE_UNKNOWN = "SOURCE_UNKNOWN"


class PhysicalEventTruth(str, Enum):
    UNKNOWN = "UNKNOWN"
    INFERRED = "INFERRED"
    CORROBORATED = "CORROBORATED"
    VERIFIED = "VERIFIED"


def _aware(value: datetime | None, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")


def canonical_evidence_hash(payload: Mapping[str, Any]) -> str:
    """Stable integrity hash; never independent verification of truth."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class SourceEvidence:
    source: str
    source_record_id: str
    retrieved_at: datetime
    evidence_refs: tuple[str, ...]
    raw_evidence_hash: str

    issued_at: datetime | None = None
    effective_at: datetime | None = None
    onset_at: datetime | None = None
    expires_at: datetime | None = None
    ends_at: datetime | None = None
    response: str | None = None
    sender_name: str | None = None
    nws_headline: str | None = None

    status: str | None = None
    message_type: str | None = None
    category: str | None = None
    source_severity: str | None = None
    certainty: str | None = None
    urgency: str | None = None
    phenomenon: str | None = None
    geographic_scope: str | None = None

    source_truth: SourceObservationTruth = (
        SourceObservationTruth.OBSERVED_SOURCE_RECORD
    )
    execution_authority: str = "none"
    outreach_authority: str = "none"
    traffic_authority: str = "none"
    calls_authority: str = "none"
    payment_authority: str = "none"
    revenue_recognition_authority: str = "none"
    commercial_authority: str = "none"

    def __post_init__(self) -> None:
        for key in AUTHORITY_FIELDS:
            if getattr(self, key) != "none":
                raise ValueError("event truth cannot grant external authority")
        for value in asdict(self).values():
            if isinstance(value, str) and len(value) > 4096:
                raise ValueError("source_field_invalid")
        if len(self.evidence_refs) > 33 or any(not isinstance(ref, str) or len(ref) > 4096 for ref in self.evidence_refs):
            raise ValueError("source_references_invalid")
        if not self.source.strip():
            raise ValueError("source required")
        if not self.source_record_id.strip():
            raise ValueError("source_record_id required")
        if not self.evidence_refs or any(not str(x).strip() for x in self.evidence_refs):
            raise ValueError("evidence_refs required")
        if len(self.raw_evidence_hash) != 64 or any(c not in "0123456789abcdef" for c in self.raw_evidence_hash):
            raise ValueError("sha256 raw_evidence_hash required")

        if self.retrieved_at is None:
            raise ValueError("retrieved_at required")
        if self.source_truth != SourceObservationTruth.OBSERVED_SOURCE_RECORD:
            raise ValueError("invalid source truth")
        for name in (
            "retrieved_at",
            "issued_at",
            "effective_at",
            "onset_at",
            "expires_at",
            "ends_at",
        ):
            _aware(getattr(self, name), name)

        if self.execution_authority != "none":
            raise ValueError("event evidence cannot grant execution")
        if self.commercial_authority != "none":
            raise ValueError("event evidence cannot grant commercial authority")

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key in (
            "retrieved_at",
            "issued_at",
            "effective_at",
            "onset_at",
            "expires_at",
            "ends_at",
        ):
            item = getattr(self, key)
            value[key] = item.isoformat() if item is not None else None
        value["source_truth"] = self.source_truth.value
        return value


@dataclass(frozen=True)
class EventAssertion:
    source_record_id: str
    phenomenon: str
    geographic_scope: str
    assertion_truth: EventAssertionTruth
    evidence_refs: tuple[str, ...]
    execution_authority: str = "none"
    outreach_authority: str = "none"
    traffic_authority: str = "none"
    calls_authority: str = "none"
    commercial_authority: str = "none"
    payment_authority: str = "none"
    revenue_recognition_authority: str = "none"

    def __post_init__(self) -> None:
        for key in AUTHORITY_FIELDS:
            if getattr(self, key) != "none":
                raise ValueError("event truth cannot grant external authority")
        if not isinstance(self.assertion_truth, EventAssertionTruth):
            raise ValueError("invalid assertion truth")
        if not self.source_record_id.strip():
            raise ValueError("source_record_id required")
        if not self.phenomenon.strip():
            raise ValueError("phenomenon required")
        if not self.geographic_scope.strip():
            raise ValueError("geographic_scope required")
        if not self.evidence_refs:
            raise ValueError("evidence_refs required")
        if self.execution_authority != "none":
            raise ValueError("event assertion cannot grant execution")


@dataclass(frozen=True)
class EventTruthAssessment:
    event_id: str
    assertion: EventAssertion
    source_count: int
    independent_source_count: int
    agreement_state: str
    conflict_state: str
    confidence: float | None
    physical_truth: PhysicalEventTruth = PhysicalEventTruth.UNKNOWN
    execution_authority: str = "none"
    traffic_authority: str = "none"
    calls_authority: str = "none"
    outreach_authority: str = "none"
    commercial_authority: str = "none"
    payment_authority: str = "none"
    revenue_recognition_authority: str = "none"

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id required")
        if self.source_count < 1:
            raise ValueError("source_count must be positive")
        if not 1 <= self.independent_source_count <= self.source_count:
            raise ValueError("invalid independent_source_count")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be 0..1")

        if not isinstance(self.physical_truth, PhysicalEventTruth):
            raise ValueError("invalid physical truth")
        if self.physical_truth in (PhysicalEventTruth.CORROBORATED, PhysicalEventTruth.VERIFIED):
            raise ValueError("independent physical verification pipeline required")

        for value in (
            self.execution_authority,
            self.outreach_authority,
            self.traffic_authority,
            self.calls_authority,
            self.commercial_authority,
            self.payment_authority,
            self.revenue_recognition_authority,
        ):
            if value != "none":
                raise ValueError("event truth cannot grant external authority")


def assertion_truth_from_source(
    *,
    certainty: str | None,
    message_type: str | None = None,
) -> EventAssertionTruth:
    certainty_key = str(certainty or "").strip().casefold()
    message_key = str(message_type or "").strip().casefold()

    if certainty_key == "observed":
        return EventAssertionTruth.SOURCE_REPORTS_OBSERVED
    if certainty_key == "likely":
        return EventAssertionTruth.SOURCE_REPORTS_LIKELY
    if certainty_key == "possible":
        return EventAssertionTruth.SOURCE_REPORTS_POSSIBLE
    if message_key in {"forecast", "outlook"}:
        return EventAssertionTruth.SOURCE_FORECAST
    return EventAssertionTruth.SOURCE_UNKNOWN


AUTHORITY_FIELDS = ("execution_authority", "outreach_authority", "traffic_authority",
                    "calls_authority", "commercial_authority", "payment_authority",
                    "revenue_recognition_authority")
TIMESTAMP_FIELDS = ("retrieved_at", "issued_at", "effective_at", "onset_at",
                    "expires_at", "ends_at")


def source_timestamp(value: Any, *, required: bool = True) -> datetime | None:
    """Parse real source time, never repair it using a clock or assumed zone."""
    if value is None or value == "":
        if not required:
            return None
        raise ValueError("source_timestamp_missing")
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("source_timestamp_invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("source_timestamp_timezone_missing")
    return parsed.astimezone(timezone.utc)


def assess_event_truth(evidence: tuple[SourceEvidence, ...]) -> EventTruthAssessment:
    """Conservative convergence foundation, not a physical verification engine.

    Callers must group evidence for the same event. Distinct providers are not
    assumed independent: independence remains unestablished beyond one origin.
    Contradictory versions remain visible, including from a single provider.
    """
    if not evidence:
        raise ValueError("source evidence required")
    rows = sorted(evidence, key=lambda e: (e.source, e.source_record_id, e.raw_evidence_hash))
    first = rows[0]
    truths = {assertion_truth_from_source(certainty=e.certainty, message_type=e.message_type) for e in rows}
    versions = {}
    for e in rows:
        versions.setdefault((e.source, e.source_record_id), set()).add(e.raw_evidence_hash)
    conflict = len(truths) > 1 or any(len(v) > 1 for v in versions.values())
    assertion = EventAssertion(first.source_record_id, first.phenomenon or "UNKNOWN",
        first.geographic_scope or "UNKNOWN",
        next(iter(truths)) if len(truths) == 1 else EventAssertionTruth.SOURCE_UNKNOWN,
        tuple(sorted({ref for e in rows for ref in e.evidence_refs})))
    return EventTruthAssessment(first.source_record_id, assertion, len(versions), 1,
        "CONFLICT" if conflict else ("SINGLE_SOURCE" if len(versions) == 1 else "CONSISTENT_ASSERTIONS"),
        "CONFLICTING_SOURCE_ASSERTIONS" if conflict else "NONE_DETECTED", None)


def normalized_event_evidence(evidence: SourceEvidence) -> dict[str, Any]:
    result = evidence.as_dict()
    result["evidence_refs"] = list(evidence.evidence_refs)
    assessment = assess_event_truth((evidence,))
    result.update(assertion_truth=assessment.assertion.assertion_truth.value,
                  physical_truth=assessment.physical_truth.value)
    result.update({key: "none" for key in AUTHORITY_FIELDS})
    return result


def replay_source_evidence(row: Mapping[str, Any]) -> SourceEvidence:
    """Revalidate persisted normalized evidence, ignoring no authority promotion."""
    from dataclasses import fields
    if any(row.get(key, "none") != "none" for key in AUTHORITY_FIELDS):
        raise ValueError("event truth cannot grant external authority")
    kwargs = {f.name: row[f.name] for f in fields(SourceEvidence) if f.name in row}
    for key in TIMESTAMP_FIELDS:
        kwargs[key] = source_timestamp(row.get(key), required=key == "retrieved_at")
    kwargs["source_truth"] = SourceObservationTruth(row["source_truth"])
    kwargs["evidence_refs"] = tuple(row["evidence_refs"])
    evidence = SourceEvidence(**kwargs)
    if evidence.source == "nws_alert":
        source_timestamp(evidence.issued_at)
        payload = evidence.as_dict()
        for key in (*AUTHORITY_FIELDS, "retrieved_at", "source_truth", "raw_evidence_hash"):
            payload.pop(key, None)
        if canonical_evidence_hash(payload) != evidence.raw_evidence_hash:
            raise ValueError("evidence_hash_mismatch")
    expected = normalized_event_evidence(evidence)
    if row.get("physical_truth") != "UNKNOWN" or row.get("assertion_truth") != expected["assertion_truth"]:
        raise ValueError("invalid replay truth")
    return evidence
