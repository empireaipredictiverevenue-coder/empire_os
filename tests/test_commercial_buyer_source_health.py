"""Original buyer-capacity and first-party source health: no invented buyers."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from empire_os.commercial_buyer_source_health import (
    evaluate_buyer_source_health, inspect_original_buyer_health,
)

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
CLOCK = "2026-10-20T11:40:00+00:00"


def fixtures():
    capacity = {
        "schema_version": "empire.buyer_capacity_readiness.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "observed_at": CLOCK,
        "allocation_executed": False,
        "payment_action": False,
        "revenue_recognition": False,
        "buyers_seen": 1023,
        "terms_verified": 0,
        "capacity_verified": 0,
        "delivery_verified": 0,
        "fully_activated": 0,
        "contact_email": "private@example.invalid",
    }
    quality = {
        "schema_version": "empire.buyer_evidence_quality.v1",
        "mode": "OBSERVE",
        "commercial_authority": "none",
        "outbound_sent": False,
        "database_write_performed": False,
        "generated_at": CLOCK,
        "scout_candidate_count": 7,
        "candidate_with_valid_direct_purchase_receipt": 2,
        "unsupported_positive_direct_buyer_flags": 1,
        "company_name": "PRIVATE Customer Ltd",
    }
    return capacity, quality


def test_real_source_counts_remain_different_denominators_and_private():
    buyer, scout = fixtures()
    old = (deepcopy(buyer), deepcopy(scout))
    report = evaluate_buyer_source_health(buyer, scout, now=NOW)
    assert (buyer, scout) == old
    assert report["status"] == "BUYER_CONTRACT_CAPACITY_EVIDENCE_HOLD"
    assert report["buyer_capacity_records_seen_not_verified_purchasers"] == 1023
    assert report["first_party_purchase_claim_receipts_not_contracts"] == 2
    assert report["missing_verified_terms_for_any_capacity_record"] is True
    assert report["verified_purchase_events_claimed_by_this_report"] is None
    assert report["realized_revenue_cents_claimed_by_this_report"] is None
    assert report["outbound_authorized"] is False
    assert "private@" not in str(report)
    assert "PRIVATE Customer" not in str(report)


def test_even_owner_activation_count_is_not_payment_proof():
    buyer, scout = fixtures()
    buyer.update(
        fully_activated=3, capacity_verified=3,
        terms_verified=3, delivery_verified=3,
    )
    report = evaluate_buyer_source_health(buyer, scout, now=NOW)
    assert report["owner_fully_activated_count_not_independent_payment_proof"] == 3
    assert report["missing_verified_terms_for_any_capacity_record"] is False
    assert report["verified_purchase_events_claimed_by_this_report"] is None
    assert report["payments_executed"] is False


def test_stale_or_future_owner_snapshots_not_fresh_claims():
    buyer, scout = fixtures()
    buyer["observed_at"] = "2026-10-11T00:00:00+00:00"
    r = evaluate_buyer_source_health(buyer, scout, now=NOW)
    assert r["status"] == "ORIGINAL_BUYER_SOURCE_REVIEW_REQUIRED"
    assert r["source_owner_freshness"]["buyer_capacity_owner"] == "STALE"
    buyer, scout = fixtures()
    scout["generated_at"] = "2026-10-25T12:00:00+00:00"
    r = evaluate_buyer_source_health(buyer, scout, now=NOW)
    assert r["source_owner_freshness"]["buyer_scout_evidence_owner"] == "FUTURE"


@pytest.mark.parametrize("changed", [
    ("capacity", "schema_version", "fake"),
    ("capacity", "payment_action", True),
    ("capacity", "allocation_executed", True),
    ("quality", "outbound_sent", True),
    ("quality", "commercial_authority", "send"),
    ("quality", "candidate_with_valid_direct_purchase_receipt", 8),
    ("capacity", "terms_verified", 999999),
])
def test_source_spoofing_or_contradiction_rejected(changed):
    buyer, scout = fixtures()
    src, key, value = changed
    (buyer if src == "capacity" else scout)[key] = value
    with pytest.raises(ValueError):
        evaluate_buyer_source_health(buyer, scout, now=NOW)


def test_missing_or_broken_source_is_explicit_unknown_not_zero(tmp_path):
    r = inspect_original_buyer_health(tmp_path, now=NOW)
    assert r["status"] == "ORIGINAL_BUYER_SOURCE_UNAVAILABLE"
    assert r["verified_purchase_events_claimed_by_this_report"] is None
    buyer, scout = fixtures()
    p = tmp_path / "runtime/buyer_capacity_readiness/latest.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(buyer))
    other = tmp_path / "runtime/buyer_acquisition/evidence_quality_latest.json"
    other.parent.mkdir(parents=True)
    other.write_text("{bad json")
    r = inspect_original_buyer_health(tmp_path, now=NOW)
    assert r["status"] == "ORIGINAL_BUYER_SOURCE_UNAVAILABLE"


def test_original_file_reads_never_modify_source(tmp_path):
    buyer, scout = fixtures()
    paths = [
        (tmp_path / "runtime/buyer_capacity_readiness/latest.json", buyer),
        (tmp_path / "runtime/buyer_acquisition/evidence_quality_latest.json", scout),
    ]
    for path, obj in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj))
    originals = [p.read_bytes() for p, _ in paths]
    out = inspect_original_buyer_health(tmp_path, now=NOW)
    assert out["status"] == "BUYER_CONTRACT_CAPACITY_EVIDENCE_HOLD"
    assert originals == [p.read_bytes() for p, _ in paths]


def test_owner_snapshot_transitions_are_deduplicated_not_transactions():
    from empire_os.commercial_buyer_source_health import review_buyer_evidence_transition
    buyer, scout = fixtures()
    first = evaluate_buyer_source_health(buyer, scout, now=NOW)
    baseline = review_buyer_evidence_transition(None, first)
    assert baseline["status"] == "INITIAL_BUYER_EVIDENCE_BASELINE"
    same = review_buyer_evidence_transition(first, first)
    assert same["status"] == "UNCHANGED_ORIGINAL_BUYER_EVIDENCE_HOLD"
    assert same["repeated_owner_attention_suppressed"] is True
    buyer["capacity_verified"] = 1
    revised = evaluate_buyer_source_health(buyer, scout, now=NOW)
    change = review_buyer_evidence_transition(first, revised)
    assert change["status"] == "OWNER_COHORT_COUNTERS_CHANGED_REQUIRE_VERIFICATION"
    assert change["owner_claim_counter_deltas_not_transactions"]["owner_capacity_verified_claim_count"] == 1
    assert change["verified_new_buyer_purchases"] is None
    assert change["money_received_cents"] is None
    assert change["task_dispatched"] is False


def test_previous_owner_snapshot_can_not_inject_contact_or_commercial_authority():
    from empire_os.commercial_buyer_source_health import review_buyer_evidence_transition
    buyer, scout = fixtures()
    original = evaluate_buyer_source_health(buyer, scout, now=NOW)
    forged = dict(original)
    forged["owner_terms_verified_claim_count"] = "private@example.invalid"
    forged["outbound_authorized"] = True
    reviewed = review_buyer_evidence_transition(forged, original)
    assert reviewed["status"] == "INITIAL_BUYER_EVIDENCE_BASELINE"
    assert "private@" not in str(reviewed)
    assert reviewed["outbound_authorized"] is False
