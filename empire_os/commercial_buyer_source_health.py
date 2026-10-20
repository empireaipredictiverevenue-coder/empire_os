"""First-party buyer-capacity evidence health for existing adaptive Ops.

Consumes only the original Buyer Capacity and Buyer Scout evidence owners'
read-only snapshots. A webpage purchase claim is NOT buyer capacity, accepted
terms, settled orders, delivery, replies or customer spend authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any, Mapping

SCHEMA = "empire.commercial.original_buyer_evidence_health.v1"
CAPACITY_SCHEMA = "empire.buyer_capacity_readiness.v1"
QUALITY_SCHEMA = "empire.buyer_evidence_quality.v1"
CAPACITY_FILE = "runtime/buyer_capacity_readiness/latest.json"
QUALITY_FILE = "runtime/buyer_acquisition/evidence_quality_latest.json"
MAX_BYTES = 300_000
MAX_AGE_HOURS = 24


def _count(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= 2_000_000:
        raise ValueError("bounded original owner evidence count required")
    return value


def _source_age(raw: Any, now: datetime) -> tuple[str, int | None]:
    if not isinstance(raw, str) or len(raw) > 90:
        return "INVALID", None
    try:
        at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if at.utcoffset() is None:
            raise ValueError("timezone missing")
        seconds = (now - at.astimezone(timezone.utc)).total_seconds()
        if seconds < -300:
            return "FUTURE", None
        return ("STALE" if seconds > MAX_AGE_HOURS * 3600 else "FRESH",
                max(0, int(seconds // 3600)))
    except (ValueError, OverflowError, TypeError):
        return "INVALID", None


def evaluate_buyer_source_health(
    capacity: Mapping[str, Any],
    quality: Mapping[str, Any],
    *, now: datetime,
) -> dict[str, Any]:
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("timezone-aware original buyer review required")
    clock = now.astimezone(timezone.utc)
    if (
        not isinstance(capacity, Mapping)
        or capacity.get("schema_version") != CAPACITY_SCHEMA
        or capacity.get("mode") != "OBSERVE"
        or capacity.get("execution_authority") != "none"
        or capacity.get("allocation_executed") is not False
        or capacity.get("payment_action") is not False
        or capacity.get("revenue_recognition") is not False
    ):
        raise ValueError("trusted nonexecuting buyer capacity snapshot required")
    if (
        not isinstance(quality, Mapping)
        or quality.get("schema_version") != QUALITY_SCHEMA
        or quality.get("mode") != "OBSERVE"
        or quality.get("commercial_authority") != "none"
        or quality.get("outbound_sent") is not False
        or quality.get("database_write_performed") is not False
    ):
        raise ValueError("trusted nonexecuting buyer source quality snapshot required")
    fields = ("buyers_seen", "capacity_verified", "terms_verified",
              "delivery_verified", "fully_activated")
    buyer_counts = {name: _count(capacity.get(name)) for name in fields}
    n = buyer_counts["buyers_seen"]
    if any(buyer_counts[k] > n for k in fields[1:]):
        raise ValueError("original buyer capacity count contradiction")
    quality_claims = _count(quality.get("candidate_with_valid_direct_purchase_receipt"))
    unsupported = _count(quality.get("unsupported_positive_direct_buyer_flags"))
    scout_count = _count(quality.get("scout_candidate_count"))
    if quality_claims > scout_count or unsupported > scout_count:
        raise ValueError("first-party Scout claim count contradiction")
    t1, h1 = _source_age(capacity.get("observed_at"), clock)
    t2, h2 = _source_age(quality.get("generated_at"), clock)
    freshness = {"buyer_capacity_owner": t1, "buyer_scout_evidence_owner": t2}
    stale = any(x != "FRESH" for x in freshness.values())
    return {
        "schema_version": SCHEMA,
        "status": (
            "ORIGINAL_BUYER_SOURCE_REVIEW_REQUIRED" if stale else
            "BUYER_CONTRACT_CAPACITY_EVIDENCE_HOLD"
        ),
        "mode": "OBSERVE",
        "source_owner_freshness": freshness,
        "source_owner_age_hours_floor": {
            "buyer_capacity_owner": h1,
            "buyer_scout_evidence_owner": h2,
        },
        "buyer_capacity_records_seen_not_verified_purchasers": n,
        "owner_capacity_verified_claim_count": buyer_counts["capacity_verified"],
        "owner_terms_verified_claim_count": buyer_counts["terms_verified"],
        "owner_delivery_verified_claim_count": buyer_counts["delivery_verified"],
        "owner_fully_activated_count_not_independent_payment_proof": buyer_counts["fully_activated"],
        "scout_candidate_count_separate_cohort": scout_count,
        "first_party_purchase_claim_receipts_not_contracts": quality_claims,
        "unsupported_direct_purchase_claim_flags": unsupported,
        "missing_verified_terms_for_any_capacity_record": buyer_counts["terms_verified"] == 0,
        "missing_verified_capacity_for_any_capacity_record": buyer_counts["capacity_verified"] == 0,
        "proof_required_from_existing_owner": [
            "ORIGINAL_TENANT_SCOPED_COUNTERPARTY_IDENTITY",
            "ACCEPTED_COMMERCIAL_BUY_BOX_AND_TERMS",
            "VERIFIED_BUYER_CAPACITY_AND_DELIVERY_DESTINATION",
            "EXACT_CANONICAL_ORDER_AND_PAYMENT_PROVENANCE_FOR_OUTCOMES",
        ],
        "verified_purchase_events_claimed_by_this_report": None,
        "realized_revenue_cents_claimed_by_this_report": None,
        "no_cross_source_person_or_company_matching": True,
        "no_buyer_activation_from_page_receipt": True,
        "outbound_authorized": False,
        "database_writes": False,
        "payments_executed": False,
        "agent_tasks_created": False,
        "execution_authority": "none",
    }


def _bounded_owner_file(root: Path, relative: str):
    p = root / relative
    if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_BYTES:
        raise ValueError("bounded owner source unavailable")
    record = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError("original owner record required")
    return record


def inspect_original_buyer_health(root: Path, *, now: datetime) -> dict[str, Any]:
    try:
        return evaluate_buyer_source_health(
            _bounded_owner_file(root, CAPACITY_FILE),
            _bounded_owner_file(root, QUALITY_FILE),
            now=now,
        )
    except (ValueError, TypeError, OSError, json.JSONDecodeError, OverflowError):
        return {
            "schema_version": SCHEMA,
            "status": "ORIGINAL_BUYER_SOURCE_UNAVAILABLE",
            "mode": "OBSERVE",
            "proof_required_from_existing_owner": [
                "ORIGINAL_BUYER_CAPACITY_AND_EVIDENCE_SNAPSHOTS"
            ],
            "verified_purchase_events_claimed_by_this_report": None,
            "realized_revenue_cents_claimed_by_this_report": None,
            "outbound_authorized": False,
            "database_writes": False,
            "payments_executed": False,
            "agent_tasks_created": False,
            "execution_authority": "none",
        }


_CHANGE_FIELDS = (
    "buyer_capacity_records_seen_not_verified_purchasers",
    "owner_capacity_verified_claim_count",
    "owner_terms_verified_claim_count",
    "owner_delivery_verified_claim_count",
    "owner_fully_activated_count_not_independent_payment_proof",
    "scout_candidate_count_separate_cohort",
    "first_party_purchase_claim_receipts_not_contracts",
    "unsupported_direct_purchase_claim_flags",
)


def review_buyer_evidence_transition(
    previous: Mapping[str, Any] | None, current: Mapping[str, Any]
) -> dict[str, Any]:
    """Existing Ops snapshot memory: compare owner claims only, no dispatch."""
    valid_current = (
        isinstance(current, Mapping)
        and current.get("schema_version") == SCHEMA
        and current.get("mode") == "OBSERVE"
        and current.get("execution_authority") == "none"
        and current.get("outbound_authorized") is False
        and current.get("database_writes") is False
    )
    if not valid_current:
        raise ValueError("original owner health report required")
    active = current.get("status") == "BUYER_CONTRACT_CAPACITY_EVIDENCE_HOLD"
    prior_ok = (
        isinstance(previous, Mapping)
        and previous.get("schema_version") == SCHEMA
        and previous.get("mode") == "OBSERVE"
        and previous.get("execution_authority") == "none"
        and previous.get("outbound_authorized") is False
        and previous.get("database_writes") is False
        and previous.get("status") == "BUYER_CONTRACT_CAPACITY_EVIDENCE_HOLD"
        and all(type(previous.get(k)) is int and 0 <= previous[k] <= 2_000_000
                for k in _CHANGE_FIELDS)
    )
    if not active:
        state = "SOURCE_UNAVAILABLE_OR_OUTDATED_HOLD"
        delta = {}
    else:
        if any(type(current.get(k)) is not int or current[k] < 0 for k in _CHANGE_FIELDS):
            raise ValueError("bounded current buyer owner counters required")
        delta = {
            k: current[k] - previous[k] for k in _CHANGE_FIELDS
            if prior_ok and current[k] != previous[k]
        }
        state = (
            "INITIAL_BUYER_EVIDENCE_BASELINE" if not prior_ok else
            "OWNER_COHORT_COUNTERS_CHANGED_REQUIRE_VERIFICATION" if delta else
            "UNCHANGED_ORIGINAL_BUYER_EVIDENCE_HOLD"
        )
    return {
        "schema_version": "empire.commercial.buyer_evidence_transition.v1",
        "status": state,
        "owner_claim_counter_deltas_not_transactions": delta,
        "owner_attestation_required_before_commercial_progress": True,
        "repeated_owner_attention_suppressed": not bool(delta) and prior_ok,
        "no_cross_source_identity_linkage": True,
        "verified_new_buyer_purchases": None,
        "new_contracts_signed": None,
        "money_received_cents": None,
        "outbound_authorized": False,
        "task_dispatched": False,
        "execution_authority": "none",
    }
