"""Aggregate-only link diagnostics are NOT authenticated buyer evidence."""
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.reply_lineage_health import assess_reply_lineage


NOW = datetime(2026, 10, 9, 17, 30, tzinfo=timezone.utc)


def _snapshot():
    return {
        "generated_at": NOW.isoformat(),
        "execution_authority": "none",
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "raw_reply_records_are_commercial_proof": False,
        "inbound_reply_authenticity_verified": False,
        "restricted_reply_lineage": {
            "schema": "empire.market_gps_restricted_reply_lineage.v1",
            "window_days": 90,
            "reply_records_observed": 5,
            "reply_records_with_intent_pointer": 4,
            "reply_records_matched_to_intent": 3,
            "reply_records_matched_to_prospect": 2,
            "reply_records_missing_intent_pointer": 1,
            "reply_records_with_unmatched_intent": 1,
            "reply_records_with_unmatched_prospect": 1,
            "positive_classification_records_unverified": 1,
            "original_provider_message_id_checked": False,
            "canonical_contact_identity_verified": False,
            "provider_thread_binding_verified": False,
            "tenant_binding_verified": False,
            "buyer_intent_verified": False,
            "commercial_demand_inferred": False,
            "read_only_aggregate": True,
            "execution_authority": "none",
        },
    }


def test_pending_prior_to_next_gps_cycle_is_not_zero_replies():
    result = assess_reply_lineage({
        "generated_at": NOW.isoformat(),
        "execution_authority": "none",
    }, NOW)
    assert result["status"] == "PENDING_RESTRICTED_LINEAGE_SNAPSHOT"
    assert "counts" not in result
    assert "LINEAGE_AGGREGATE_NOT_YET_OBSERVED" in result["reason_codes"]
    assert result["buyer_intent_verified"] is False


def test_structural_join_counts_preserve_all_authentication_gates():
    result = assess_reply_lineage(_snapshot(), NOW)
    assert result["status"] == "CURRENT_STRUCTURAL_COUNTS_ONLY"
    assert result["counts"]["reply_records_observed"] == 5
    assert result["counts"]["reply_records_with_unmatched_intent"] == 1
    assert "REPLY_ROWS_MISSING_INTENT_POINTER" in result["reason_codes"]
    assert "REPLY_INTENT_POINTER_WITH_NO_MATCH" in result["reason_codes"]
    assert "INTENT_WITH_NO_PROSPECT_MATCH" in result["reason_codes"]
    assert result["buyer_intent_verified"] is False
    assert result["tenant_authority_verified"] is False
    assert result["original_provider_identity_verified"] is False
    assert result["execution_authority"] == "none"


@pytest.mark.parametrize("key,value", [
    ("generated_at", "2026-10-09T17:30:00"),
    ("generated_at", "2026-10-10T17:30:00Z"),
    ("generated_at", "2026-10-09T10:30:00Z"),
])
def test_stale_future_or_undated_aggregate_has_no_counts(key, value):
    raw = _snapshot()
    raw[key] = value
    result = assess_reply_lineage(raw, NOW)
    assert result["status"] == "REJECTED_STALE_OR_UNDATED_AGGREGATE"
    assert "counts" not in result


@pytest.mark.parametrize("key,value", [
    ("execution_authority", "execute"),
    ("buyer_intent_inferred", True),
    ("raw_reply_records_are_commercial_proof", True),
])
def test_unsafe_envelope_is_rejected(key, value):
    raw = _snapshot()
    raw[key] = value
    result = assess_reply_lineage(raw, NOW)
    assert result["status"] == "REJECTED_UNTRUSTED_AGGREGATE_CONTRACT"
    assert "counts" not in result


@pytest.mark.parametrize("key,value", [
    ("tenant_binding_verified", True),
    ("original_provider_message_id_checked", True),
    ("read_only_aggregate", False),
    ("window_days", 900),
    ("schema", "other.schema"),
])
def test_untrusted_embedded_claim_is_rejected(key, value):
    raw = _snapshot()
    raw["restricted_reply_lineage"][key] = value
    result = assess_reply_lineage(raw, NOW)
    assert result["status"] == "REJECTED_UNTRUSTED_AGGREGATE_CONTRACT"
    assert "counts" not in result


@pytest.mark.parametrize("key,value", [
    ("reply_records_observed", -1),
    ("reply_records_matched_to_prospect", 12),
    ("reply_records_with_unmatched_intent", 0),
    ("reply_records_observed", True),
])
def test_corrupt_or_mismatched_counts_are_rejected(key, value):
    raw = _snapshot()
    raw["restricted_reply_lineage"][key] = value
    result = assess_reply_lineage(raw, NOW)
    assert result["status"].startswith("REJECTED_")
    assert "counts" not in result


def test_zero_observed_rows_does_not_prove_absence_of_buyer_demand():
    raw = _snapshot()
    for key in (
        "reply_records_observed",
        "reply_records_with_intent_pointer",
        "reply_records_matched_to_intent",
        "reply_records_matched_to_prospect",
        "reply_records_missing_intent_pointer",
        "reply_records_with_unmatched_intent",
        "reply_records_with_unmatched_prospect",
        "positive_classification_records_unverified",
    ):
        raw["restricted_reply_lineage"][key] = 0
    result = assess_reply_lineage(raw, NOW)
    assert result["counts"]["reply_records_observed"] == 0
    assert "NO_REPLY_ROWS_IN_OBSERVED_WINDOW" in result["reason_codes"]
    assert result["buyer_intent_verified"] is False
    assert result["commercial_demand_verified"] is False


def test_naive_clock_refused():
    with pytest.raises(ValueError, match="timezone"):
        assess_reply_lineage(_snapshot(), datetime(2026, 10, 9, 17, 30))
