"""Prospective observation-only feedback; no fake buyer or emotional scores."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib

import pytest

from empire_os.prime_conversation_response_learning_shadow import (
    review_objection_response_outcomes,
)

NOW = datetime(2026, 10, 24, 10, tzinfo=timezone.utc)

def case(i=0, **changes):
    at = NOW - timedelta(days=3)
    row = {
        "case_digest": hashlib.sha256(f"synthetic-consenting-case-{i}".encode()).hexdigest(),
        "approach_code": "OFFER_VERIFIABLE_EVIDENCE_WITHOUT_GUARANTEES",
        "original_inbound_at": at.isoformat(),
        "human_reply_at": (at + timedelta(hours=1)).isoformat(),
        "response_observed_at": (at + timedelta(hours=3)).isoformat(),
        "outcome_code": "FOLLOWUP_QUESTION_OBSERVED",
        "original_owner_readback_reviewed": True,
        "permitted_purpose_reviewed": True,
        "synthetic": False,  # models the shape of an owner-approved real row; never real proof
        "transcript_or_personal_details_included": False,
    }
    row.update(changes)
    return row

def review(rows=None):
    return review_objection_response_outcomes(
        original_owner_rows=rows, as_of=NOW,
    )


def test_no_real_outcomes_unknown_not_zero_business():
    out = review()
    assert out["status"] == "NO_ORIGINAL_OUTCOME_ROWS_CONNECTED"
    assert out["eligible_case_count_band_if_at_least_ten"] is None
    assert out["verified_buyer_conversion_count"] is None
    assert out["independent_original_source_provenance_verified"] is False
    assert out["learned_weights_promoted"] is False


def test_small_sample_suppressed_and_no_personality_tracking():
    out = review([case(i) for i in range(9)])
    assert out["status"] == "OUTCOME_AGGREGATION_HELD_SMALL_COHORT"
    assert out["approach_groups_sufficient_for_coarse_review"] == []
    assert out["eligible_case_count_band_if_at_least_ten"] is None
    assert out["person_level_prediction_or_profiling"] is False


def test_ten_cases_allow_coarse_description_not_causal_claim():
    out = review([case(i) for i in range(10)])
    assert out["status"] == "UNAUTHENTICATED_OWNER_REVIEWED_DESCRIPTIVE_COHORT_ONLY"
    assert out["eligible_case_count_band_if_at_least_ten"] == "10-19"
    assert len(out["approach_groups_sufficient_for_coarse_review"]) == 1
    grp = out["approach_groups_sufficient_for_coarse_review"][0]
    assert grp["observed_outcome_code_count_bands"]["FOLLOWUP_QUESTION_OBSERVED"] == "10-19"
    assert grp["descriptive_only_not_causal_lift"] is True
    assert out["treatment_effect_or_uplift_established"] is False
    assert out["realized_revenue_cents"] is None
    assert out["send_authorized"] is False
    assert out["outbound_sent"] is False
    assert "synthetic-consenting-case" not in str(out)


def test_pending_not_counted_as_success():
    rows = [case(i) for i in range(10)]
    for row in rows[:8]:
        row.update(outcome_code="UNKNOWN_PENDING", response_observed_at=None)
    out = review(rows)
    assert out["eligible_case_count_band_if_at_least_ten"] == "10-19"
    assert out["unresolved_censored_case_count_band_if_at_least_ten"] is None
    assert out["approach_groups_sufficient_for_coarse_review"][0]["observed_outcome_code_count_bands"] == {}
    assert out["learned_weights_promoted"] is False


def test_decline_and_optout_are_not_an_optimisation_target():
    rows = [case(i, outcome_code="DECLINED_OBSERVED") for i in range(10)]
    out = review(rows)
    assert "DECLINED_OBSERVED" in out["approach_groups_sufficient_for_coarse_review"][0]["observed_outcome_code_count_bands"]
    assert out["person_level_prediction_or_profiling"] is False


@pytest.mark.parametrize("change, reason", [
    ({"case_digest": "personal@example.com"}, "opaque_case_digest"),
    ({"original_owner_readback_reviewed": False}, "source_hold"),
    ({"permitted_purpose_reviewed": False}, "source_hold"),
    ({"synthetic": True}, "source_hold"),
    ({"transcript_or_personal_details_included": True}, "source_hold"),
    ({"approach_code": "EXPLOIT_ANXIETY_TO_CLOSE"}, "unrecognised_human_reply"),
    ({"outcome_code": "REALIZED_REVENUE"}, "unknown_original_observed"),
    ({"human_reply_at": "2026-10-20T20:00:00"}, "original_response_clock"),
    ({"human_reply_at": (NOW + timedelta(days=3)).isoformat()}, "noncausal_original_reply"),
    ({"response_observed_at": (NOW + timedelta(days=3)).isoformat()}, "noncausal_original_outcome"),
    ({"response_observed_at": (NOW - timedelta(days=10)).isoformat()}, "noncausal_original_outcome"),
    ({"outcome_code": "UNKNOWN_PENDING"}, "censored_vs_observed"),
    ({"response_observed_at": None}, "censored_vs_observed"),
    ({"raw_text": "private contact body"}, "exact_privacy_minimal"),
])
def test_outcome_row_attacks_held(change, reason):
    with pytest.raises(ValueError, match=reason):
        review([case(**change)])


def test_no_reply_cannot_be_recorded_as_human_sent():
    with pytest.raises(ValueError, match="no_reply_policy"):
        review([case(approach_code="NO_NEW_REPLY_SUGGESTED_FROM_CUES")])


def test_no_reply_can_only_be_held_or_reported_without_send():
    row = case(approach_code="NO_NEW_REPLY_SUGGESTED_FROM_CUES", human_reply_at=None,
               outcome_code="UNKNOWN_PENDING", response_observed_at=None)
    out = review([row])
    assert out["status"] == "OUTCOME_AGGREGATION_HELD_SMALL_COHORT"
    assert out["send_authorized"] is False


def test_duplicate_pseudonymous_case_cannot_inflate_observation_counts():
    with pytest.raises(ValueError, match="replay_or_duplicate"):
        review([case(3), case(3)])


def test_more_than_500_cases_refused():
    with pytest.raises(ValueError, match="bounded_original_outcome"):
        review([case(i) for i in range(501)])


def test_fields_never_return_identifiers():
    output = review([case(i) for i in range(12)])
    assert "case_digest" not in str(output)
    assert "message" not in str(output).lower()
    assert "email" not in str(output).lower()
    assert output["database_writes"] is False
    assert output["execution_authority"] == "none"


def test_original_predictive_bridge_reports_no_feedback_when_unconnected():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    out = build_predictive_revenue_brain_review(
        tenant_id="synthetic-tenant", as_of=NOW,
    )
    assert out["prime_conversation_response_learning_shadow"]["status"] == "NO_ORIGINAL_OUTCOME_ROWS_CONNECTED"
    assert out["prime_conversation_response_learning_shadow"]["verified_buyer_conversion_count"] is None
    assert out["recognized_revenue_cents"] is None
    assert out["outbound_sent"] is False
    assert out["database_writes"] is False


def test_original_predictive_bridge_carries_coarse_descriptive_feedback_not_authority():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    out = build_predictive_revenue_brain_review(
        tenant_id="synthetic-tenant",
        as_of=NOW,
        original_conversation_response_feedback_rows=[case(i) for i in range(10)],
    )
    learn = out["prime_conversation_response_learning_shadow"]
    assert learn["eligible_case_count_band_if_at_least_ten"] == "10-19"
    assert learn["learned_weights_promoted"] is False
    assert learn["independent_original_source_provenance_verified"] is False
    assert learn["verified_buyer_conversion_count"] is None
    assert learn["treatment_effect_or_uplift_established"] is False
    assert out["prime_first_buyer_intent_independently_verified"] is False
    assert out["payment_executed"] is False
    assert out["recognized_revenue_cents"] is None


def test_original_predictive_bridge_rejects_invalid_original_feedback():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    with pytest.raises(ValueError, match="unrecognised_human_reply_approach"):
        build_predictive_revenue_brain_review(
            tenant_id="synthetic-tenant",
            as_of=NOW,
            original_conversation_response_feedback_rows=[
                case(approach_code="PRESSURE_AND_MANIPULATE"),
            ],
        )


def test_no_reply_policy_cannot_take_credit_for_customer_question_answered():
    with pytest.raises(ValueError, match="no_reply_policy_cannot_claim_question_answered"):
        review([case(
            approach_code="NO_NEW_REPLY_SUGGESTED_FROM_CUES",
            human_reply_at=None,
            outcome_code="QUESTION_ANSWERED_REPORTED",
        )])
