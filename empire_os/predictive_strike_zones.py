"""Pure OBSERVE projection of evidenced Predictive Revenue strike candidates.

Callers supply already joined, current owner projections for one opportunity
or market per row. ``opportunity_key`` is the stable identity (including for
markets); ``decay_state`` comes from commercial Opportunity Decay, and
``buyer_capacity_remaining`` / ``buyer_capacity_evidence_ref`` from buyer capacity.
EV requires ``expected_revenue_value_cents`` and ``erv_evidence_ref``;
``evidence_refs`` identifies the observed market/opportunity evidence.

This module does no fetching, persistence, temporal reassessment, EV calculation,
or capacity verification. Evidence references are provenance supplied by owners,
not proof independently verified here. It never grants execution authority.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
from typing import Any, Iterable, Mapping


def _text(value: Any) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not isfinite(value):
        return None
    return value


def _authority() -> dict[str, Any]:
    return {
        "mode": "OBSERVE",
        "recommendation_only": True,
        "actual_revenue": False,
        "execution_authority": "none",
        "crawler_execution": False,
        "outbound": False,
        "ad_spend": False,
        "allocation": False,
        "revenue_recognition": False,
    }


def project_predictive_strike_zones(
    opportunities: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rank eligible rows by explicit EV descending, then stable identity.

    All copies of a duplicate identity are BLOCKED. Known disqualifications
    take precedence over UNKNOWN, with every missing/invalid gate retained in
    blockers. Only STRIKE_CANDIDATE rows receive a rank. Extra input fields
    (including price, scores and authority flags) cannot affect the projection.
    """
    inputs = list(opportunities)
    identities = Counter(_text(row.get("opportunity_key")) for row in inputs)
    rows: list[dict[str, Any]] = []
    for source in inputs:
        key = _text(source.get("opportunity_key"))
        ev = _number(source.get("expected_revenue_value_cents"))
        capacity = _number(source.get("buyer_capacity_remaining"))
        erv_ref = _text(source.get("erv_evidence_ref"))
        capacity_ref = _text(source.get("buyer_capacity_evidence_ref"))
        decay = _text(source.get("decay_state"))
        raw_refs = source.get("evidence_refs")
        refs = sorted({
            ref for value in raw_refs if (ref := _text(value))
        }) if isinstance(raw_refs, (list, tuple, set)) else []
        blockers: list[str] = []
        blocked = False
        if key is None:
            blockers.append("opportunity_key_missing_or_invalid")
        elif identities[key] > 1:
            blockers.append("duplicate_opportunity_key")
            blocked = True
        if not refs:
            blockers.append("evidence_refs_missing")
        if ev is None:
            blockers.append("expected_revenue_value_cents_missing_or_invalid")
        elif ev <= 0:
            blockers.append("expected_revenue_value_not_positive")
            blocked = True
        if erv_ref is None:
            blockers.append("erv_evidence_ref_missing")
        if decay in {"STALE", "EXPIRED"}:
            blockers.append("decay_" + decay.lower())
            blocked = True
        elif decay != "ACTIVE":
            blockers.append("decay_unknown")
        if capacity is None:
            blockers.append("buyer_capacity_remaining_missing_or_invalid")
        elif capacity <= 0:
            blockers.append("buyer_capacity_not_positive")
            blocked = True
        if capacity_ref is None:
            blockers.append("buyer_capacity_evidence_ref_missing")
        rows.append({
            "opportunity_key": key,
            "status": (
                "BLOCKED" if blocked else "UNKNOWN" if blockers
                else "STRIKE_CANDIDATE"
            ),
            "rank": None,
            "expected_revenue_value_cents": ev,
            "erv_evidence_ref": erv_ref,
            "decay_state": decay if decay in {
                "ACTIVE", "STALE", "EXPIRED"
            } else "UNKNOWN",
            "buyer_capacity_remaining": capacity,
            "buyer_capacity_evidence_ref": capacity_ref,
            "evidence_refs": refs,
            "blockers": blockers,
            **_authority(),
        })
    ranked = sorted(
        (row for row in rows if row["status"] == "STRIKE_CANDIDATE"),
        key=lambda row: (-row["expected_revenue_value_cents"], row["opportunity_key"]),
    )
    for rank, row in enumerate(ranked, start=1):
        row["rank"] = rank
    return {
        "schema_version": "empire.predictive_strike_zones.v1",
        "ranking_basis": "expected_revenue_value_cents",
        "rows": rows,
        "ranked_candidates": ranked,
        **_authority(),
    }
