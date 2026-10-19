"""Read-only admission readiness must never imply live ingestion."""
import json
import pytest

from scripts import review_empire_analytics_dormant_ingress_20261019 as mod


def source(status):
    return {"status":status,"website_sessions_verified":False}


def test_observed_static_source_prepares_contract_but_never_collects(monkeypatch):
    monkeypatch.setattr(mod,"review_existing_monitor",lambda:source(
        "STATIC_HOMEPAGE_TAG_SOURCE_OBSERVED_COLLECTOR_HELD"))
    d=mod.inspect()
    assert d["status"]=="DORMANT_HTTP_CONTRACT_READY_COLLECTION_NOT_AUTHORISED"
    assert d["http_contract_source_present"] is True
    assert d["http_simulation_requires_local_test_guard"] is True
    for field in ("public_route_mounted_verified","website_analytics_consent_verified",
                  "actual_website_sessions_verified","crm_attribution_verified",
                  "realised_revenue_verified","database_writes","public_website_modified",
                  "tracking_pixels_added","browser_collector_activated"):
        assert d[field] is False


def test_stale_or_invalid_source_fails_closed(monkeypatch):
    monkeypatch.setattr(mod,"review_existing_monitor",lambda:source(
        "HELD_TAG_SOURCE_UNVERIFIED"))
    d=mod.inspect()
    assert d["status"]=="HELD_TAG_INTELLIGENCE_MONITOR_UNVERIFIED"
    assert d["static_page_observation_verified"] is False
    assert d["browser_collector_activated"] is False


def test_only_readonly_operator_flag_supported(monkeypatch,capsys):
    monkeypatch.setattr(mod,"review_existing_monitor",lambda:source(
        "STATIC_HOMEPAGE_TAG_SOURCE_OBSERVED_COLLECTOR_HELD"))
    assert mod.main(["--read-only"])==0
    output=json.loads(capsys.readouterr().out)
    assert output["execution_authority"]=="NONE"
    assert output["mode"]=="READ_ONLY"
    for flag in ([],["--apply"],["--publish"],["--restart"],["--enable-tracking"]):
        with pytest.raises(SystemExit):
            mod.main(flag)
