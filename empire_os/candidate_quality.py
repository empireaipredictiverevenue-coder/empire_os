"""Fail-closed quality boundary for canonical prospect acquisition."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any


PLACEHOLDER_NAMES = frozenset({
    "",
    "na",
    "n/a",
    "none",
    "unknown",
    "not available",
    "not applicable",
    "tbd",
    "test",
})

# These sources can reveal demand/opportunity, but their rows are not
# themselves verified business identities suitable for canonical prospects.
SIGNAL_ONLY_SOURCES = frozenset({
    "permits_nyc",
    "courtlistener",
    "chicago_311",
    "chicago_permits",
    "nyc_hpd",
    "nws_alerts",
    "storm_alerts",
    "reddit",
    "reddit_json",
})

IDENTITY_OR_DIRECT_SOURCES = frozenset({
    "overpass_osm",
    "aeo_form",
    "manual_import",
})

GENERIC_SIGNAL_PREFIXES = (
    "hpd violation ",
    "nws alert ",
    "storm alert ",
    "311 request ",
)


@dataclass(frozen=True)
class QualityDecision:
    accepted: bool
    reason_codes: tuple[str, ...]
    confidence: int
    entity_kind: str
    source_role: str

    def to_evidence(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason_codes": list(self.reason_codes),
            "confidence": self.confidence,
            "entity_kind": self.entity_kind,
            "source_role": self.source_role,
        }


class CandidateQualityError(ValueError):
    """Candidate is not safe to canonicalize as a prospect."""


def _candidate_data(candidate: Any) -> dict[str, Any]:
    if isinstance(candidate, dict):
        return dict(candidate)

    if is_dataclass(candidate):
        return asdict(candidate)

    fields = (
        "name",
        "email",
        "phone",
        "niche",
        "metro",
        "state",
        "details",
        "source",
        "lead_score",
        "url",
        "raw",
    )
    return {
        field: getattr(candidate, field, None)
        for field in fields
    }


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def assess_candidate(candidate: Any) -> QualityDecision:
    """Assess whether a candidate may enter canonical prospect ingest."""
    data = _candidate_data(candidate)

    name = _text(data.get("name"))
    name_key = name.casefold()
    niche = _text(data.get("niche")).casefold()
    metro = _text(data.get("metro")).casefold()
    source = _text(data.get("source")).casefold()

    reasons: list[str] = []

    if source in SIGNAL_ONLY_SOURCES:
        source_role = "signal"
        entity_kind = "signal"
    elif source in IDENTITY_OR_DIRECT_SOURCES:
        source_role = "identity_or_direct"
        entity_kind = "business"
    else:
        source_role = "unknown"
        entity_kind = "unknown"

    if not name:
        reasons.append("missing_name")
    elif name_key in PLACEHOLDER_NAMES:
        reasons.append("placeholder_name")

    if not niche:
        reasons.append("missing_niche")

    if not metro:
        reasons.append("missing_metro")

    if not source:
        reasons.append("missing_source")
    elif source_role == "unknown":
        reasons.append("unclassified_source_role")

    if any(
        name_key.startswith(prefix)
        for prefix in GENERIC_SIGNAL_PREFIXES
    ):
        reasons.append("generated_signal_label")
        entity_kind = "signal"

    if source_role == "signal":
        reasons.append("signal_requires_identity_resolution")

    has_provenance = any((
        _text(data.get("phone")),
        _text(data.get("email")),
        _text(data.get("url")),
        bool(data.get("raw")),
    ))
    if not has_provenance:
        reasons.append("insufficient_identity_evidence")

    confidence = 0

    if name and name_key not in PLACEHOLDER_NAMES:
        confidence += 25
    if niche:
        confidence += 15
    if metro:
        confidence += 15
    if source:
        confidence += 10
    if _text(data.get("phone")):
        confidence += 20
    if _text(data.get("email")):
        confidence += 15
    if _text(data.get("url")):
        confidence += 10
    if data.get("raw"):
        confidence += 10

    confidence = min(confidence, 100)

    # A signal may be high-quality evidence while still being the wrong
    # entity type for canonical prospect creation.
    if source_role == "signal":
        confidence = min(confidence, 40)
    elif source_role == "unknown":
        confidence = min(confidence, 20)

    return QualityDecision(
        accepted=not reasons,
        reason_codes=tuple(dict.fromkeys(reasons)),
        confidence=confidence,
        entity_kind=entity_kind,
        source_role=source_role,
    )


def enforce_candidate_quality(candidate: Any) -> QualityDecision:
    decision = assess_candidate(candidate)

    if not decision.accepted:
        reasons = ",".join(decision.reason_codes)
        raise CandidateQualityError(
            f"candidate quality rejected: {reasons}"
        )

    return decision
