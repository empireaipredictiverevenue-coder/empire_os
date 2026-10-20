"""Adaptive commercial evidence review: transitions, de-dup, trust and no actions."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from empire_os.commercial_sales_director_adaptive_review import (
    adaptive_original_proof_review,
)

NOW = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)


def make_proof():
    return {
        "schema_version": "empire.commercial.sales_director_original_proof_handoff.v1",
        "mode": "OBSERVE",
        "status": "ORIGINAL_AUTHENTICATED_REPLY_EVIDENCE_HOLD",
        "execution_authority": "none",
        "outbound_authorized": False,
        "crm_mutations": False,
        "agent_tasks_created": False,
        "database_writes": False,
        "original_inbound_provider_events_independently_authenticated": False,
        "case_count": 2,
        "casebook_source_refresh_required": True,
        "review_actions_not_dispatched": {
            "REFRESH_ORIGINAL_COMMERCIAL_SOURCE_EVIDENCE_FIRST": 1,
            "REVIEW_SUPPRESSION_AND_MISSING_CANONICAL_CONTEXT_NO_OUTREACH": 1,
        },
        "source_blockers_allowlisted": [
            "NO_CANONICAL_INBOUND_MESSAGES_VERIFIED",
            "TENANT_AUTHORITY_BINDING_NOT_PROVEN",
        ],
        "original_evidence_proof_summary": {
            "total_control_count": 11,
            "verified_control_count": 5,
            "canonical_message_count": 0,
            "observed_inbound_reply_candidates": 0,
            "authenticated_inbound_reply_count_verified": None,
            "verified_reply_join_count": 0,
            "founder_mailbox_observer_status": "NO_COMPLETE_INBOUND_MESSAGE",
        },
        "sales_director_case_reviews": [
            {
                "operator_case_number": i,
                "recipient": "VERY_PRIVATE@example.invalid",
                "original_recovery_row_numbers": [i],
                "live_followup_permission": False,
                "provider_message_authentication_verified_for_this_case": False,
                "commercial_buyer_intent_verified_for_this_case": False,
                "agent_job_created": False,
            } for i in (1, 2)
        ],
    }


def call(current=None, previous=None, receipts=None):
    return adaptive_original_proof_review(
        current=current or make_proof(), previous=previous,
        source_receipts=receipts, now=NOW,
    )


def test_initial_then_identical_suppresses_duplicate_work_and_private_data():
    first = call()
    assert first["transition"] == "INITIAL_EVIDENCE_REVIEW"
    assert first["operator_attention_due"] is True
    assert sum(x["historical_case_count"] for x in first["existing_owner_review_suggestions"]) == 2
    second = call(previous=first)
    assert second["transition"] == "UNCHANGED_HOLD_NO_DUPLICATE_WORK"
    assert second["operator_attention_due"] is False
    assert second["existing_owner_review_suggestions"] == []
    assert second["duplicate_owner_attention_suppressed"] is True
    assert "VERY_PRIVATE" not in str(first)
    assert "VERY_PRIVATE" not in str(second)
    for row in (first, second):
        assert row["outbound_authorized"] is False
        assert row["database_writes"] is False
        assert row["agent_tasks_created"] is False
        assert row["case_local_provider_authentication_attested"] is False


def test_source_changed_without_real_proof_never_claims_progress():
    first = call(receipts={"conversation_recovery": "a" * 64})
    changed = call(previous=first, receipts={"conversation_recovery": "b" * 64})
    assert changed["transition"] == "OWNER_SOURCE_CHANGED_NO_PROOF_UPGRADE"
    assert changed["changed_owner_source_names"] == ["conversation_recovery"]
    assert changed["operator_attention_due"] is False
    assert changed["existing_owner_review_suggestions"] == []
    third = call(previous=changed, receipts={"conversation_recovery": "b" * 64})
    assert third["transition"] == "UNCHANGED_HOLD_NO_DUPLICATE_WORK"


def test_real_review_state_change_reopens_existing_owner_case_only():
    first = call()
    new_proof = make_proof()
    new_proof["original_evidence_proof_summary"]["observed_inbound_reply_candidates"] = 1
    changed = call(current=new_proof, previous=first)
    assert changed["transition"] == "MATERIAL_EVIDENCE_STATE_CHANGED"
    assert changed["operator_attention_due"] is True
    assert changed["outbound_authorized"] is False
    assert changed["case_local_provider_authentication_attested"] is False
    assert all(x["task_dispatched"] is False for x in changed["existing_owner_review_suggestions"])


def test_semantic_digest_is_deterministic_and_ignores_clock_and_case_order():
    current = make_proof()
    first = call(current=current)
    current["review_generated_at"] = "2026-10-20T11:01:00Z"
    current["sales_director_case_reviews"].reverse()
    current["sales_director_case_reviews"][0]["operator_case_number"] = 52
    current["sales_director_case_reviews"][0]["original_recovery_row_numbers"] = [999]
    changed = call(current=current, previous=first)
    assert changed["transition"] == "UNCHANGED_HOLD_NO_DUPLICATE_WORK"
    assert changed["evidence_semantic_hash"] == first["evidence_semantic_hash"]


def test_forged_previous_semantic_checksum_fails_closed():
    first = call()
    tampered = deepcopy(first)
    tampered["evidence_semantic_state"]["case_count"] = 900
    with pytest.raises(ValueError, match="checksum"):
        call(previous=tampered)


@pytest.mark.parametrize("key,bad", [
    ("schema_version", "untrusted"),
    ("execution_authority", "send"),
    ("outbound_authorized", True),
    ("database_writes", True),
    ("agent_tasks_created", True),
    ("original_inbound_provider_events_independently_authenticated", True),
])
def test_wrong_current_proof_contract_fails_closed(key, bad):
    current = make_proof()
    current[key] = bad
    with pytest.raises(ValueError, match="trusted"):
        call(current=current)


def test_unknown_owner_route_cannot_dispatch_or_leak():
    current = make_proof()
    current["review_actions_not_dispatched"] = {"SEND_NOW": 2}
    with pytest.raises(ValueError, match="bounded"):
        call(current=current)
    current = make_proof()
    current["source_blockers_allowlisted"].append("SECRET_PROSPECT_PRIVATE_NAME")
    with pytest.raises(ValueError, match="blocker"):
        call(current=current)


def test_case_level_send_permission_cannot_be_adapted():
    current = make_proof()
    current["sales_director_case_reviews"][0]["live_followup_permission"] = True
    with pytest.raises(ValueError, match="case-specific"):
        call(current=current)


def test_invalid_sha_receipt_rejected():
    with pytest.raises(ValueError, match="SHA256"):
        call(receipts={"conversation_recovery": "not-a-sha"})
    with pytest.raises(ValueError, match="only existing"):
        call(receipts={"private_recipient": "a" * 64})


def test_malformed_previous_authority_rejected():
    prior = call()
    prior["outbound_authorized"] = True
    with pytest.raises(ValueError, match="previous"):
        call(previous=prior)


def test_zero_cases_is_still_a_safe_nonexecuting_transition():
    current = make_proof()
    current["case_count"] = 0
    current["review_actions_not_dispatched"] = {}
    current["sales_director_case_reviews"] = []
    result = call(current=current)
    assert result["operator_attention_due"] is True
    assert result["existing_owner_review_suggestions"] == []
    assert result["outbound_authorized"] is False
