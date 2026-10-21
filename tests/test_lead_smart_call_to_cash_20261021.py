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


def test_write_latest_requires_root(monkeypatch, tmp_path):
    from scripts import review_lead_smart_call_to_cash_20261021 as c
    monkeypatch.setattr(c.os, "geteuid", lambda: 1000)
    value = prove_from_observation(report(), known_site_handoffs=0)
    with pytest.raises(PermissionError):
        c.write_latest(value, path=tmp_path/"latest.json")
    assert not (tmp_path/"latest.json").exists()


def test_persisted_observation_is_permission_sealed(monkeypatch,tmp_path):
    from scripts import review_lead_smart_call_to_cash_20261021 as c
    monkeypatch.setattr(c.os, "geteuid", lambda: 0)
    val = prove_from_observation(report(), known_site_handoffs=0)
    p = tmp_path/"latest.json"
    c.write_latest(val,path=p)
    assert p.stat().st_mode & 0o777 == 0o600
    assert json.loads(p.read_text())["verified_cash_payments"]==0
    assert "real_ringba_call_id_001" not in p.read_text()
    p.chmod(0o644)
    with pytest.raises(PermissionError):
        c.write_latest(val,path=p)


def test_ringba_detail_connected_event_does_not_prove_buyer_or_payout():
    from scripts.review_lead_smart_call_to_cash_20261021 import detail_by_call_id
    cid = "real_ringba_call_id_001"
    raw = {
        "isSuccessful": True,
        "report": {"records": [{
            "inboundCallId": cid,
            "campaignId": api.EXPECTED_CAMPAIGN_ID,
            "number": api.EXPECTED_TRACKING_NUMBER,
            "hasConnected": True,
            "isDuplicate": True,
            "connectedCallLengthInSeconds": 32,
            "callLengthInSeconds": 48,
            "inboundPhoneNumber": "+19995550000",
            "recordingUrl": "https://private-recording.invalid",
            "events": [{"name": "ConnectedCall", "callConnectionDt": 1},
                       {"name": "CompletedCall"}],
        }]},
    }
    stripped = detail_by_call_id(raw, expected_ids=[cid])
    assert stripped[cid]["provider_connected_call_event_verified"] is True
    assert stripped[cid]["provider_duplicate_flag_observed"] is True
    result = prove_from_observation(report(), known_site_handoffs=0,
                                    detail_report=raw)
    assert result["provider_connected_call_events_observed"] == 1
    assert result["provider_buyer_leg_connections_verified"] == 0
    assert result["verified_accepted_payable_calls"] == 0
    assert result["verified_cash_payments"] == 0
    assert result["provider_reported_row_summaries"][0][
        "provider_buyer_destination_identity_verified"] is False
    blob = json.dumps(result)
    assert "+19995550000" not in blob
    assert "private-recording" not in blob
    assert cid not in blob


@pytest.mark.parametrize("damage", [
    {"isSuccessful": False},
    {"report": {"records": []}},
    {"report": {"records": [{"inboundCallId": "unexpected"}]}},
])
def test_unreliable_detail_cannot_promote_connection(damage):
    from scripts.review_lead_smart_call_to_cash_20261021 import detail_by_call_id
    base = {"isSuccessful": True, "report": {"records": []}}
    with pytest.raises(ValueError):
        detail_by_call_id({**base, **damage},
                          expected_ids=["real_ringba_call_id_001"])
