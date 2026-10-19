"""Source-only, owner-fenced Empire Analytics release preflight contract."""
import json
import pytest
from scripts import review_empire_analytics_private_release_20261019 as module

BACKEND={
 "schema_version":"empire.search_growth.department_integration.v1",
 "status":"DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN",
 "search_rankings_verified":False,
 "realised_revenue_verified":False,
 "gsc_daily_chart":{
  "source":"google_search_console_date_dimension",
  "status":"DATE_DIMENSION_ROWS_OBSERVED",
  "independent_google_rank_positions_verified":False,
  "realised_revenue_verified":False,
 },
}

def check(**changes):
    args={"frozen":True,"prior":True,"old_routes":True,"public_closed":True,"backend":BACKEND}
    args.update(changes)
    return module.assess(**args)

def test_exact_existing_runtime_and_real_source_required():
    r=check()
    assert r["status"]=="FROZEN_BRANDED_ANALYTICS_READY_FOR_FOUNDER_RELEASE"
    assert r["frozen_brand_and_source_verified"] is True
    assert r["ten_existing_routes_healthy"] is True
    assert r["public_department_routes_closed"] is True
    assert r["visitor_analytics_connected"] is False
    assert r["gsc_is_website_sessions"] is False
    assert r["revenue_verified"] is False
    assert r["service_restarted"] is False
    assert r["production_changed"] is False

@pytest.mark.parametrize("changes",[
 {"frozen":False},
 {"prior":False},
 {"old_routes":False},
 {"public_closed":False},
 {"backend":{}},
 {"backend":{"schema_version":"untrusted"}},
 {"backend":{**BACKEND,"search_rankings_verified":True}},
 {"backend":{**BACKEND,"realised_revenue_verified":True}},
 {"backend":{**BACKEND,"gsc_daily_chart":None}},
 {"backend":{**BACKEND,"gsc_daily_chart":{**BACKEND["gsc_daily_chart"],"status":"HELD"}}},
 {"backend":{**BACKEND,"gsc_daily_chart":{**BACKEND["gsc_daily_chart"],"independent_google_rank_positions_verified":True}}},
])
def test_release_fails_closed_on_false_claim_or_owner_change(changes):
    r=check(**changes)
    assert r["status"]=="HOLD_BRANDED_ANALYTICS_OWNER_OR_SOURCE"
    assert r["production_changed"] is False

def test_unknown_urls_are_not_probed():
    assert module.get("http://169.254.169.254/latest/meta-data")==(None,{})
    assert module.get("https://example.com/collect")==(None,{})

def test_cli_is_strictly_read_only(monkeypatch,capsys):
    monkeypatch.setattr(module,"inspect",lambda:check())
    assert module.main(["--read-only"])==0
    d=json.loads(capsys.readouterr().out)
    assert d["execution_authority"]=="NONE"
    for arg in ([],["--apply"],["--restart"],["--publish"],["--read-only","--apply"]):
        with pytest.raises(SystemExit):
            module.main(arg)
