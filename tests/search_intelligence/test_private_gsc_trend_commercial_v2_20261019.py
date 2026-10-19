"""Read-only private SEO chart release checks never deploy or fake ranks."""
import json

import pytest
from scripts import review_private_gsc_trend_commercial_v2_20261019 as module

BASE = {
    "schema_version": "empire.search_growth.department_integration.v1",
    "status": "DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN",
    "search_rankings_verified": False,
    "realised_revenue_verified": False,
}
CHART = {
    "status": "DATE_DIMENSION_ROWS_OBSERVED",
    "source": "google_search_console_date_dimension",
    "missing_days_treated_as_zero": False,
    "independent_google_rank_positions_verified": False,
    "realised_revenue_verified": False,
    "rows": [{"date":"2026-10-04"},{"date":"2026-10-05"}],
}


def check(backend=None, **kwargs):
    args={
        "source_ok":True,"service_ok":True,
        "old_routes_ok":True,"public_closed":True,
        "backend":BASE if backend is None else backend,
    }
    args.update(kwargs)
    return module.assess(**args)


def test_staged_candidate_waits_for_existing_backend_activation():
    d=check()
    assert d["status"]=="FROZEN_CANDIDATE_GSC_BACKEND_ACTIVATION_PENDING"
    assert d["exact_new_build_verified"] is True
    assert d["active_prior_console_unchanged"] is True
    assert d["daily_api_source_attested"] is False
    assert d["production_changed"] is False
    assert d["execution_authority"]=="NONE"


def test_real_attested_backend_ready_does_not_claim_approval():
    d=check(backend={**BASE,"gsc_daily_chart":CHART})
    assert d["status"]=="FROZEN_CANDIDATE_BACKEND_READY_REQUIRES_FOUNDER_RELEASE_APPROVAL"
    assert d["daily_api_source_attested"] is True
    assert d["no_service_restarted"] is True
    assert d["seo_rankings_verified"] is False
    assert d["realised_revenue_verified"] is False


@pytest.mark.parametrize("override",[
    {"source_ok":False},
    {"service_ok":False},
    {"old_routes_ok":False},
    {"public_closed":False},
    {"backend":{"status":"FAKE_RANKS"}},
    {"backend":{**BASE,"search_rankings_verified":True}},
    {"backend":{**BASE,"realised_revenue_verified":True}},
    {"backend":[]},
])
def test_held_rejects_service_drift_and_public_exposure(override):
    d=check(**override)
    assert d["status"]=="HELD_SOURCE_OWNER_OR_PUBLIC_BOUNDARY"
    assert d["production_changed"] is False


@pytest.mark.parametrize("changed",[
    {"status":"HELD_GSC_DAILY_SOURCE_UNAVAILABLE"},
    {"source":"untrusted_source"},
    {"missing_days_treated_as_zero":True},
    {"independent_google_rank_positions_verified":True},
    {"realised_revenue_verified":True},
    {"rows":[]},
    {"rows":None},
])
def test_unverified_chart_never_promoted(changed):
    c={**CHART,**changed}
    d=check(backend={**BASE,"gsc_daily_chart":c})
    assert d["daily_api_source_attested"] is False
    assert d["status"]=="FROZEN_CANDIDATE_GSC_BACKEND_ACTIVATION_PENDING"


def test_unknown_url_refused_by_preflight():
    assert module._get("http://169.254.169.254/latest/meta-data")==(None,{})
    assert module._get("https://some-other-domain.example/page")==(None,{})


def test_cli_rejects_any_mutating_operation(monkeypatch, capsys):
    monkeypatch.setattr(module,"inspect",lambda:check())
    assert module.main(["--read-only"])==0
    result=json.loads(capsys.readouterr().out)
    assert result["no_service_restarted"] is True
    for arguments in ([],["--apply"],["--restart"],["--publish"],["--read-only","--apply"]):
        with pytest.raises(SystemExit):
            module.main(arguments)
