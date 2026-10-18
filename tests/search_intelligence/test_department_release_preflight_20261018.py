"""Private SEO dashboard source and release-gate checks. No deployments."""
import json

import pytest

from scripts import review_search_department_release_preflight_20261018 as unit

HEALTH = {
    "service":"search-intelligence-api","mode":"OBSERVE",
    "execution_allowed":False,
}
DEPT = {
    "schema":"empire.search_growth.department_integration.v1",
    "mode":"OBSERVE", "status":"DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN",
    "rankings_verified":False, "revenue_verified":False,
    "cache_control":"no-store",
}


def assess(**overrides):
    args = {
        "source":True,
        "health_code":200,
        "health":HEALTH,
        "department_code":404,
        "department":{},
        "public_api":404,
        "public_page":404,
    }
    args.update(overrides)
    return unit.assess(**args)


def test_read_only_source_ready_requires_separate_restart():
    r=assess()
    assert r["status"]=="API_SOURCE_READY_RESTART_REQUIRES_APPROVAL"
    assert r["existing_loopback_api_restart_required"] is True
    assert r["new_department_route_active"] is False
    assert r["dashboard_production_publication_authorized"] is False
    assert r["dashboard_private_identity_gate_verified"] is False
    assert r["systemd_restarted"] is False
    assert r["database_writes"] is False


def test_existing_loopback_api_live_with_exact_data_is_not_dashboard_permission():
    r=assess(department_code=200,department=DEPT)
    assert r["status"]=="PRIVATE_API_ACTIVE_DASHBOARD_DEPLOY_HELD"
    assert r["new_department_route_active"] is True
    assert r["dashboard_private_identity_gate_verified"] is False
    assert r["search_rankings_verified"] is False


@pytest.mark.parametrize("kwargs",[
    {"source":False},
    {"health_code":503},
    {"health":{"service":"search-intelligence-api","mode":"ACTIVE","execution_allowed":True}},
    {"department_code":500},
    {"department_code":200,"department":{"status":"FAKE_RANKS"}},
    {"department_code":200,"department":{**DEPT,"rankings_verified":True}},
    {"department_code":200,"department":{**DEPT,"cache_control":"public"}},
    {"public_api":200},
    {"public_page":200},
    {"public_page":302},
    {"public_page":None},
    {"public_api":None},
])
def test_untrusted_source_or_exposure_fails_closed(kwargs):
    r=assess(**kwargs)
    assert r["status"]=="HELD_RELEASE_PRECONDITIONS_NOT_VERIFIED"
    assert r["new_department_route_active"] is False
    assert r["dashboard_production_publication_authorized"] is False


def test_unknown_url_never_requested(monkeypatch):
    assert unit.status_get("http://169.254.169.254/latest/metadata")== (None,{})
    assert unit.status_get("https://example.com/private")== (None,{})


def test_git_source_contract_rejects_wrong_unit(tmp_path):
    fake=tmp_path/"unit.service"
    fake.write_text("[Service]\nUser=root\nExecStart=/usr/bin/false")
    assert unit.source_ready(root=tmp_path,unit=fake) is False


def test_cli_read_only_is_mandatory(monkeypatch,capsys):
    monkeypatch.setattr(unit,"inspect",lambda:assess())
    assert unit.main(["--read-only"])==0
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="API_SOURCE_READY_RESTART_REQUIRES_APPROVAL"
    for args in ([],["--apply"],["--restart"],["--read-only","--publish"]):
        with pytest.raises(SystemExit):
            unit.main(args)


def test_rejected_read_never_leaks_server_error(monkeypatch,capsys):
    monkeypatch.setattr(unit,"inspect",lambda:assess(source=False))
    assert unit.main(["--read-only"])==2
    d=json.loads(capsys.readouterr().out)
    assert d["status"]=="HELD_RELEASE_PRECONDITIONS_NOT_VERIFIED"
    assert d["execution_authority"]=="NONE"
