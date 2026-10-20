"""Fail-closed tests: Conversation OS global health cannot promote historic threads."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from empire_os.commercial_sales_director_original_proof import (
    review_sales_director_original_proof,
)

NOW = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)


def inputs(*, stale=True):
    cases = [
        {
            "operator_case_number": 1,
            "owner_lane": "sales_director_operator",
            "state": "SUPPRESSION_OR_CONTEXT_HOLD",
            "recovery_source_row_numbers": [3],
            "offer_book_target_row_numbers": [2],
            "inbound_reply_verified": False,
            "live_outbound_authorized": False,
            "agent_task_created": False,
            "recipient": "secret@example.invalid",
            "root_intent_id": "private-intent",
        },
        {
            "operator_case_number": 2,
            "owner_lane": "sales_director_operator",
            "state": "FRESH_PROVENANCE_REQUIRED",
            "recovery_source_row_numbers": [4],
            "offer_book_target_row_numbers": [6],
            "inbound_reply_verified": False,
            "live_outbound_authorized": False,
            "agent_task_created": False,
            "company": "Private Customer Ltd",
        },
    ]
    return {
        "casebook": {
            "schema_version": "empire.commercial.conversation_conversion_casebook.v1",
            "mode": "OBSERVE",
            "execution_authority": "none",
            "outbound_authorized": False,
            "agent_tasks_created": False,
            "database_writes": False,
            "source_evidence_refresh_required": stale,
            "distinct_offer_thread_refs": 2,
            "manual_operator_cases": cases,
        },
        "conversation_proof": {
            "schema_version": "empire.conversation_control_operational_truth.v1",
            "mode": "OBSERVE",
            "status": "HOLD_REAL_REPLY_EVIDENCE_REQUIRED",
            "execution_authority": "NONE",
            "automatic_promotion_authorized": False,
            "authenticated_reply_identity_verified": False,
            "tenant_binding_independently_verified": False,
            "buyer_intent_verified": False,
            "outbound_enabled": False,
            "database_writes": False,
            "total_control_count": 11,
            "verified_control_count": 5,
            "canonical_message_count": 0,
            "observed_inbound_reply_candidate_count": 0,
            "authenticated_inbound_reply_count_verified": None,
            "verified_reply_join_count": 0,
            "founder_mailbox_observer_status": "NO_COMPLETE_INBOUND_MESSAGE",
            "source_blockers": [
                "JOIN_CARDINALITY_UNVERIFIED",
                "SECRET_RAW_REPLY_BODY_DO_NOT_DISCLOSE",
            ],
        },
        "now": NOW,
    }


def test_exact_source_contract_and_no_private_echo():
    provided = inputs()
    before = deepcopy(provided)
    review = review_sales_director_original_proof(**provided)
    assert provided == before
    assert review["case_count"] == 2
    assert review["status"] == "ORIGINAL_AUTHENTICATED_REPLY_EVIDENCE_HOLD"
    assert review["review_actions_not_dispatched"] == {
        "REFRESH_ORIGINAL_COMMERCIAL_SOURCE_EVIDENCE_FIRST": 1,
        "REVIEW_SUPPRESSION_AND_MISSING_CANONICAL_CONTEXT_NO_OUTREACH": 1,
    }
    assert review["source_blockers_allowlisted"] == ["JOIN_CARDINALITY_UNVERIFIED"]
    assert review["original_evidence_proof_summary"]["canonical_message_count"] == 0
    assert review["agent_tasks_created"] is False
    assert review["outbound_authorized"] is False
    assert "secret@" not in str(review)
    assert "Private Customer" not in str(review)
    assert "private-intent" not in str(review)
    assert "SECRET_RAW_REPLY_BODY" not in str(review)
    assert review["sales_director_case_reviews"][0]["original_recovery_row_numbers"] == [3]


def test_fresh_shadow_still_blocks_orig_provider_absent():
    p = inputs(stale=False)
    review = review_sales_director_original_proof(**p)
    assert review["review_actions_not_dispatched"]["VERIFY_ORIGINAL_PROVIDER_INBOUND_AND_TENANT_CONTACT_BINDING"] == 1
    assert all(r["live_followup_permission"] is False for r in review["sales_director_case_reviews"])


def test_aggregate_inbound_counts_cannot_authenticate_specific_case():
    p = inputs(stale=False)
    p["conversation_proof"].update({
        "canonical_message_count": 100,
        "observed_inbound_reply_candidate_count": 100,
        "verified_reply_join_count": 98,
        "authenticated_inbound_reply_count_verified": 50,
        "founder_mailbox_observer_status": "VERIFIED_RUNTIME",
    })
    review = review_sales_director_original_proof(**p)
    assert review["original_evidence_proof_summary"]["authenticated_inbound_reply_count_verified"] == 50
    assert all(row["original_inbound_proof_linked_to_this_case"] is False for row in review["sales_director_case_reviews"])
    assert all(row["live_followup_permission"] is False for row in review["sales_director_case_reviews"])


@pytest.mark.parametrize("key,value", [
    ("schema_version", "fake-version"),
    ("mode", "SEND"),
    ("status", "APPROVED"),
    ("execution_authority", "send"),
    ("automatic_promotion_authorized", True),
    ("authenticated_reply_identity_verified", True),
    ("tenant_binding_independently_verified", True),
    ("buyer_intent_verified", True),
    ("outbound_enabled", True),
    ("database_writes", True),
])
def test_owner_proof_authority_forgery_fails_closed(key, value):
    p = inputs()
    p["conversation_proof"][key] = value
    with pytest.raises(ValueError, match="not trusted"):
        review_sales_director_original_proof(**p)


@pytest.mark.parametrize("key,value", [
    ("schema_version", "different"),
    ("mode", "AUTO"),
    ("execution_authority", "send"),
    ("outbound_authorized", True),
    ("agent_tasks_created", True),
    ("database_writes", True),
])
def test_casebook_authority_forgery_fails_closed(key, value):
    p = inputs()
    p["casebook"][key] = value
    with pytest.raises(ValueError, match="casebook"):
        review_sales_director_original_proof(**p)


def test_bad_case_count_and_duplicate_case_id_rejected():
    p = inputs()
    p["casebook"]["distinct_offer_thread_refs"] = 1
    with pytest.raises(ValueError, match="count"):
        review_sales_director_original_proof(**p)
    p = inputs()
    p["casebook"]["manual_operator_cases"][1]["operator_case_number"] = 1
    with pytest.raises(ValueError, match="casebook case"):
        review_sales_director_original_proof(**p)


def test_unknown_case_state_is_never_auto_routed():
    p = inputs()
    p["casebook"]["manual_operator_cases"][1]["state"] = "FULLY_APPROVED_TO_SEND"
    with pytest.raises(ValueError, match="untrusted casebook case"):
        review_sales_director_original_proof(**p)


def test_bad_row_number_and_missing_identity_row_ref_rejected():
    p = inputs()
    p["casebook"]["manual_operator_cases"][0]["recovery_source_row_numbers"] = [0]
    with pytest.raises(ValueError, match="1-based"):
        review_sales_director_original_proof(**p)
    p = inputs()
    p["casebook"]["manual_operator_cases"][0]["offer_book_target_row_numbers"] = []
    with pytest.raises(ValueError, match="case missing"):
        review_sales_director_original_proof(**p)


def test_bad_conversation_control_count_rejected():
    p = inputs()
    p["conversation_proof"]["verified_control_count"] = 12
    with pytest.raises(ValueError, match="bounded Conversation OS controls"):
        review_sales_director_original_proof(**p)


def test_no_tz_refused():
    p = inputs()
    p["now"] = datetime(2026, 10, 20, 10)
    with pytest.raises(ValueError, match="timezone-aware"):
        review_sales_director_original_proof(**p)
