"""Existing two-hop production gateways stay unmounted by default."""
from __future__ import annotations

from scripts import review_data_brokerage_premium_gateway_20261018 as p

def source():
    return {
        "status":"PREMIUM_DISCOVERY_FEATURE_TESTED_RELEASE_HELD",
        "premium_unpriced_proposals":2,
        "production_premium_route_mounted":False,
        "production_api_changed":False,"database_writes":False,
        "payment_activated":False,
    }

def test_feature_is_unmounted_and_preflight_is_a_hold_not_a_deployment():
    r=p.inspect(preflight=source,paths=lambda:(
        {"/v1/checkout/commercial/offers"},
        {"/v1/commercial/interests"},
    ))
    assert r["status"]=="TWO_HOP_PREMIUM_GATEWAY_ADAPTER_READY_RELEASE_HELD"
    assert r["production_route_published"] is False
    assert r["real_buyer_enquiry_verified"] is False
    assert r["buyer_to_founder_crm_verified"] is False
    assert r["production_crm_delivery_proven"] is False
    assert r["payment_activated"] is False
    assert r["crm_records_created"]==0

def test_unapproved_source_or_existing_route_drift_blocks_success():
    for key,value in (
        ("status","LIVE"),
        ("premium_unpriced_proposals",1),
        ("production_premium_route_mounted",True),
        ("database_writes",True),
        ("payment_activated",True),
    ):
        values=source();values[key]=value
        r=p.inspect(preflight=lambda:values,
                    paths=lambda:(set(),set()))
        assert r["status"].startswith("HOLD")
    for routes in (
        ({p.PUBLIC_PATH},set()),
        (set(),{p.PRIVATE_PATH}),
        ({p.PUBLIC_PATH},{p.PRIVATE_PATH}),
    ):
        r=p.inspect(preflight=source,paths=lambda:routes)
        assert r["status"].startswith("HOLD")
        assert r["failure_stage"]=="LIVE_ROUTE_ALREADY_CHANGED_NEEDS_SEPARATE_AUDIT"

def test_exceptions_fail_closed_without_secrets():
    def fail():
        raise RuntimeError("INTERNAL_PRIVATE_DATABASE_PASSPHRASE")
    r=p.inspect(preflight=fail)
    assert r["status"].startswith("HOLD")
    assert "INTERNAL_PRIVATE" not in str(r)

def test_no_flag_no_read_or_route_import(monkeypatch,capsys):
    monkeypatch.setattr(p,"inspect",lambda:(_ for _ in ()).throw(
        AssertionError("no source reads allowed without flag")))
    assert p.main([])==2
    assert "HOLD_EXPLICIT_READ_ONLY_FLAG_REQUIRED" in capsys.readouterr().out
