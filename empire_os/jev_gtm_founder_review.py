"""Founder-facing no-PII review projection for authenticated JEV economic evidence.

Designed for use *inside an existing authorised read-only EmpireDB session*.
No endpoint, new auth path, dashboard writes or live exposure is introduced.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from empire_os.jev_gtm_canonical_economic_bridge import read_jev_canonical_economic_research

ALLOWED = ("revenue_leak", "idle_asset", "market_gap", "idle_waste")


def build_jev_founder_economic_review(
    cursor: Any, *, entity_id: str, as_of: datetime
) -> dict[str, Any]:
    """Return anonymised, read-only insights from the governed canonical source."""
    snapshot = read_jev_canonical_economic_research(cursor, entity_id=entity_id, as_of=as_of)
    counts = Counter(s["signal_type"] for s in snapshot["signals"])
    result = {
        "schema_version": "empire.jev.founder_economic_review.v1",
        "mode": "OBSERVE",
        "signal_count": snapshot["economic_signal_count"],
        "signals_by_type": {key: counts.get(key, 0) for key in ALLOWED},
        "evidence_fingerprint": snapshot["signal_fingerprint"],
        "entity_binding_from_observed_signal": snapshot["entity_binding_from_observed_signal"],
        "source_reader": snapshot["source_reader"],
        "status": (
            "ECONOMIC_EVIDENCE_FOR_RESEARCH" if snapshot["economic_signal_count"] > 0
            else "NO_CANONICAL_ECONOMIC_EVIDENCE"
        ),
        "buyer_conversations_verified": False,
        "verified_revenue": None,
        "contact_clearance_available": False,
        "buying_probability_available": False,
        "next_action": "RESEARCH_REQUIRED",
        "independent_buyer_identity_verified": False,
        "source_authorised_commercial_action": False,
        "founder_review_only": True,
        "contains_contact_data": False,
        "outbound_sent": False,
        "payment_action": False,
        "execution_authority": "none",
    }
    if sum(result["signals_by_type"].values()) != result["signal_count"]:
        raise ValueError("economic signal family projection mismatch")
    return result
