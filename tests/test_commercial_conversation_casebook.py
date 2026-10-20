"""Offline boundaries for exact-ID conversation conversion casebook."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from empire_os.commercial_conversation_casebook import review_conversion_casebook

NOW = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
CURRENT = "2026-10-20T09:00:00Z"
OLD = "2026-09-29T00:00:00Z"


def packets(*, hold=True):
    return {
        "offer_book": {
            "schema_version": "empire.predictive-revenue.commercial-offer-book.v2",
            "execution_authority": "none",
            "targets": [
                {
                    "company": "Secret Company",
                    "email": "alice@example.invalid",
                    "canonical_prospect_id": None,
                    "source_product_codes": ["sample_report"],
                    "conversation_refs": ["root-1", "root-2"],
                },
                {
                    "company": "Second Example",
                    "conversation_refs": ["root-3"],
                },
            ],
        },
        "conversation_recovery": {
            "schema_version": "empire.conversation_recovery.v1",
            "execution_authority": "none",
            "send_executed": False,
            "observed_at": CURRENT,
            "items": [
                {
                    "root_intent_id": "root-1", "business_name": "Secret Company",
                    "recipient": "alice@example.invalid",
                    "recoverable": True, "recovery_reason": "due_now",
                },
                {
                    "root_intent_id": "root-2", "recoverable": False,
                    "recovery_reason": "suppressed_after_delivery",
                },
                {
                    "root_intent_id": "root-3", "recoverable": False,
                    "recovery_reason": "missing_canonical_context",
                },
                {"root_intent_id": "root-unlinked", "recoverable": True},
            ],
        },
        "source_health": {
            "schema_version": "empire.commercial_growth.shadow_offer_reconstruction.v1",
            "mode": "OBSERVE",
            "execution_authority": "none",
            "recomputed_using_existing_owner_logic": True,
            "source_refresh_review_required": hold,
            "calculated_at": CURRENT,
        },
        "now": NOW,
    }


def test_exact_linkage_no_contact_leak_and_no_writes():
    inputs = packets()
    original = deepcopy(inputs)
    result = review_conversion_casebook(**inputs)
    assert inputs == original
    assert result["distinct_offer_thread_refs"] == 3
    assert result["exact_recovery_matches"] == 3
    assert result["offer_targets_with_original_conversation_refs"] == 2
    assert result["unlinked_recovery_thread_records"] == 1
    assert result["state_counts"] == {
        "FRESH_PROVENANCE_REQUIRED": 1,
        "SUPPRESSION_OR_CONTEXT_HOLD": 2,
    }
    assert result["outbound_authorized"] is False
    assert result["database_writes"] is False
    assert result["agent_tasks_created"] is False
    assert result["manual_operator_cases"][0]["owner_lane"] == "sales_director_operator"
    assert result["manual_operator_cases"][0]["recovery_source_row_numbers"] == [2]
    assert result["manual_operator_cases"][0]["offer_book_target_row_numbers"] == [1]
    assert "alice@" not in str(result)
    assert "Secret Company" not in str(result)
    assert "root-1" not in str(result)
    assert "root-2" not in str(result)


def test_fresh_source_does_not_make_original_thread_sendable():
    p = packets(hold=False)
    r = review_conversion_casebook(**p)
    assert r["status"] == "SALES_OPERATOR_MANUAL_REVIEW_ONLY"
    assert r["state_counts"]["HISTORICAL_CONTEXT_READY_FOR_HUMAN_REVIEW"] == 1
    assert all(c["live_outbound_authorized"] is False for c in r["manual_operator_cases"])
    assert all(c["inbound_reply_verified"] is False for c in r["manual_operator_cases"])
    assert all(c["original_provider_inbox_checked"] is False for c in r["manual_operator_cases"])


def test_fuzzy_company_match_is_not_a_link():
    p = packets()
    p["offer_book"]["targets"][1]["conversation_refs"] = ["different-root"]
    p["conversation_recovery"]["items"][2]["business_name"] = "Second Example"
    r = review_conversion_casebook(**p)
    assert r["unmatched_offer_thread_refs"] == 1
    assert r["state_counts"]["MISSING_EXACT_RECOVERY_RECEIPT"] == 1


def test_duplicate_thread_on_two_offers_is_quarantined():
    p = packets(hold=False)
    p["offer_book"]["targets"][1]["conversation_refs"] = ["root-1"]
    r = review_conversion_casebook(**p)
    item = next(c for c in r["manual_operator_cases"] if c["recovery_source_row_numbers"] == [1])
    assert item["state"] == "AMBIGUOUS_EXACT_THREAD_IDENTITY"
    assert item["offer_book_target_row_numbers"] == [1, 2]


def test_recovery_with_duplicate_exact_ids_is_held():
    p = packets()
    p["conversation_recovery"]["items"].append({
        "root_intent_id": "root-1", "recoverable": True,
    })
    r = review_conversion_casebook(**p)
    assert r["state_counts"]["AMBIGUOUS_EXACT_THREAD_IDENTITY"] == 1


def test_repeated_ref_in_same_offer_deduplicated_and_counted():
    p = packets()
    p["offer_book"]["targets"][0]["conversation_refs"].append("root-1")
    r = review_conversion_casebook(**p)
    assert r["distinct_offer_thread_refs"] == 3
    assert r["duplicate_refs_within_offer"] == 1


def test_unrecoverable_cannot_be_laundered_by_fresh_clock():
    p = packets(hold=False)
    r = review_conversion_casebook(**p)
    assert r["state_counts"]["SUPPRESSION_OR_CONTEXT_HOLD"] == 2


def test_old_recovery_timestamp_forces_freshness_hold():
    p = packets(hold=False)
    p["conversation_recovery"]["observed_at"] = OLD
    r = review_conversion_casebook(**p)
    assert r["source_evidence_refresh_required"] is True
    assert r["status"] == "SOURCE_REVIEW_HOLD"
    assert r["state_counts"]["FRESH_PROVENANCE_REQUIRED"] == 1


@pytest.mark.parametrize("key", ["offer_book", "conversation_recovery", "source_health"])
def test_authority_escalation_rejected(key):
    p = packets()
    p[key]["execution_authority"] = "send"
    with pytest.raises(ValueError):
        review_conversion_casebook(**p)


def test_recovery_send_executed_unacceptable():
    p = packets()
    p["conversation_recovery"]["send_executed"] = True
    with pytest.raises(ValueError):
        review_conversion_casebook(**p)


def test_forged_freshness_health_contract_is_rejected():
    p = packets()
    p["source_health"]["recomputed_using_existing_owner_logic"] = False
    with pytest.raises(ValueError):
        review_conversion_casebook(**p)


def test_excessive_conversation_refs_fails_closed():
    p = packets()
    p["offer_book"]["targets"][0]["conversation_refs"] = ["ref"] * 51
    with pytest.raises(ValueError, match="bounded"):
        review_conversion_casebook(**p)


def test_not_timezone_aware_refused():
    p = packets()
    p["now"] = datetime(2026, 10, 20, 9)
    with pytest.raises(ValueError, match="timezone-aware"):
        review_conversion_casebook(**p)
