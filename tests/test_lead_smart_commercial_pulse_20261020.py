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
        "starts_at":"2026-10-20T13:00:00+00:00",
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

def make_report(paths, provider=None,gsc=None, now=NOW):
    control,ledger,track=paths
    return mod.pulse(now=now,control_path=control,ledger_path=ledger,
        tracking_path=track,
        provider_reader=provider or (lambda:{
            "status":"RESTRICTED_PROVIDER_ROWS_OBSERVED",
            "matching_rows_in_returned_window":1,
            "includes_historical_test_calls":"POSSIBLE",
            "buyer_leg_connected_verified":False,
            "payable_call_verified":False,"settled_revenue_verified":False
        }),
        zip_request_reader=lambda **kwargs:{
            "status":"TEST_INJECTED_OPERATIONAL_COUNTS",
            "http_post_requests":0,
            "unique_homeowner_visitors_verified":False,
        },
        content_request_reader=lambda **kwargs:{
            "status":"TEST_INJECTED_OPERATIONAL_COUNTS",
            "landing_get_requests":0,
            "guide_get_requests":0,
            "unique_homeowner_visitors_verified":False,
            "consented_sessions_verified":False,
            "landing_to_zip_conversion_verified":False,
        },
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

def test_caller_local_overlap_never_clears_expired_traffic_window(tmp_path):
    from datetime import datetime,timezone
    clock=datetime(2026,11,11,19,0,tzinfo=timezone.utc)
    report=make_report(base(tmp_path,enabled=True),now=clock)
    h=report["buyer_hours_and_campaign_window"]
    assert h["all_fifty_state_reported_clocks_in_window"] is True
    assert h["campaign_window_state"]=="EXPIRED"
    assert h["reported_timezone_policy"]=="CALLER_LOCAL_NOT_UNIVERSAL_CHICAGO"
    assert h["actual_live_call_authorized"] is False
    assert h["current_buyer_capacity_verified"] is False
    assert h["fresh_founder_campaign_window_authorized"] is False
    assert report["site_handoff_switch_enabled"] is True
    assert report["actual_connected_homeowner_calls_verified"] is False


def test_chicago_open_while_pacific_closed_does_not_imply_nationwide(tmp_path):
    clock=datetime(2026,11,11,14,23,tzinfo=timezone.utc)
    report=make_report(base(tmp_path,enabled=False),now=clock)
    h=report["buyer_hours_and_campaign_window"]
    assert h["all_fifty_state_reported_clocks_in_window"] is False
    assert h["campaign_window_state"]=="EXPIRED"
    assert h["actual_live_call_authorized"] is False


def test_invalid_founder_campaign_dates_are_observed_as_held(tmp_path):
    clock=datetime(2026,11,11,19,0,tzinfo=timezone.utc)
    paths=base(tmp_path)
    control=paths[0]
    d=json.loads(control.read_text())
    d["ends_at"]="unparseable"
    control.write_text(json.dumps(d))
    h=make_report(paths,now=clock)["buyer_hours_and_campaign_window"]
    assert h["campaign_window_state"]=="INVALID_WINDOW_HELD"
    assert h["actual_live_call_authorized"] is False


def test_readonly_reporting_open_clock_does_not_require_customer_identifiers():
    clock=datetime(2026,11,11,19,0,tzinfo=timezone.utc)
    status=mod.buyer_hours_and_campaign_window(now=clock,control={
        "starts_at":"2026-11-11T18:00:00+00:00",
        "ends_at":"2026-11-11T22:00:00+00:00",
        "enabled":True,
    })
    assert status["campaign_window_state"]=="IN_WINDOW"
    assert status["all_fifty_state_reported_clocks_in_window"] is True
    assert status["actual_live_call_authorized"] is False
    assert status["buyer_route_and_ani_verified"] is False
    assert status["independent_recording_compliance_verified"] is False
    assert status["source_refs"]==[
        "gmail:1a12229d9d3ffe75","gmail:1a15ea2dfa8c46b1"]

def test_zip_http_counts_reuse_existing_gateway_without_claiming_homeowners():
    log=(
        'INFO:     [private-client] - "POST /roofing/coverage-check HTTP/1.1" 200 OK\n'
        'INFO:     [private-client] - "POST /roofing/coverage-check HTTP/1.1" 422 Unprocessable Entity\n'
        'INFO:     [private-client] - "POST /roofing/coverage-check HTTP/1.1" 503 Service Unavailable\n'
    )
    commands=[]
    def runner(command,**kwargs):
        commands.append((command,kwargs))
        return type("Result",(),{"returncode":0,"stdout":log})()
    result=mod.zip_check_http_request_observation(now=NOW,runner=runner)
    assert result["status"]=="HTTP_REQUEST_COUNTS_ONLY_NOT_VISITORS"
    assert result["http_post_requests"]==3
    assert result["http_200_guidance_responses"]==1
    assert result["http_4xx_responses"]==1
    assert result["http_5xx_responses"]==1
    assert result["unique_homeowner_visitors_verified"] is False
    assert result["source_attribution_verified"] is False
    assert result["includes_operator_tests_or_bots_possible"] is True
    assert result["raw_addresses_or_property_zips_exported"] is False
    assert commands[0][0][0]=="journalctl"
    assert commands[0][0][1]=="--unit=empire-public-gateway.service"
    assert commands[0][1]["timeout"]==12


def test_zip_http_reader_fails_closed_on_unverified_log_format():
    def runner(command,**kwargs):
        return type("Result",(),{"returncode":0,"stdout":"fake ZIP body /roofing/coverage-check\n"})()
    result=mod.zip_check_http_request_observation(now=NOW,runner=runner)
    assert result["status"]=="HTTP_JOURNAL_LOG_FORMAT_UNVERIFIED"
    assert result["http_post_requests"] is None


@pytest.mark.parametrize("rc,output",[(1,""),(0,"x"* (mod.MAX_ZIP_JOURNAL_BYTES+1))])
def test_zip_http_reader_does_not_report_partial_count(rc,output):
    def runner(command,**kwargs):
        return type("Result",(),{"returncode":rc,"stdout":output})()
    result=mod.zip_check_http_request_observation(now=NOW,runner=runner)
    assert result["status"]=="HTTP_JOURNAL_UNAVAILABLE_OR_UNBOUNDED"
    assert result["http_post_requests"] is None


def test_commercial_pulse_http_requests_never_count_as_site_handoffs(tmp_path):
    report=make_report(base(tmp_path,handoffs=0))
    assert report["zip_check_http_operational_requests"]["http_post_requests"]==0
    assert report["site_handoffs_recorded"]==0
    assert report["actual_connected_homeowner_calls_verified"] is False
    assert report["settled_revenue_verified"] is False


def test_roofing_html_gateway_counts_separate_main_page_and_existing_guides():
    log=(
        'INFO: [private-client] - "GET /roofing HTTP/1.1" 200 OK\n'
        'INFO: [private-client] - "GET /roofing?utm_medium=organic HTTP/1.1" 200 OK\n'
        'INFO: [private-client] - "GET /roofing/installation-checklist HTTP/1.1" 200 OK\n'
        'INFO: [private-client] - "GET /roofing/replacement-vs-repair HTTP/1.1" 404 Not Found\n'
    )
    calls=[]
    def runner(command,**kwargs):
        calls.append(command)
        return type("Result",(),{"returncode":0,"stdout":log})()
    d=mod.roofing_content_http_request_observation(now=NOW,runner=runner)
    assert d["status"]=="HTTP_REQUEST_COUNTS_ONLY_NOT_VISITORS"
    assert d["landing_get_requests"]==2
    assert d["guide_get_requests"]==2
    assert d["http_200_responses"]==3
    assert d["http_4xx_responses"]==1
    assert d["http_5xx_responses"]==0
    assert d["cdn_cache_hits_unobserved"] is True
    assert d["source_attribution_verified"] is False
    assert d["landing_to_zip_conversion_verified"] is False
    assert d["raw_addresses_queries_or_referrers_exported"] is False
    assert len(calls)==1
    assert all("utm_medium=organic" not in str(v) for v in d.values())


def test_roofing_html_gateway_count_fails_closed_on_unknown_traffic():
    log='INFO: [private-client] - "GET /roofing-hero.webp HTTP/1.1" 200 OK\n'
    def runner(command,**kwargs):
        return type("Result",(),{"returncode":0,"stdout":log})()
    d=mod.roofing_content_http_request_observation(now=NOW,runner=runner)
    assert d["status"]=="HTTP_JOURNAL_LOG_FORMAT_UNVERIFIED"
    assert d["landing_get_requests"] is None


def test_roofing_html_gateway_count_preserves_unknown_when_journal_unavailable():
    def runner(command,**kwargs):
        return type("Result",(),{"returncode":1,"stdout":""})()
    d=mod.roofing_content_http_request_observation(now=NOW,runner=runner)
    assert d["status"]=="HTTP_JOURNAL_UNAVAILABLE_OR_UNBOUNDED"
    assert d["guide_get_requests"] is None
    assert d["unique_homeowner_visitors_verified"] is False


def test_roofing_html_observation_never_claims_a_consented_funnel(tmp_path):
    report=make_report(base(tmp_path))
    metric=report["roofing_content_http_operational_requests"]
    assert metric["landing_get_requests"]==0
    assert metric["guide_get_requests"]==0
    assert report["site_handoffs_recorded"]==0
    assert metric["consented_sessions_verified"] is False
    assert metric["landing_to_zip_conversion_verified"] is False
    assert report["settled_revenue_verified"] is False



def test_guide_gsc_rows_use_same_original_page_reader_without_revenue_claims(monkeypatch):
    from io import BytesIO
    from datetime import datetime
    packet={
        "available":True,"site_url":"sc-domain:empire-ai.co.uk",
        "data_state":"final",
        "items":[
            {"keys":[mod.CANONICAL],"clicks":1,"impressions":9},
            {"keys":[mod.GUIDES[0]],"clicks":2,"impressions":18},
            {"keys":[mod.GUIDES[1]],"clicks":0,"impressions":4},
        ],
    }
    seen=[]
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,n):return json.dumps(packet).encode()
    def fake_open(req,timeout):
        seen.append((req.full_url,timeout))
        return Response()
    monkeypatch.setattr(mod,"urlopen",fake_open)
    result=mod.gsc_pages("2026-11-11","2026-11-20")
    assert len(seen)==1
    assert "search-console/pages?" in seen[0][0]
    assert result["clicks"]==1 and result["impressions"]==9
    guides=result["guide_observations"]
    assert guides["status"]=="PAGE_DIMENSION_GUIDES_REVIEWED"
    assert guides["gsc_period_end_precedes_guide_publication"] is False
    assert [(x["clicks"],x["impressions"]) for x in guides["pages"]]==[(2,18),(0,4)]
    assert all(x["indexed_in_google_verified"] is False for x in guides["pages"])
    assert guides["consented_enquiries_verified"] is False
    assert guides["real_sales_verified"] is False


def test_missing_guide_rows_before_release_are_unknown_not_zero(monkeypatch):
    packet={"available":True,"site_url":"sc-domain:empire-ai.co.uk",
            "data_state":"final",
            "items":[{"keys":[mod.CANONICAL],"clicks":0,"impressions":2}]}
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,n):return json.dumps(packet).encode()
    monkeypatch.setattr(mod,"urlopen",lambda *args,**kwargs:Response())
    d=mod.gsc_pages("2026-10-28","2026-11-10")
    assert d["guide_observations"]["gsc_period_end_precedes_guide_publication"] is True
    assert all(x["status"]=="NO_REPORTED_PAGE_ROW" for x in d["guide_observations"]["pages"])
    assert all(x["impressions"] is None and x["clicks"] is None
               for x in d["guide_observations"]["pages"])
    assert d["indexed_in_google_verified"] is False
    assert d["impressions"]==2


def test_invalid_guide_metrics_fail_closed_on_source_corruption(monkeypatch):
    packet={"available":True,"site_url":"sc-domain:empire-ai.co.uk",
            "data_state":"final","items":[
                {"keys":[mod.GUIDES[0]],"clicks":-1,"impressions":30}]}
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,n):return json.dumps(packet).encode()
    monkeypatch.setattr(mod,"urlopen",lambda *args,**kwargs:Response())
    with pytest.raises(ValueError,match="gsc_guide_row_invalid"):
        mod.gsc_pages("2026-11-11","2026-11-20")


def test_gsc_outage_does_not_invent_guide_traffic_or_crm_sales(tmp_path):
    def down(*args):raise RuntimeError("provider_outage")
    report=make_report(base(tmp_path,enabled=False),gsc=down)
    guides=report["google_search_console_guides"]
    assert guides["status"]=="NO_VERIFIED_GUIDE_PAGE_EVIDENCE"
    assert len(guides["pages"])==2
    assert all(x["impressions"] is None for x in guides["pages"])
    assert guides["consented_enquiries_verified"] is False
    assert guides["real_sales_verified"] is False
    assert report["site_handoffs_recorded"]==0
    assert report["settled_revenue_verified"] is False
