"""Deterministic Search Evidence Fabric classification and promotion planning."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

SUPPORTED = {
    "competitor_search_presence": "competitor_serp_presence",
    "ai_citation_observation": "ai_citation",
    "backlink_observation": "backlink",
    "indexation_observation": "indexation",
    "search_revenue_attribution": "revenue_attribution",
}
DESTINATIONS = {
    "ai_citation": "seo_ai_visibility_observations",
    "backlink": "seo_backlink_observations",
    "indexation": "seo_indexation",
    "revenue_attribution": "seo_revenue_attribution",
}

@dataclass(frozen=True)
class SearchEvidencePlan:
    evidence_id: str
    signal_type: str
    evidence_class: str
    observed_at: str
    provenance: tuple[str, ...]
    quality_gate: str | None
    confidence: float | None
    destination: str | None
    promotion_ready: bool
    blockers: tuple[str, ...]
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _valid_time(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None
    except (TypeError, ValueError):
        return False


def plan_search_evidence(signal: Mapping[str, Any]) -> SearchEvidencePlan:
    signal_type = str(signal.get("signal_type") or "").strip()
    evidence_class = SUPPORTED.get(signal_type, "unknown")
    observed_at = str(signal.get("observed_at") or "").strip()
    payload = signal.get("payload") if isinstance(signal.get("payload"), Mapping) else {}
    blockers: list[str] = []
    if evidence_class == "unknown": blockers.append("unsupported_signal_type")
    if not _valid_time(observed_at): blockers.append("valid_point_in_time_required")
    try:
        confidence = float(signal["confidence"]) if signal.get("confidence") is not None else None
    except (TypeError, ValueError):
        confidence = None; blockers.append("valid_confidence_required")
    if confidence is not None and not 0 <= confidence <= 1: blockers.append("valid_confidence_required")

    observations = payload.get("observations") if isinstance(payload, Mapping) else None
    provenance: set[str] = set()
    quality_gates: set[str] = set()
    if isinstance(observations, list):
        for row in observations:
            if not isinstance(row, Mapping): continue
            prov = row.get("provenance")
            if isinstance(prov, Mapping):
                source = str(prov.get("source") or "").strip()
                gate = str(prov.get("quality_gate") or "").strip()
                if source: provenance.add(source)
                if gate: quality_gates.add(gate)
            elif isinstance(prov, (list, tuple)):
                provenance.update(str(x).strip() for x in prov if str(x).strip())
    direct = signal.get("provenance")
    if isinstance(direct, (list, tuple)):
        provenance.update(str(x).strip() for x in direct if str(x).strip())
    if not provenance: blockers.append("provenance_required")
    if len(quality_gates) > 1: blockers.append("ambiguous_quality_gate")
    quality_gate = next(iter(quality_gates), None)

    destination = DESTINATIONS.get(evidence_class)
    if evidence_class == "competitor_serp_presence":
        # Preserve as observed competitor evidence; no canonical SEO table currently
        # represents generic competitor SERP rows without changing their meaning.
        blockers.append("canonical_competitor_serp_destination_required")
    if destination is None and evidence_class != "unknown" and not blockers:
        blockers.append("canonical_destination_required")

    identity = {
        "signal_type": signal_type,
        "entity_id": str(signal.get("entity_id") or ""),
        "observed_at": observed_at,
        "payload": payload,
    }
    return SearchEvidencePlan(
        evidence_id=_canonical_hash(identity), signal_type=signal_type,
        evidence_class=evidence_class, observed_at=observed_at,
        provenance=tuple(sorted(provenance)), quality_gate=quality_gate,
        confidence=confidence, destination=destination,
        promotion_ready=not blockers and destination is not None,
        blockers=tuple(dict.fromkeys(blockers)),
    )
