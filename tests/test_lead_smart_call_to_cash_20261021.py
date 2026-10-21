"""Verify Ringba source proof cannot silently promote connected calls or cash."""
import json
import pytest
from empire_os import lead_smart_ringba_api_observer as api
from scripts.review_lead_smart_call_to_cash_20261021 import (
    opaque_id, safe_seconds, prove_from_observation,
)

def report(**overrides):
    j = {
        "schema_version": api.SCHEMA_VERSION,
        "campaign_id_expected": api.EXPECTED_CAMPAIGN_ID,
        "tracking_number_expected": api.EXPECTED_TRACKING_NUMBER,
        "execution_authority": "NONE",
        "revenue_recognized": False,
        "exact_campaign_and_number_match_count": 1,
        "exact_matches": [{
            "call_id": "real_ringba_call_id_001",
            "dialed_number": api.EXPECTED_TRACKING_NUMBER,
            "connected_seconds": 256,
            "total_seconds": 400,
            "started_at_candidate": "2026-10-16T18:00:00Z",
            "payout_candidate": 134.55,
            "event_names": ["connected", "converted"],
            "raw_persisted": False,
        }],
    }
    return {**j, **overrides}

def test_observed_call_not_invented_payable_or_cash():
    out = prove_from_observation(report(), known_site_handoffs=0)
    assert out["provider_exact_matches_in_bounded_window"] == 1
    assert out["first_party_site_handoffs_recorded"] == 0
    assert out["verified_accepted_payable_calls"] == 0
    assert out["verified_cash_payments"] == 0
    assert out["settled_revenue_usd_verified"] is None
    assert out["provider_buyer_leg_connections_verified"] == 0
    row = out["provider_reported_row_summaries"][0]
    assert row["provider_reported_connected_seconds"] == 256
    assert row["buyer_leg_connection_verified"] is False
    assert row["agreed_payable_amount_usd"] is None
    assert row["paid_amount_usd"] is None
    assert row["test_call_possible"] is True
    assert row["call_id_sha256"].startswith("sha256:")
    blob = json.dumps(out)
    assert "real_ringba_call_id_001" not in blob
    assert row["provider_payout_candidate_unconfirmed"] == 134.55
    assert row["buyer_accepted_payable_call_verified"] is False
    assert '"event_names"' not in blob

@pytest.mark.parametrize("field,bad",[
    ("campaign_id_expected", "different"),
    ("tracking_number_expected", "+15555555555"),
    ("execution_authority", "LIVE_TRAFFIC"),
    ("revenue_recognized", True),
    ("schema_version", "untrusted")
])
def test_untrusted_report_fails_closed(field, bad):
    with pytest.raises(ValueError):
        prove_from_observation(report(**{field:bad}), known_site_handoffs=0)

def test_duplicate_ids_fail_and_missing_ids_remain_opaque():
    j = report()
    j["exact_matches"].append(dict(j["exact_matches"][0]))
    j["exact_campaign_and_number_match_count"] = 2
    with pytest.raises(ValueError, match="duplicate"):
        prove_from_observation(j, known_site_handoffs=0)
    j["exact_matches"][1]["call_id"] = None
    out = prove_from_observation(j, known_site_handoffs=0)
    assert out["provider_reported_row_summaries"][1]["call_id_sha256"] is None
    assert not out["call_details_authenticated_as_buyer_connected"]

@pytest.mark.parametrize("seconds",[-3, True, "unknown", 1.5, float("nan"), None])
def test_untrustworthy_duration_is_absent(seconds):
    assert safe_seconds(seconds) is None

def test_missing_handoff_ledger_is_not_confirmed_as_zero():
    with pytest.raises(ValueError):
        prove_from_observation(report(), known_site_handoffs=None)

def test_no_rows_is_not_revenue():
    out = prove_from_observation(report(
        exact_matches=[],exact_campaign_and_number_match_count=0), known_site_handoffs=0)
    assert out["verified_accepted_payable_calls"] == 0
    assert out["settled_revenue_usd_verified"] is None
