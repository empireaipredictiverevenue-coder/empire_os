"""HTTP-level privacy and governance preflight for an unmounted collector."""
from datetime import datetime,timezone
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.analytics.dormant_event_ingress import (
    PATH, build_dormant_event_ingress, TEST_GUARD_NAME, TEST_GUARD_VALUE,
)

NOW=datetime(2026,10,19,12,tzinfo=timezone.utc)
HEADERS={"origin":"https://empire-ai.co.uk",
         "sec-fetch-site":"same-origin",
         "content-type":"application/json"}

def row(**kwargs):
    event={
        "event_nonce":"a"*32,"session_nonce":"b"*32,
        "event_type":"page_view","occurred_at":"2026-10-19T12:00:00Z",
        "page_path":"/",
    }
    event.update(kwargs)
    return event

def payload(**kwargs):
    return {"events":[row(**kwargs)]}

def client(*,enabled=False,consent=None,channel=None,local=True,
           paths=None,clock=None,limiter=None):
    app=FastAPI()
    app.include_router(build_dormant_event_ingress(
        allow_local_test_simulation=enabled,
        approved_paths=["/"] if paths is None else paths,
        resolve_server_consent=consent,
        resolve_server_channel=channel,
        clock=clock,
        limiter=limiter,
    ))
    return TestClient(app,client=("127.0.0.1" if local else "203.0.113.1",43333))

@pytest.fixture
def test_guard(monkeypatch):
    monkeypatch.setenv(TEST_GUARD_NAME,TEST_GUARD_VALUE)

@pytest.fixture
def accepting(test_guard):
    return client(enabled=True,consent=lambda _:True,
                  channel=lambda _:"direct",clock=lambda:NOW)

def send(c,p=None,headers=None):
    return c.post(PATH,json=payload() if p is None else p,
                  headers=HEADERS if headers is None else headers)

def test_unmounted_default_is_never_part_of_any_existing_production_app():
    from empire_os.search_intelligence.service import app as live_source_app
    assert not any(getattr(route,"path","")==PATH for route in live_source_app.routes)

def test_default_disabled_even_with_local_peer_and_valid_payload():
    r=send(client())
    assert r.status_code==503
    assert r.json()["status"]=="ANALYTICS_INGESTION_NOT_ACTIVATED"
    assert r.json()["production_ingestion"] is False
    assert r.headers["cache-control"].startswith("no-store")

def test_explicit_enabled_without_test_guard_is_still_disabled(monkeypatch):
    monkeypatch.delenv(TEST_GUARD_NAME,raising=False)
    c=client(enabled=True,consent=lambda _:True,
             channel=lambda _:"direct",clock=lambda:NOW)
    assert send(c).status_code==503

def test_enabled_with_no_resolver_still_disabled(test_guard):
    assert send(client(enabled=True,clock=lambda:NOW)).status_code==503

def test_test_guard_removed_after_factory_instantiation_disables_again(test_guard,monkeypatch):
    c=client(enabled=True,consent=lambda _:True,
             channel=lambda _:"direct",clock=lambda:NOW)
    monkeypatch.delenv(TEST_GUARD_NAME)
    assert send(c).status_code==503

def test_safe_local_simulation_is_explicitly_not_real_data(accepting):
    r=send(accepting)
    assert r.status_code==200
    d=r.json()
    assert d["accepted"] is False
    assert d["production_ingestion"] is False
    assert d["website_sessions_verified"] is False
    assert d["realised_revenue_verified"] is False
    assert d["simulation_only"] is True
    assert d["simulation"]["mode"]=="SIMULATION_ONLY"
    assert d["simulation"]["simulated_page_views"]==1
    for field in ("event_nonce","session_nonce","page_path","b"*32,"a"*32):
        assert field not in json.dumps(d)
    assert r.headers["referrer-policy"]=="no-referrer"
    assert r.headers["x-content-type-options"]=="nosniff"

def test_unknown_source_consent_fails_without_logging_sensitive_payload(test_guard):
    c=client(enabled=True,consent=lambda _:False,
             channel=lambda _:"direct",clock=lambda:NOW)
    r=send(c)
    assert r.status_code==422
    assert "b"*32 not in r.text

def test_unverified_acquisition_source_fails_without_faked_direct(test_guard):
    c=client(enabled=True,consent=lambda _:True,
             channel=lambda _:"paid_search",clock=lambda:NOW)
    assert send(c).status_code==422

@pytest.mark.parametrize("headers,status",[
    ({},403),
    ({"origin":"https://attacker.example","sec-fetch-site":"same-origin","content-type":"application/json"},403),
    ({"origin":"https://empire-ai.co.uk.evil","sec-fetch-site":"same-origin","content-type":"application/json"},403),
    ({"origin":"https://empire-ai.co.uk","sec-fetch-site":"cross-site","content-type":"application/json"},403),
    ({"origin":"https://empire-ai.co.uk","sec-fetch-site":"none","content-type":"application/json"},403),
    ({**HEADERS,"cookie":"_ga=untrusted"},403),
    ({**HEADERS,"authorization":"Bearer injected"},403),
    ({**HEADERS,"content-type":"text/plain"},415),
    ({**HEADERS,"content-type":"application/json; charset=utf-8"},415),
    ({**HEADERS,"content-encoding":"gzip"},415),
])
def test_cross_origin_credentials_or_noncanonical_media_denied(accepting,headers,status):
    r=send(accepting,headers=headers)
    assert r.status_code==status
    assert r.json()["production_ingestion"] is False

def test_nonlocal_peer_cannot_execute_simulation(test_guard):
    c=client(enabled=True,local=False,consent=lambda _:True,
             channel=lambda _:"direct",clock=lambda:NOW)
    assert send(c).status_code==403

def test_more_than_32k_bytes_refused_before_event_parsing(accepting):
    big={**row(),"email":"private@example.invalid"*3000}
    r=send(accepting,p={"events":[big]})
    assert r.status_code==413
    assert "private@example.invalid" not in r.text

@pytest.mark.parametrize("extra",[
    {"email":"person@example.com"},
    {"consent":True},
    {"acquisition_channel":"organic_search"},
    {"cookie":"foo"},
    {"user_agent":"Mozilla"},
    {"referrer":"https://secret.example/?token=hidden"},
    {"session_id":"a-person"},
    {"revenue_cents":99999},
])
def test_malicious_event_field_rejected(accepting,extra):
    r=send(accepting,p={"events":[row(**extra)]})
    assert r.status_code==422
    assert r.json()["accepted"] is False
    assert all(v not in r.text for v in ("person@example.com","hidden","99999"))

def test_unregistered_path_rejected(accepting):
    assert send(accepting,p=payload(page_path="/private/person/")).status_code==422

def test_batch_must_have_exact_one_key(accepting):
    for p in ({"events":[row()],"debug":True},{},[],{"event":row()}):
        assert send(accepting,p=p).status_code==422

def test_duplicate_nonce_conflict_is_held(accepting):
    a=row()
    b={**a,"event_type":"cta_click"}
    assert send(accepting,p={"events":[a,b]}).status_code==422

def test_one_event_retry_is_deduplicated_simulation_only(accepting):
    r=send(accepting,p={"events":[row(),row()]})
    assert r.status_code==200
    assert r.json()["simulation"]["duplicate_retries_discarded"]==1
    assert r.json()["simulation"]["simulated_page_views"]==1

def test_null_and_bad_json_held(accepting):
    for raw in (b"{bad-json",b"null",b'{"events":null}'):
        r=accepting.post(PATH,content=raw,headers=HEADERS)
        assert r.status_code==422

def test_rate_limit_uses_existing_empire_intake_limiter(accepting):
    codes=[send(accepting).status_code for _ in range(63)]
    assert codes[:60]==[200]*60
    assert codes[60:]==[429]*3

def test_approved_router_can_only_simulate_not_write_to_storage(accepting):
    assert not hasattr(accepting.app.state,"analytics_database")
    assert send(accepting).json()["simulation"]["database_writes"] is False

def test_reject_wrong_http_method(accepting):
    r=accepting.get(PATH)
    assert r.status_code==405
