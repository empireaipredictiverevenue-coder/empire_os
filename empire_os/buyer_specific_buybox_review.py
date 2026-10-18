"""Private, read-only candidate review over the existing EmpireDB buyer projection.

Same-record identity, market, terms, capacity and delivery gaps are reported.
The projected buyer fields cannot prove signed buyer-specific buy-box terms,
postcode eligibility, current acceptance, price consent or settlement.
Never elevate this review to lead allocation, quoting, outreach or payment.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Iterable, Mapping

from empire_os.buyer_allocation import buyer_activation_decision, buyer_identity_quality_hold

SCHEMA_VERSION = "empire.predictive_revenue.buyer_buybox_candidate_review.v1"
MAX_INPUT = 10000
MAX_OUTPUT = 15
MAX_TEXT = 160
STEPS = (
    ("buyer_identity", "VERIFY_BUYER_IDENTITY"),
    ("buyer_review", "VERIFY_AUTHORITATIVE_BUYER_REVIEW"),
    ("market", "VERIFY_BUYER_MARKET_AND_POSTCODE"),
    ("configured_capacity", "VERIFY_BUYER_CAP_AND_VOLUME"),
    ("capacity_evidence", "VERIFY_BUYER_CAPACITY_AGREEMENT"),
    ("terms_evidence", "VERIFY_BUYER_PRICING_AND_TERMS"),
    ("delivery_destination", "VERIFY_BUYER_DESTINATION"),
    ("delivery_evidence", "VERIFY_ACCEPTANCE_AND_DELIVERY"),
    ("activation", "VERIFY_BUYER_ACTIVATION"),
)
# Checklist progress is a triage aid, never predictive confidence or eligibility.
PRIORITY_WEIGHT = {
    "buyer_identity": 2,
    "buyer_review": 6,
    "market": 3,
    "configured_capacity": 2,
    "capacity_evidence": 5,
    "terms_evidence": 5,
    "delivery_destination": 2,
    "delivery_evidence": 4,
    "activation": 3,
}


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _stamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 60:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp.astimezone(timezone.utc) if stamp.tzinfo is not None else None


def _past_date(value: Any, *, now: datetime) -> bool:
    stamp = _stamp(value)
    return stamp is not None and stamp <= now


def _positive_configured_cap(value: Any) -> bool:
    return type(value) is int and 0 < value <= 1_000_000


def _delivery_configured(row: Mapping[str, Any]) -> bool:
    return bool(_text(row.get("destination_phone")) or _text(row.get("webhook_url")))


def review_single_buyer(
    row: Mapping[str, Any],
    *,
    as_of: datetime,
) -> dict[str, Any] | None:
    """No contacts or raw contract identifiers appear in this candidate record."""
    if not isinstance(row, Mapping):
        return None
    if buyer_identity_quality_hold(dict(row)):
        return None
    raw_id = _text(row.get("id"), 200)
    if not raw_id:
        return None

    checked = {
        "buyer_identity": bool(_text(row.get("buyer_name"))),
        "buyer_review": _past_date(row.get("reviewed_at"), now=as_of),
        "market": bool(_text(row.get("niche"))) and bool(_text(row.get("metro"))),
        "configured_capacity": _positive_configured_cap(row.get("daily_cap")),
        "capacity_evidence": _past_date(row.get("capacity_verified_at"), now=as_of),
        "terms_evidence": (
            bool(_text(row.get("commercial_terms_source")))
            and bool(_text(row.get("commercial_terms_reference")))
            and _past_date(row.get("commercial_terms_verified_at"), now=as_of)
        ),
        "delivery_destination": _delivery_configured(row),
        "delivery_evidence": _past_date(row.get("delivery_verified_at"), now=as_of),
        "activation": (
            row.get("is_active") is True
            and _text(row.get("status")).lower() == "active"
            and _text(row.get("commercial_activation_state")).lower() == "activated"
            and _past_date(row.get("commercial_activated_at"), now=as_of)
        ),
    }
    # Existing gate is displayed as a separate configured state; don't weaken
    # it by calling a report "activated" merely because a subset is populated.
    activation_allowed, activation_reason = buyer_activation_decision(dict(row))
    missing = [
        {"evidence_key": key, "next_action": action}
        for key, action in STEPS if not checked[key]
    ]
    ready_count = sum(checked.values())
    rank = sum(PRIORITY_WEIGHT[k] for k, ok in checked.items() if ok)
    return {
        "buyer_ref": "buyerref_" + sha256(raw_id.encode()).hexdigest()[:20],
        "buyer_name": _text(row.get("buyer_name"), 100) or None,
        "market_niche": _text(row.get("niche"), 80) or None,
        "market_metro": _text(row.get("metro"), 80) or None,
        "evidence_stage_count": ready_count,
        "evidence_stage_total": len(STEPS),
        "review_rank": rank,
        "review_rank_is_revenue_probability": False,
        "recorded_evidence": checked,
        "missing_evidence": missing,
        "next_action": missing[0]["next_action"]
                       if missing else "VERIFY_EXACT_BUYBOX_TERMS_AND_RECONTACT",
        "configured_activation_gate_passed": activation_allowed,
        "configured_activation_reason": activation_reason,
        "specific_buybox_verified": False,
        "postcode_and_price_verified": False,
        "buyer_acceptance_verified": False,
        "buyer_can_be_quoted": False,
        "lead_delivery_authorized": False,
        "execution_authority": "none",
    }


def review_buyer_buybox_candidates(
    buyer_rows: Iterable[Mapping[str, Any]],
    *,
    as_of: datetime,
    max_candidates: int = 10,
) -> dict[str, Any]:
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    if type(max_candidates) is not int or not 1 <= max_candidates <= MAX_OUTPUT:
        raise ValueError("max_candidates outside bounded range")
    now = as_of.astimezone(timezone.utc)
    rows: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    observed = 0
    excluded = 0
    for row in buyer_rows:
        observed += 1
        if observed > MAX_INPUT:
            raise ValueError("buyer inventory exceeds review limit; do not report partial results")
        review = review_single_buyer(row, as_of=now)
        if review is None:
            excluded += 1
            continue
        if review["buyer_ref"] in seen_refs:
            raise ValueError("duplicate buyer identity in canonical inventory")
        seen_refs.add(review["buyer_ref"])
        rows.append(review)
    rows.sort(key=lambda row: (
        -row["review_rank"], -row["evidence_stage_count"], row["buyer_ref"],
    ))
    # Never return any of the raw endpoint, name/contact details beyond the
    # organisation name already projected in the source buyer table.
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "status": "CANDIDATE_REVIEW_READY" if rows else "NO_REAL_BUYER_CANDIDATES",
        "source": "existing_empiredb_buyer_projection",
        "mode": "OBSERVE",
        "buyers_observed": observed,
        "excluded_identity_count": excluded,
        "candidate_count": len(rows),
        "returned_count": min(len(rows), max_candidates),
        "truncated_count": max(0, len(rows) - max_candidates),
        "candidates": rows[:max_candidates],
        "specific_verified_buybox_count": None,
        "actual_payer_count": None,
        "lead_delivery_authorized": False,
        "buyer_activation_performed": False,
        "database_writes": False,
        "outbound_sent": False,
        "revenue_recognized": False,
        "execution_authority": "none",
    }
