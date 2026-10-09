"""Stage 3 exact-join and tenant/identity quarantine gauntlet.

All identifiers and inboxes here are synthetic *test fixtures*. No database,
mail provider, customer file, or production conversation is accessed.
"""
from copy import deepcopy

import pytest

from empire_os.conversation_reply_binding_review import review_identity_bindings
from empire_os.conversation_reply_linkage_plan import plan


def candidate():
    return {
        "replies": [{
            "id": "synthetic-reply-1", "intent_id": "synthetic-intent-1",
            "provider_message_id": "synthetic-provider-1",
            "message_id": "<reply-1@fixture.example>",
            "in_reply_to": "<sent-1@fixture.example>",
            "direction": "inbound",
            "normalized_from_contact": "buyer@fixture.example",
            "tenant_id": "synthetic-tenant-a",
            "body_text": "DO NOT LEAK PRIVATE BODY",
        }],
        "outbound_intents": [{
            "id": "synthetic-intent-1", "status": "sent",
            "prospect_id": "synthetic-prospect-1",
        }],
        "conversations": [{
            "id": "synthetic-conv-1", "outbound_intent_id": "synthetic-intent-1",
            "channel": "email", "state": "engaged",
            "prospect_id": "synthetic-prospect-1",
        }],
        "tenant_authorities": [{
            "tenant_id": "synthetic-tenant-a",
            "intent_id": "synthetic-intent-1",
            "conversation_id": "synthetic-conv-1",
            "status": "active", "evidence_ref": "synthetic:tenant-authorization",
        }],
        "contact_authorities": [{
            "tenant_id": "synthetic-tenant-a",
            "intent_id": "synthetic-intent-1",
            "normalized_contact": "buyer@fixture.example",
            "contact_id": "synthetic-contact-1",
            "status": "active", "evidence_ref": "synthetic:contact-authorization",
        }],
        "original_outbound_headers": [{
            "intent_id": "synthetic-intent-1",
            "message_id": "<sent-1@fixture.example>",
            "evidence_ref": "synthetic:sent-header",
        }],
        "provider_receipts": [{
            "provider_message_id": "synthetic-provider-1",
            "message_id": "<reply-1@fixture.example>",
            "in_reply_to": "<sent-1@fixture.example>",
            "direction": "inbound", "tenant_id": "synthetic-tenant-a",
            "source_ref": "synthetic:inbox-receipt",
        }],
    }


def test_exact_one_to_one_structural_case_is_review_only_and_pii_free():
    evidence = candidate()
    result = review_identity_bindings(evidence)
    assert result["structurally_reviewable_count"] == 1
    assert result["quarantined_count"] == 0
    assert result["records"][0]["status"] == "STRUCTURALLY_REVIEWABLE_NOT_AUTHENTICATED"
    assert result["records"][0]["original_provider_authenticated"] is False
    assert result["tenant_authority_independently_attested"] is False
    assert result["buyer_intent_verified_count"] == 0
    assert result["canonical_messages_promoted"] == 0
    assert result["database_mutations"] == 0
    assert result["execution_authority"] == "none"
    rendered = repr(result)
    for private in ("buyer@fixture.example", "DO NOT LEAK PRIVATE BODY",
                    "synthetic-tenant-a", "<reply-1@fixture.example>",
                    "synthetic:inbox-receipt"):
        assert private not in rendered


@pytest.mark.parametrize("table,change,reason", [
    ("replies", {"intent_id": "wrong"}, "OUTBOUND_INTENT_NOT_FOUND"),
    ("replies", {"direction": "outbound"}, "ORIGINAL_INBOUND_DIRECTION_UNVERIFIED"),
    ("replies", {"in_reply_to": "<wrong@fixture.example>"},
     "ORIGINAL_OUTBOUND_RFC_PARENT_NOT_FOUND"),
    ("replies", {"provider_message_id": ""}, "ORIGINAL_PROVIDER_THREAD_EVIDENCE_MISSING"),
    ("replies", {"tenant_id": "synthetic-tenant-b"}, "CROSS_TENANT_REPLY_CONFLICT"),
    ("replies", {"normalized_from_contact": "attacker@fixture.example"},
     "CANONICAL_CONTACT_NOT_PROVEN"),
    ("outbound_intents", {"status": "draft"}, "OUTBOUND_INTENT_NOT_SENT_OR_SUPPRESSED"),
    ("conversations", {"prospect_id": "another-prospect"}, "CANONICAL_PARTICIPANT_CONFLICT"),
    ("conversations", {"state": "closed"}, "CONVERSATION_NOT_ACTIVE_EMAIL"),
    ("tenant_authorities", {"tenant_id": ""}, "TENANT_AUTHORITY_NOT_PROVEN"),
    ("tenant_authorities", {"evidence_ref": ""}, "TENANT_AUTHORITY_NOT_PROVEN"),
    ("contact_authorities", {"status": "revoked"}, "CANONICAL_CONTACT_NOT_PROVEN"),
    ("provider_receipts", {"tenant_id": "synthetic-tenant-b"}, "CROSS_TENANT_RECEIPT_CONFLICT"),
    ("provider_receipts", {"source_ref": ""}, "PROVIDER_RECEIPT_PROVENANCE_INCOMPLETE"),
])
def test_disallowed_identity_or_forged_metadata_is_quarantined(table, change, reason):
    evidence = candidate()
    evidence[table][0].update(change)
    result = review_identity_bindings(evidence)
    assert result["quarantined_count"] == 1
    assert reason in result["records"][0]["reason_codes"]
    assert result["buyer_intent_verified_count"] == 0
    assert result["execution_authority"] == "none"


@pytest.mark.parametrize("table,reason", [
    ("outbound_intents", "OUTBOUND_INTENT_AMBIGUOUS"),
    ("conversations", "CONVERSATION_AMBIGUOUS"),
    ("tenant_authorities", "TENANT_AUTHORITY_AMBIGUOUS"),
    ("contact_authorities", "CANONICAL_CONTACT_AMBIGUOUS"),
    ("original_outbound_headers", "ORIGINAL_OUTBOUND_RFC_PARENT_AMBIGUOUS"),
    ("provider_receipts", "PROVIDER_RECEIPT_AMBIGUOUS"),
])
def test_multiple_possible_links_are_not_selected_arbitrarily(table, reason):
    evidence = candidate()
    evidence[table].append(deepcopy(evidence[table][0]))
    result = review_identity_bindings(evidence)
    assert result["quarantined_count"] == 1
    assert reason in result["reason_counts"]


def test_replay_and_duplicate_reply_id_are_quarantined():
    evidence = candidate()
    evidence["replies"].append(deepcopy(evidence["replies"][0]))
    result = review_identity_bindings(evidence)
    assert result["quarantined_count"] == 2
    assert result["reason_counts"]["DUPLICATE_PROVIDER_EVENT"] == 2
    assert result["reason_counts"]["REPLY_SOURCE_ID_DUPLICATED"] == 2
    assert result["reason_counts"]["DUPLICATE_RFC_MESSAGE_ID"] == 2
    assert result["canonical_messages_promoted"] == 0


@pytest.mark.parametrize("key,value", [
    ("replies", [{"id": "r"}] * 101),
    ("provider_receipts", [{"id": "r"}] * 101),
    ("tenant_authorities", "not an array"),
    ("replies", [None]),
])
def test_unbounded_or_invalid_inputs_fail_closed(key, value):
    evidence = candidate()
    evidence[key] = value
    with pytest.raises(ValueError):
        review_identity_bindings(evidence)


def test_existing_planner_consumes_controlled_result_but_never_calls_it_proof():
    evidence = candidate()
    result = plan({"database_candidates": []}, {}, controlled_identity_inputs=evidence)
    review = result["controlled_identity_review"]
    assert review["structurally_reviewable_count"] == 1
    assert result["controlled_identity_review_not_live_evidence"] is True
    assert result["actual_joined_rows_proven"] == 0
    assert result["buyer_intent_verified"] is False
    assert result["canonical_messages_promoted"] == 0
    assert result["database_access_attempted"] is False
    assert result["external_execution_authority"] == "none"


def test_live_planner_has_no_implicit_synthetic_data_or_identity_promotion():
    result = plan({"database_candidates": []}, {})
    assert result["controlled_identity_review"] is None
    assert result["buyer_intent_verified"] is False
    assert result["actual_joined_rows_proven"] == 0


@pytest.mark.parametrize("field,value,reason", [
    ("message_id", "not-an-rfc-message-id", "INVALID_ORIGINAL_RFC_MESSAGE_CHAIN"),
    ("in_reply_to", "<missing-at-sign>", "INVALID_ORIGINAL_RFC_MESSAGE_CHAIN"),
    ("normalized_from_contact", "not-an-address", "CONTACT_ADDRESS_MISSING_OR_INVALID"),
])
def test_untrusted_source_identifiers_never_pass_structural_review(field, value, reason):
    e = candidate()
    e["replies"][0][field] = value
    report = review_identity_bindings(e)
    assert report["quarantined_count"] == 1
    assert reason in report["reason_counts"]
    assert report["buyer_intent_verified_count"] == 0


def test_partial_participant_binding_is_not_accepted():
    e = candidate()
    e["outbound_intents"][0]["entity_id"] = "synthetic-company-1"
    report = review_identity_bindings(e)
    assert report["quarantined_count"] == 1
    assert "CANONICAL_PARTICIPANT_SCOPE_INCOMPLETE" in report["reason_counts"]


def test_empty_input_does_not_imply_zero_buyer_demand():
    report = review_identity_bindings({})
    assert report["candidate_count"] == 0
    assert report["production_original_provider_verification_performed"] is False
    assert report["buyer_intent_verified_count"] == 0
    assert report["source_table_reads"] == 0
