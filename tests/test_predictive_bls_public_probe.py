"""BLS public one-shot source observation is not finance-source approval."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json

import pytest

from empire_os.predictive_bls_public_probe import (
    SERIES_ID, API_URL, review_public_bls_v1_response, probe_bls_public_v1,
)

NOW=datetime(2026,10,20,12,tzinfo=timezone.utc)


def api_packet():
    return {
        "status":"REQUEST_SUCCEEDED","message":[],
        "Results":{"series":[{"seriesID":SERIES_ID,"data":[
            {"year":"2026","period":"M09","value":"110.2",
             "footnotes":[{"code":"P","text":"Preliminary"}]},
            {"year":"2025","period":"M09","value":"100.0",
             "footnotes":[{}]},
        ]}]},
    }


def test_valid_monthly_original_source_remains_research_only():
    result=review_public_bls_v1_response(api_packet(),as_of=NOW)
    assert result["status"]=="BLS_PUBLIC_MONTHLY_INDEX_OBSERVED_RESEARCH_ONLY"
    assert result["source_last_month"]=="2026-09"
    assert result["latest_published_index"]=="110.2"
    assert result["prior_year_comparable_index"]=="100.0"
    assert result["published_index_yoy_percent"]==10.2
    assert result["reported_preliminary"] is True
    assert result["source_data_points"]==2
    assert result["independent_finance_source_owner_approval"] is False
    assert result["company_material_cost_or_profit_verified"] is False
    assert result["original_supplier_quote_authenticated"] is False
    assert result["market_specific_cost_model_calibration_allowed"] is False
    assert result["database_writes"] is False
    assert result["source_files_written"] is False
    assert result["outbound_sent"] is False


@pytest.mark.parametrize("alter",[
    ("status","REQUEST_FAILED"), ("message",["warning"]),
])
def test_api_status_or_warning_rejected(alter):
    x=api_packet();x[alter[0]]=alter[1]
    assert review_public_bls_v1_response(x,as_of=NOW)["status"]=="BLS_PUBLIC_SOURCE_PROBE_HOLD"


@pytest.mark.parametrize("field,value",[
    ("seriesID","PCU999999999"),("data",[]),
])
def test_wrong_series_or_empty_observation_hold(field,value):
    x=api_packet();x["Results"]["series"][0][field]=value
    assert review_public_bls_v1_response(x,as_of=NOW)["status"]=="BLS_PUBLIC_SOURCE_PROBE_HOLD"


@pytest.mark.parametrize("field,value",[
    ("year","2030"),("period","M14"),("value","nan"),("value","0"),
    ("value","$100"),("value","-100"),("footnotes",None),
])
def test_untrusted_source_value_never_enters_profit_model(field,value):
    x=api_packet();x["Results"]["series"][0]["data"][0][field]=value
    out=review_public_bls_v1_response(x,as_of=NOW)
    assert out["status"]=="BLS_PUBLIC_SOURCE_PROBE_HOLD"
    assert out["market_specific_cost_model_calibration_allowed"] is False


def test_missing_prior_year_does_not_invent_zero_growth():
    x=api_packet()
    x["Results"]["series"][0]["data"].pop()
    r=review_public_bls_v1_response(x,as_of=NOW)
    assert r["status"]=="BLS_PUBLIC_SOURCE_PROBE_HOLD"
    assert r["published_index_yoy_percent"] is None


def test_data_date_is_checked_separately_from_fetch_clock():
    out=review_public_bls_v1_response(api_packet(),as_of=NOW+timedelta(days=250))
    assert out["status"]=="BLS_PUBLIC_SOURCE_PROBE_HOLD"


def test_no_http_call_unless_user_explicitly_sets_probe_flag(monkeypatch,capsys):
    import scripts.review_predictive_multi_index_cost_pressure_20261020 as cli
    called=[]
    def no_fetch(*,as_of):
        called.append(1)
        return {"status":"BLS_PUBLIC_SOURCE_PROBE_HOLD"}
    monkeypatch.setattr(cli,"probe_bls_public_v1",no_fetch)
    monkeypatch.setattr("sys.argv",["probe","--read-only"])
    cli.main()
    out=json.loads(capsys.readouterr().out)
    assert called==[]
    assert out["official_bls_public_research_probe"] is None
    assert out["bls_source_status"]=="BLS_OWNER_SOURCE_NOT_CONNECTED"


def test_probe_flag_does_not_grant_finance_approval(monkeypatch,capsys):
    import scripts.review_predictive_multi_index_cost_pressure_20261020 as cli
    called=[]
    def permitted(*,as_of):
        called.append(True)
        return review_public_bls_v1_response(api_packet(),as_of=NOW)
    monkeypatch.setattr(cli,"probe_bls_public_v1",permitted)
    monkeypatch.setattr("sys.argv",["probe","--read-only","--probe-official-bls-v1"])
    cli.main()
    out=json.loads(capsys.readouterr().out)
    assert called==[True]
    assert out["status"]=="OFFICIAL_BLS_PUBLIC_RESEARCH_OBSERVED_OWNER_APPROVAL_REQUIRED"
    assert out["public_research_source_is_finance_owner_approved"] is False
    assert out["hypothetical_scenario_review"] is None
    assert out["bls_series_count"] is None
    assert out["database_writes"] is False


def test_probe_fixed_https_url_and_single_bounded_read(monkeypatch):
    import empire_os.predictive_bls_public_probe as mod
    class Response:
        def __init__(self): self.calls=0
        def geturl(self): return API_URL
        def read(self,n):
            self.calls+=1
            assert n==mod.MAX_BYTES+1
            return json.dumps(api_packet()).encode()
        def __enter__(self): return self
        def __exit__(self,*args): return False
    call=[]
    item=Response()
    def mock_urlopen(req,timeout):
        assert req.full_url==API_URL
        assert timeout==10
        call.append(1)
        return item
    monkeypatch.setattr(mod,"urlopen",mock_urlopen)
    out=probe_bls_public_v1(as_of=NOW)
    assert out["status"]=="BLS_PUBLIC_MONTHLY_INDEX_OBSERVED_RESEARCH_ONLY"
    assert call==[1] and item.calls==1


def test_redirect_to_unexpected_hostname_fail_closed(monkeypatch):
    import empire_os.predictive_bls_public_probe as mod
    class Response:
        def geturl(self): return "https://example.org/fake"
        def __enter__(self): return self
        def __exit__(self,*args): return False
    monkeypatch.setattr(mod,"urlopen",lambda *a,**k:Response())
    out=probe_bls_public_v1(as_of=NOW)
    assert out["hold_code"]=="BLS_UNEXPECTED_API_REDIRECT"


def test_bls_m13_annual_rows_are_excluded_not_treated_as_december():
    x=api_packet()
    x["Results"]["series"][0]["data"].append({
        "year":"2025","period":"M13","periodName":"Annual",
        "value":"999.9","footnotes":[],
    })
    out=review_public_bls_v1_response(x,as_of=NOW)
    assert out["status"]=="BLS_PUBLIC_MONTHLY_INDEX_OBSERVED_RESEARCH_ONLY"
    assert out["published_index_yoy_percent"]==10.2
    assert out["annual_m13_points_excluded_from_monthly_analysis"]==1
    assert out["source_data_points"]==2


def test_untrusted_m13_annual_classification_cannot_bypass_validation():
    x=api_packet()
    x["Results"]["series"][0]["data"].append({
        "year":"2025","period":"M13","periodName":"December",
        "value":"999.9","footnotes":[],
    })
    out=review_public_bls_v1_response(x,as_of=NOW)
    assert out["status"]=="BLS_PUBLIC_SOURCE_PROBE_HOLD"
