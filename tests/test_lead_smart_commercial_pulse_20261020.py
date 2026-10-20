"""Truth separation: search impressions, dial-link handoffs, provider rows and payouts."""
from datetime import datetime, timezone
from pathlib import Path
import json
import pytest
from scripts import review_lead_smart_commercial_pulse_20261020 as mod

NOW=datetime(2026,10,20,15,tzinfo=timezone.utc)

def base(tmp_path, enabled=True, handoffs=0):
    control=tmp_path/"control.json"
    control.write_text(json.dumps({
        "campaign_id":"CA8278ed3f26e9495b881fe3833174d007",
        "tracking_number":"+18883579305",
        "enabled":enabled,"mode":"FULL_CAMPAIGN",
        "ends_at":"2026-10-27T13:00:00+00:00",
        "max_daily_site_handoffs":20,"max_site_handoffs":140,
    }))
    ledger=tmp_path/"site_handoffs.json"
    if handoffs:
        ledger.write_text(json.dumps({
            "site_handoffs":handoffs,"local_day":"2026-10-20",
            "daily_site_handoffs":handoffs
        }))
    tracking=tmp_path/"tracking.json"
    tracking.write_text(json.dumps({"verified_at":"2026-10-20T14:04:00+00:00"}))
    return control,ledger,tracking

def make_report(paths, provider=None,gsc=None):
    control,ledger,track=paths
    return mod.pulse(now=NOW,control_path=control,ledger_path=ledger,
        tracking_path=track,
        provider_reader=provider or (lambda:{
            "status":"RESTRICTED_PROVIDER_ROWS_OBSERVED",
            "matching_rows_in_returned_window":1,
            "includes_historical_test_calls":"POSSIBLE",
            "buyer_leg_connected_verified":False,
            "payable_call_verified":False,"settled_revenue_verified":False
        }),
        gsc_reader=gsc or (lambda start,end:{
            "status":"NO_REPORTED_PAGE_ROW","clicks":0,
            "impressions":0,"indexed_in_google_verified":False
        }))

def test_live_campaign_handoff_count_not_equated_with_calls(tmp_path):
    data=make_report(base(tmp_path,handoffs=2))
    assert data["site_handoffs_recorded"]==2
    assert data["site_handoffs_today"]==2
    assert data["ringba"]["matching_rows_in_returned_window"]==1
    assert data["actual_connected_homeowner_calls_verified"] is False
    assert data["settled_revenue_verified"] is False
    assert data["gross_profit_verified"] is False
    assert "NOT connected calls" in data["handoff_metric"]

def test_zero_gsc_rows_do_not_claim_indexability_false_or_human_traffic(tmp_path):
    data=make_report(base(tmp_path))
    assert data["google_search_console"]["status"]=="NO_REPORTED_PAGE_ROW"
    assert data["google_search_console"]["indexed_in_google_verified"] is False
    assert data["site_handoffs_recorded"]==0

def test_no_untrusted_campaign_or_handoff_claim(tmp_path):
    paths=base(tmp_path,enabled=False)
    control,ledger,tracking=paths
    bad=json.loads(control.read_text());bad["campaign_id"]="other"
    control.write_text(json.dumps(bad))
    with pytest.raises(RuntimeError,match="unexpected_campaign"):
        make_report(paths)
    bad["campaign_id"]="CA8278ed3f26e9495b881fe3833174d007"
    control.write_text(json.dumps(bad))
    ledger.write_text(json.dumps({"site_handoffs":-1}))
    with pytest.raises(ValueError,match="invalid_handoff"):
        make_report(paths)

def test_gsc_unknown_not_false_zero_impressions(tmp_path):
    def fail(*args):
        raise RuntimeError("upstream_missing")
    data=make_report(base(tmp_path),gsc=fail)
    assert data["google_search_console"]["status"]=="GSC_UNAVAILABLE"
    assert data["google_search_console"]["impressions"] is None

def test_provider_reader_no_secret_leak_and_no_paid_inference(monkeypatch):
    def simulated(command,**kwargs):
        assert command[:2]==["sudo","-n"]
        assert "RINGBA_API_TOKEN" not in str(command)
        return type("Run",(),{"returncode":0,"stdout":json.dumps({
            "schema_version":"empire.lead_smart.ringba_privileged_one_hit.v1",
            "account_selection_resolved":True,
            "call_log_evidence":{"matching_campaign_number_call_rows":1}
        })})()
    monkeypatch.setattr(mod.subprocess,"run",simulated)
    result=mod.ringba_proof()
    assert result["matching_rows_in_returned_window"]==1
    assert result["provider_token_read_by_unprivileged_process"] is False
    assert result["payable_call_verified"] is False
