"""Empire v49 USB matcher counterfactual, isolated from ALL dispatch paths.

Formula and legacy eligibility transcribed from the supplied 2026-10-19
v49 shadow pack. The legacy model is a rank heuristic, not a probability.
Research gates are only asserted fixture booleans; no authentication of
licences, users, source rights, buyer capacity or payment is performed.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
from typing import Any, Mapping, Sequence

SCHEMA = "empire.flagship.legacy_v49_matching_counterfactual.v1"
WEIGHTS = (0.40, 0.25, 0.15, 0.10, 0.10)
REQUIRED_RESEARCH_FLAGS = (
    "territory_verified", "specialty_verified", "license_verified",
    "capacity_verified", "source_rights_verified", "trust_score_verified",
    "dispatch_history_verified",
)
MAX_ROWS = 100


def _numeric(value: Any, field: str, low: float, high: float) -> float:
    if type(value) not in (int, float) or not isfinite(value) or not low <= value <= high:
        raise ValueError("unsupported original numeric field: " + field)
    return float(value)


def _terms(value: Any, field: str) -> set[str]:
    if not isinstance(value, (list, tuple)) or len(value) > 30:
        raise ValueError("unbounded terms: " + field)
    if any(not isinstance(x, str) or not 1 <= len(x) <= 70 for x in value):
        raise ValueError("untrusted terms: " + field)
    terms = {x.strip().casefold() for x in value}
    if "" in terms:
        raise ValueError("empty terms: " + field)
    return terms


def review_v49_matching_counterfactual(
    *, lead: Mapping[str, Any], contractor_fixtures: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Pure source-compatibility review. Never returns candidate or tenant IDs."""
    if not isinstance(lead, Mapping):
        raise ValueError("lead must be a bounded mapping")
    tenant = lead.get("tenant_id")
    metro = lead.get("metro")
    if (not isinstance(tenant, str) or not 1 <= len(tenant) <= 128
            or not tenant.strip() or not isinstance(metro, str)
            or not 1 <= len(metro) <= 100 or not metro.strip()):
        raise ValueError("bounded historical lead tenant and market required")
    specialties = _terms(lead.get("specialties"), "lead specialties")
    approved_adjacent = _terms(lead.get("approved_adjacent_metros", []), "approved adjacent metros")
    if not specialties:
        raise ValueError("original trade required")
    if not isinstance(contractor_fixtures, (list, tuple)) or len(contractor_fixtures) > MAX_ROWS:
        raise ValueError("bounded fixture batch required")

    counts: Counter[str] = Counter()
    legacy_scores: list[float] = []
    research_scores: list[float] = []
    for candidate in contractor_fixtures:
        if not isinstance(candidate, Mapping) or type(candidate.get("active")) is not bool:
            raise ValueError("untrusted historical contractor state")
        area = candidate.get("metro", "")
        if not isinstance(area, str) or len(area) > 100:
            raise ValueError("untrusted contractor metro")
        found = _terms(candidate.get("specialties", []), "contractor specialties")
        metro_score = (
            1.0 if area.strip().casefold() == metro.strip().casefold()
            else 0.5 if area.strip().casefold() in approved_adjacent else 0.0
        )
        trade_score = len(specialties & found) / len(specialties | found) if found else 0.0
        raw_trust = candidate.get("trust_score")
        trust = _numeric(raw_trust, "trust_score", 0, 10) if raw_trust is not None else 0.0
        # Legacy trust-or-five incorrectly awards midpoint to explicit zero and missing.
        historical_trust = (trust or 5.0) / 10.0
        days = candidate.get("days_since_dispatch")
        rotation = (1.0 if days is None else
                    min(1.0, _numeric(days, "days_since_dispatch", 0, 50000) / 14.0))
        load = _numeric(candidate.get("active_dispatches"), "active_dispatches", 0, 100000)
        capacity = _numeric(candidate.get("max_concurrent", 3), "max_concurrent", 1, 100000)
        spare = max(0.0, 1.0 - load / capacity)
        score = round(sum(w*v for w, v in zip(
            WEIGHTS, (metro_score, trade_score, historical_trust, rotation, spare),
        )), 3)
        legacy = candidate["active"] and load < capacity and (metro_score > 0 or trade_score > 0)
        if legacy:
            counts["legacy_ranked"] += 1
            legacy_scores.append(score)
            if metro_score == 0:
                counts["legacy_wrong_geography"] += 1
            if trade_score == 0:
                counts["legacy_wrong_trade"] += 1
            if raw_trust is None or days is None:
                counts["legacy_unknown_data_bonus"] += 1
            if raw_trust == 0:
                counts["legacy_explicit_zero_trust_bonus"] += 1

        blockers = set()
        if not candidate["active"]:
            blockers.add("inactive")
        if candidate.get("tenant_id") != tenant:
            blockers.add("tenant_scope")
        if metro_score <= 0:
            blockers.add("geography")
        if trade_score <= 0:
            blockers.add("specialty")
        if load >= capacity:
            blockers.add("capacity_exhausted")
        if raw_trust is None or days is None:
            blockers.add("unknown_trust_or_dispatch_history")
        if candidate.get("suppressed") is not False:
            blockers.add("suppression_unknown_or_present")
        for gate in REQUIRED_RESEARCH_FLAGS:
            if candidate.get(gate) is not True:
                blockers.add(gate)
        if blockers:
            counts["evidence_held"] += 1
            for blocker in blockers:
                counts["hold_" + blocker] += 1
        else:
            counts["fixture_research_eligible"] += 1
            research_scores.append(score)

    return {
        "schema_version": SCHEMA,
        "mode": "OFFLINE_SHADOW_ONLY",
        "source": "user_supplied_v49_shadow_pack_20261019",
        "v49_weights": dict(zip(
            ("metro", "specialty_jaccard", "trust", "dispatch_rotation", "capacity"),
            WEIGHTS,
        )),
        "tested_synthetic_count": len(contractor_fixtures),
        "legacy_ranked_count": counts["legacy_ranked"],
        "legacy_wrong_geography_count": counts["legacy_wrong_geography"],
        "legacy_wrong_specialty_count": counts["legacy_wrong_trade"],
        "legacy_unknown_data_bonus_count": counts["legacy_unknown_data_bonus"],
        "legacy_zero_trust_bonus_count": counts["legacy_explicit_zero_trust_bonus"],
        "fixture_research_eligible_count": counts["fixture_research_eligible"],
        "evidence_hold_count": counts["evidence_held"],
        "evidence_hold_reason_counts": {
            k[5:]: value for k, value in sorted(counts.items()) if k.startswith("hold_")
        },
        "historical_mean_rank_score": (
            round(sum(legacy_scores)/len(legacy_scores), 3) if legacy_scores else None
        ),
        "fixture_mean_research_score": (
            round(sum(research_scores)/len(research_scores), 3) if research_scores else None
        ),
        "historical_score_is_calibrated_conversion_probability": False,
        "supplied_evidence_flags_independently_authenticated": False,
        "verified_buyer_capacity": False,
        "real_world_matching_accuracy_measured": False,
        "training_eligible": False,
        "commercial_allocations_authorized": False,
        "outbound_authorized": False,
        "production_empiredb_accessed": False,
        "external_calls": 0,
        "database_writes": False,
        "funds_moved": False,
        "execution_authority": "none",
    }
