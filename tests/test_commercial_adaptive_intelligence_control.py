"""Synthetic-only tests for the existing-owner adaptive dependency graph."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json

import pytest

from empire_os.commercial_adaptive_intelligence_control import (
    review_adaptive_commercial_intelligence,
)

NOW = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
STATES = (
    "conversion", "catalog", "radar", "buyer_acquisition", "buyer_scout",
    "buyer_capacity", "exchange", "search", "aeo", "competitor", "crawler",
)


def digest(x):
    return sha256(json.dumps(x, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def fixtures(*, stale=True, suppressed=1, cases=3, activated=0):
    counts = {
        "REVIEW_SUPPRESSION_AND_MISSING_CANONICAL_CONTEXT_NO_OUTREACH": suppressed,
        "REFRESH_ORIGINAL_COMMERCIAL_SOURCE_EVIDENCE_FIRST": cases - suppressed,
    }
    semantic = {"case_count": cases, "action_counts": counts}
    sales = {
        "schema_version": "empire.commercial.sales_director_adaptive_recheck.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "status": "ADAPTIVE_REVIEW_HOLD_NO_COMMERCIAL_AUTHORITY",
        "outbound_authorized": False,
        "agent_tasks_created": False,
        "database_writes": False,
        "case_local_provider_authentication_attested": False,
        "evidence_semantic_state": semantic,
        "evidence_semantic_hash": digest(semantic),
    }
    book = {
        "target_count": 6,
        "offer_ready_count": 0,
        "missing_canonical_prospect_id_count": 5,
        "verified_person_and_email_count": 0,
        "source_claims_verified_buyer_demand_count": 0,
    }
    offers = {
        "schema_version": "empire.commercial_growth.shadow_offer_reconstruction.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "status": "SOURCE_FRESHNESS_HOLD" if stale else "SHADOW_RECONSTRUCTION_ONLY",
        "outbound_authorized": False,
        "agent_tasks_created": False,
        "database_writes": False,
        "payment_execution": False,
        "result_is_shadow_not_current_commercial_authority": True,
        "source_refresh_review_required": stale,
        "historical_offer_book": {"target_count": 4},
        "in_memory_reconstructed_offer_book": book,
        "reconstructed_ready_catalog_product_count": 2,
    }
    source_states = {
        name: "stale" if name in ("search", "competitor") else "available"
        for name in STATES
    }
    distribution = {
        "schema_version": "empire.commercial.shadow_distribution_refresh_review.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "status": "SOURCE_AND_BUYER_EVIDENCE_HOLD",
        "live_outbound_authorized": False,
        "agent_tasks_created": False,
        "snapshot_writes": False,
        "payment_authorized": False,
        "no_current_revenue_or_buyer_evidence_inferred": True,
        "source_count": 11,
        "source_evidence_review_required": True,
        "source_states": source_states,
        "buyer_capacity_source_counts_not_buyer_demand_proof": {
            "buyers_seen": 22,
            "fully_activated": activated,
            "terms_verified": 0,
            "capacity_verified": 0,
        },
    }
    return dict(sales=sales, offers=offers, distribution=distribution,
                previous=None, now=NOW)


def review(p):
    return review_adaptive_commercial_intelligence(**p)


def test_first_review_separates_cohorts_and_prioritises_upstream():
    p = fixtures()
    untouched = deepcopy(p)
    out = review(p)
    assert p == untouched
    assert out["status"] == "COMMERCIAL_DEPENDENCY_EVIDENCE_HOLD"
    assert out["transition"] == "FIRST_COMMERCIAL_INTELLIGENCE_REVIEW"
    assert len(out["active_dependency_gates"]) == 8
    assert out["shadow_offer_targets_not_new_customers"] == 6
    assert out["historical_offer_targets_not_new_customers"] == 4
    assert out["historical_conversations_not_verified_replies"] == 3
    assert out["buyer_capacity_records_seen_not_purchasers"] == 22
    assert out["verified_purchase_or_payment_events"] is None
    assert out["accepted_verified_revenue_cents"] is None
    assert out["outbound_authorized"] is False
    assert out["model_training"] is False
    assert out["agent_tasks_created"] is False


def test_suppressed_subset_does_not_block_other_original_thread_reviews():
    out = review(fixtures(cases=9, suppressed=3))
    rows = {r["gate"]: r for r in out["active_dependency_gates"]}
    assert rows["ORIGINAL_REPLY_AUTHENTICATION"]["parallel_owner_review_possible"] is True
    impact = rows["ORIGINAL_REPLY_AUTHENTICATION"]["review_evidence_impact_not_forecast"]
    assert impact["suppression_or_missing_context_subcohort_not_eligible"] == 3
    assert impact["remaining_non_suppressed_review_cases_not_authenticated"] == 6
    assert rows["CONTACT_AND_PROSPECT_IDENTITY"]["parallel_owner_review_possible"] is False
    assert rows["CONTACT_AND_PROSPECT_IDENTITY"]["upstream_gates_blocking_work"] == ["COMMERCIAL_SOURCE_PROVENANCE"]


def test_all_suppressed_threads_do_not_route_provider_work():
    out = review(fixtures(cases=3, suppressed=3))
    node = next(r for r in out["active_dependency_gates"] if r["gate"] == "ORIGINAL_REPLY_AUTHENTICATION")
    assert node["parallel_owner_review_possible"] is False
    assert node["upstream_gates_blocking_work"] == ["CONTACT_SUPPRESSION"]
    assert "ORIGINAL_REPLY_AUTHENTICATION" not in [
        row["gate"] for row in out["recommended_parallel_reviews_not_dispatched"]
    ]


def test_unchanged_review_notifies_nobody_and_never_activates():
    a = review(fixtures())
    current = fixtures()
    current["previous"] = a
    b = review(current)
    assert b["transition"] == "UNCHANGED_COMMERCIAL_HOLD"
    assert b["recommended_parallel_reviews_not_dispatched"] == []
    assert b["operator_attention_due"] is False
    assert b["deduplicated_if_unchanged"] is True
    assert b["agent_tasks_created"] is False


def test_new_stale_source_is_regression_without_pretending_new_revenue():
    p = fixtures()
    p["distribution"]["source_states"]["search"] = "available"
    old = review(p)
    p["previous"] = old
    p["distribution"]["source_states"]["search"] = "stale"
    new = review(p)
    assert new["transition"] == "PROVENANCE_OR_METRICS_CHANGED_REVIEW_REQUIRED"
    assert new["gates_newly_blocking"] == ["SEARCH_SOURCE_FRESHNESS"]
    assert new["verified_purchase_or_payment_events"] is None
    assert new["outbound_authorized"] is False


def test_resolved_source_hold_does_not_authenticate_buyer():
    p = fixtures()
    old = review(p)
    p["previous"] = old
    p["offers"]["source_refresh_review_required"] = False
    p["offers"]["status"] = "SHADOW_RECONSTRUCTION_ONLY"
    changed = review(p)
    assert "COMMERCIAL_SOURCE_PROVENANCE" in changed["gates_no_longer_reported"]
    assert changed["independently_authenticated_buyers"] is None
    assert changed["accepted_verified_revenue_cents"] is None
    assert changed["economic_model_update"].startswith("BLOCKED")


def test_research_buyer_activation_claim_never_commercial_authority():
    p = fixtures(activated=1)
    p["distribution"]["buyer_capacity_source_counts_not_buyer_demand_proof"]["capacity_verified"] = 1
    p["distribution"]["buyer_capacity_source_counts_not_buyer_demand_proof"]["terms_verified"] = 1
    out = review(p)
    assert "BUYER_CAPACITY_AND_TERMS" in [g["gate"] for g in out["active_dependency_gates"]]
    assert out["independently_authenticated_buyers"] is None
    assert out["execution_authority"] == "none"


def test_duplicate_or_new_identity_from_research_not_inferred():
    out = review(fixtures())
    assert out["no_cross_cohort_buyer_identity_join"] is True
    assert out["historical_offer_targets_not_new_customers"] != out["shadow_offer_targets_not_new_customers"]


@pytest.mark.parametrize("name,field,bad", [
    ("sales", "outbound_authorized", True),
    ("sales", "case_local_provider_authentication_attested", True),
    ("offers", "payment_execution", True),
    ("offers", "source_refresh_review_required", 1),
    ("distribution", "payment_authorized", True),
    ("distribution", "execution_authority", "send"),
])
def test_cannot_launder_owner_authority(name, field, bad):
    p = fixtures()
    p[name][field] = bad
    with pytest.raises(ValueError):
        review(p)


def test_offer_target_count_inconsistent_fails():
    p = fixtures()
    p["offers"]["in_memory_reconstructed_offer_book"]["missing_canonical_prospect_id_count"] = 100
    with pytest.raises(ValueError, match="inconsistent"):
        review(p)


def test_source_schema_drift_and_unknown_status_are_held():
    p = fixtures()
    p["distribution"]["source_states"]["unknown"] = "available"
    with pytest.raises(ValueError, match="11-source"):
        review(p)
    p = fixtures()
    p["distribution"]["source_states"]["search"] = "buyer_verified"
    with pytest.raises(ValueError, match="11-source"):
        review(p)


def test_negative_buyers_seen_or_greater_activated_rejected():
    p = fixtures(activated=99)
    with pytest.raises(ValueError, match="buyer cohort"):
        review(p)
    p = fixtures()
    p["distribution"]["buyer_capacity_source_counts_not_buyer_demand_proof"]["buyers_seen"] = -1
    out = review(p)
    assert out["buyer_capacity_records_seen_not_purchasers"] is None
    assert out["outbound_authorized"] is False


def test_forged_prior_digest_is_rejected():
    p = fixtures()
    prior = review(p)
    prior["decision_signature_data"]["offer_ready"] = 100
    p["previous"] = prior
    with pytest.raises(ValueError, match="checksum"):
        review(p)


def test_unknown_previous_dependency_rejected():
    p = fixtures()
    prior = review(p)
    prior["decision_signature_data"]["gates"] = ["CREATE_ANOTHER_SALES_AGENT"]
    prior["decision_signature"] = digest(prior["decision_signature_data"])
    p["previous"] = prior
    with pytest.raises(ValueError, match="unknown causal"):
        review(p)


def test_aware_time_required():
    p = fixtures()
    p["now"] = datetime(2026, 10, 20)
    with pytest.raises(ValueError, match="timezone-aware"):
        review(p)


def test_three_identical_observations_learn_stagnation_without_new_jobs():
    p = fixtures()
    first = review(p)
    p["previous"] = first
    second = review(p)
    p["previous"] = second
    third = review(p)
    assert third["transition"] == "UNCHANGED_COMMERCIAL_HOLD"
    assert third["operator_attention_due"] is False
    assert third["recommended_parallel_reviews_not_dispatched"] == []
    assert "BUYER_CAPACITY_AND_TERMS" in third["persistent_holds_three_or_more_observations"]
    node = next(r for r in third["gate_memory"] if r["gate"] == "BUYER_CAPACITY_AND_TERMS")
    assert node["consecutive_active_reviews"] == 3
    assert node["lifetime_active_reviews"] == 3
    assert node["recurrences"] == 0
    assert third["operational_learning_only"] is True
    assert third["economic_feedback_training_permitted"] is False


def test_gate_resolution_then_recurrence_tracked_as_evidence_not_customer():
    p = fixtures()
    initial = review(p)
    p["previous"] = initial
    p["distribution"]["source_states"]["search"] = "available"
    resolved = review(p)
    source_memory = next(r for r in resolved["gate_memory"] if r["gate"] == "SEARCH_SOURCE_FRESHNESS")
    assert source_memory["resolutions"] == 1
    assert source_memory["consecutive_active_reviews"] == 0
    p["previous"] = resolved
    p["distribution"]["source_states"]["search"] = "stale"
    recurring = review(p)
    assert recurring["recurrent_evidence_gates"] == ["SEARCH_SOURCE_FRESHNESS"]
    recurrence = next(r for r in recurring["gate_memory"] if r["gate"] == "SEARCH_SOURCE_FRESHNESS")
    assert recurrence["recurrences"] == 1
    assert recurrence["lifetime_active_reviews"] == 2
    assert recurring["accepted_verified_revenue_cents"] is None
    assert recurring["outbound_authorized"] is False


def test_previous_operational_memory_forgery_rejected():
    p = fixtures()
    first = review(p)
    p["previous"] = first
    first["gate_memory"][0]["active"] = False
    with pytest.raises(ValueError, match="memory contradicts"):
        review(p)
    p = fixtures()
    first = review(p)
    p["previous"] = first
    first["gate_memory"][0]["consecutive_active_reviews"] = -1
    with pytest.raises(ValueError, match="memory contradicts"):
        review(p)
