"""Plan the smallest bounded evidence collection needed for v2 qualification.

Planning only: no network, database writes, prospect mutation, or outreach.
Projected gains are upper bounds, not assertions that evidence will be found.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from empire_os.lead_scoring_v2 import (
    MIN_DECISION_CONFIDENCE,
    compute_lead_score_v2,
    is_first_party_website,
)


COMPLETENESS_WEIGHTS = {
    "business_name": 15,
    "email": 15,
    "phone": 15,
    "website": 10,
    "street": 5,
    "city": 5,
    "state": 5,
    "zip": 5,
    "license_no": 10,
    "contact_name": 10,
}


@dataclass(frozen=True)
class EvidenceAction:
    key: str
    capability: str
    target_fields: tuple[str, ...]
    max_completeness_gain: int
    available_now: bool
    bounded: bool
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "capability": self.capability,
            "target_fields": list(self.target_fields),
            "max_completeness_gain": self.max_completeness_gain,
            "available_now": self.available_now,
            "bounded": self.bounded,
            "rationale": self.rationale,
        }


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip() not in ("[]", "{}")
    return bool(value) or value == 0


def _missing_fields(prospect: Mapping[str, Any]) -> list[str]:
    def value_for(field: str) -> Any:
        if field == "street" and not prospect.get("street"):
            return prospect.get("address")
        if field == "website":
            value = prospect.get("website")
            return value if is_first_party_website(value) else None
        return prospect.get(field)

    return [
        field
        for field in COMPLETENESS_WEIGHTS
        if not _present(value_for(field))
    ]


def _gain(
    fields: tuple[str, ...],
    missing: set[str],
) -> int:
    return sum(
        COMPLETENESS_WEIGHTS.get(field, 0)
        for field in fields
        if field in missing
    )


def plan_evidence_enrichment(
    prospect: Mapping[str, Any],
    *,
    target_confidence: float = MIN_DECISION_CONFIDENCE,
) -> dict[str, Any]:
    """Return a deterministic, non-executing evidence acquisition plan."""

    if not 0.0 < float(target_confidence) <= 1.0:
        raise ValueError("target_confidence must be > 0 and <= 1")

    current = compute_lead_score_v2(prospect)
    completeness = int(round(current["data_completeness_score"]))
    missing = set(_missing_fields(prospect))

    actions: list[EvidenceAction] = []

    site_fields = ("website", "email", "phone")
    site_gain = _gain(site_fields, missing)
    if site_gain:
        actions.append(
            EvidenceAction(
                key="first_party_site_probe",
                capability="prospect_enrichment",
                target_fields=tuple(
                    field for field in site_fields if field in missing
                ),
                max_completeness_gain=site_gain,
                available_now=True,
                bounded=True,
                rationale=(
                    "Existing Search Fabric + first-party site probe can "
                    "discover/verify these fields without mutating the prospect."
                ),
            )
        )

    contact_gain = _gain(("contact_name",), missing)
    if contact_gain:
        actions.append(
            EvidenceAction(
                key="decision_maker_evidence",
                capability="future_identity_people_adapter",
                target_fields=("contact_name",),
                max_completeness_gain=contact_gain,
                available_now=False,
                bounded=True,
                rationale=(
                    "A named decision maker needs direct public or licensed "
                    "evidence; the current site probe does not infer people."
                ),
            )
        )

    registry_fields = tuple(
        field
        for field in ("license_no", "street", "city", "state", "zip")
        if field in missing
    )
    registry_gain = _gain(registry_fields, missing)
    if registry_gain:
        actions.append(
            EvidenceAction(
                key="registry_evidence",
                capability="future_public_registry_adapter",
                target_fields=registry_fields,
                max_completeness_gain=registry_gain,
                available_now=False,
                bounded=True,
                rationale=(
                    "Registry/licensing evidence may close structured address "
                    "or licence gaps; no generic verified adapter is active yet."
                ),
            )
        )

    # Prefer executable bounded actions, then largest possible completeness gain.
    actions.sort(
        key=lambda item: (
            not item.available_now,
            -item.max_completeness_gain,
            item.key,
        )
    )

    required_completeness = int(round(target_confidence * 100))
    gap = max(0, required_completeness - completeness)

    selected: list[EvidenceAction] = []
    projected_completeness = completeness
    for action in actions:
        if projected_completeness >= required_completeness:
            break
        if not action.available_now:
            continue
        selected.append(action)
        projected_completeness = min(
            100,
            projected_completeness + action.max_completeness_gain,
        )

    # This is an upper bound only. v2 evidence coverage is at least 0.50 when
    # market_fit is observable from canonical business name/niche.
    market_fit_observable = bool(
        prospect.get("niche") or prospect.get("business_name")
    )
    current_coverage = current["evidence_coverage"]
    projected_coverage = max(
        current_coverage,
        0.50 if market_fit_observable else current_coverage,
    )
    if selected:
        projected_coverage = max(projected_coverage, 0.75)

    projected_confidence_upper_bound = round(
        min(projected_completeness / 100.0, projected_coverage),
        4,
    )

    return {
        "schema_version": "evidence_enrichment_plan.v1",
        "read_only": True,
        "target_confidence": float(target_confidence),
        "current_completeness": completeness,
        "current_evidence_confidence": current["evidence_confidence"],
        "current_decision_tier": current["decision_tier"],
        "completeness_gap": gap,
        "missing_fields": sorted(missing),
        "selected_actions": [
            action.as_dict() for action in selected
        ],
        "all_candidate_actions": [
            action.as_dict() for action in actions
        ],
        "projected_completeness_upper_bound": projected_completeness,
        "projected_confidence_upper_bound": (
            projected_confidence_upper_bound
        ),
        "can_reach_target_with_available_actions": (
            projected_confidence_upper_bound >= target_confidence
        ),
        "projection_is_not_observation": True,
    }
