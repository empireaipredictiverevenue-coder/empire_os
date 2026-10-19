"""End-to-end HTTP simulation with an independent offline session ledger."""
from datetime import datetime, timezone
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.analytics.dormant_event_ingress import (
    build_dormant_event_ingress, PATH,
    TEST_GUARD_NAME, TEST_GUARD_VALUE,
)
from empire_os.analytics.offline_session_authority import (
    OfflineSessionAuthority, ORIGIN,
)

NOW=datetime(2026,10,19,11,tzinfo=timezone.utc)
POLICY="draft-analytics-20261019"
HEADERS={
    "origin":ORIGIN,"sec-fetch-site":"same-origin",
    "content-type":"application/json",
}

def setup(*, allow_tracking=True):
    ledger=OfflineSessionAuthority(
        policy_revision=POLICY,
        resolve_trusted_acquisition=lambda:(
            "organic_search","server_verified_referral"),
        clock=lambda:NOW,enable_offline_simulation=True,
    )
    nonce=ledger.open_session(site=ORIGIN)
    app=FastAPI()
    app.include_router(build_dormant_event_ingress(
        allow_local_test_simulation=True,approved_paths=["/"],
        resolve_server_consent=ledger.resolve_consent,
        resolve_server_channel=ledger.resolve_acquisition,
        clock=lambda:NOW,
    ))
    c=TestClient(app,client=("127.0.0.1",37171))
    if allow_tracking:
        ledger.decide(session_nonce=nonce,decision="granted",
            trusted_server_decision=True,policy_revision=POLICY)
    payload={"events":[{
        "event_nonce":"1"*32,"session_nonce":nonce,
        "event_type":"page_view","occurred_at":"2026-10-19T11:00:00Z",
        "page_path":"/",
    }]}
    return c,ledger,nonce,payload


def test_no_consent_yields_zero_accepted_http_events(monkeypatch):
    monkeypatch.setenv(TEST_GUARD_NAME,TEST_GUARD_VALUE)
    c,ledger,nonce,payload=setup(allow_tracking=False)
    r=c.post(PATH,json=payload,headers=HEADERS)
    assert r.status_code==422
    assert r.json()["accepted"] is False
    assert not ledger.resolve_consent(nonce)


def test_granted_consent_allows_test_simulation_not_real_traffic(monkeypatch):
    monkeypatch.setenv(TEST_GUARD_NAME,TEST_GUARD_VALUE)
    c,ledger,nonce,payload=setup()
    r=c.post(PATH,json=payload,headers=HEADERS)
    assert r.status_code==200
    assert r.json()["simulation_only"] is True
    d=r.json()["simulation"]
    assert d["simulated_sessions"]==1
    assert d["simulated_page_views"]==1
    assert d["real_visitors_verified"] is False
    assert d["crm_conversion_verified"] is False
    assert d["realised_revenue_verified"] is False
    assert d["production_ingestion_enabled"] is False
    assert d["consent_source"]=="injected_server_side_resolver_simulated"
    assert nonce not in r.text


def test_revocation_immediately_denies_subsequent_http_requests(monkeypatch):
    monkeypatch.setenv(TEST_GUARD_NAME,TEST_GUARD_VALUE)
    c,ledger,nonce,payload=setup()
    assert c.post(PATH,json=payload,headers=HEADERS).status_code==200
    ledger.revoke(session_nonce=nonce,trusted_server_decision=True,
                  policy_revision=POLICY)
    second=c.post(PATH,json=payload,headers=HEADERS)
    assert second.status_code==422
    assert second.json()["accepted"] is False
    assert second.json()["production_ingestion"] is False


def test_forged_browser_consent_can_never_replace_ledger(monkeypatch):
    monkeypatch.setenv(TEST_GUARD_NAME,TEST_GUARD_VALUE)
    c,ledger,nonce,payload=setup(allow_tracking=False)
    payload["events"][0]["consent"]=True
    assert c.post(PATH,json=payload,headers=HEADERS).status_code==422


def test_acquisition_channel_cannot_be_overridden_by_browser(monkeypatch):
    monkeypatch.setenv(TEST_GUARD_NAME,TEST_GUARD_VALUE)
    c,ledger,nonce,payload=setup()
    payload["events"][0]["acquisition_channel"]="email"
    assert c.post(PATH,json=payload,headers=HEADERS).status_code==422


def test_erased_record_denies_session_reuse_in_http_simulation(monkeypatch):
    monkeypatch.setenv(TEST_GUARD_NAME,TEST_GUARD_VALUE)
    c,ledger,nonce,payload=setup()
    ledger.erase(session_nonce=nonce)
    assert c.post(PATH,json=payload,headers=HEADERS).status_code==422


def test_reject_remote_peer_even_with_server_grant(monkeypatch):
    monkeypatch.setenv(TEST_GUARD_NAME,TEST_GUARD_VALUE)
    _,ledger,nonce,payload=setup()
    app=FastAPI()
    app.include_router(build_dormant_event_ingress(
        allow_local_test_simulation=True,approved_paths=["/"],
        resolve_server_consent=ledger.resolve_consent,
        resolve_server_channel=ledger.resolve_acquisition,
        clock=lambda:NOW))
    remote=TestClient(app,client=("203.0.113.88",4174))
    r=remote.post(PATH,json=payload,headers=HEADERS)
    assert r.status_code==403
    assert r.json()["production_ingestion"] is False
