"""Privacy-safe measurement contract regression; NO LIVE EVENTS OR TRACKING."""
from datetime import datetime, timedelta, timezone
import json
import pytest

from empire_os.analytics.first_party_event_contract import (
    EventContractHeld, simulate_verified_batch, MAX_BATCH,
)

NOW=datetime(2026,10,19,12,tzinfo=timezone.utc)
SESSION="a"*32


def event(name="page_view", *, idx=1, session=SESSION, path="/"):
    return {
        "event_nonce":f"{idx:032x}",
        "session_nonce":session,
        "event_type":name,
        "occurred_at":NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "page_path":path,
    }


def calculate(items, **kwargs):
    return simulate_verified_batch(
        items,approved_paths=["/","/industries/roofing/"],
        resolve_server_consent=lambda session: True,
        resolve_server_channel=lambda session: "organic_search",
        now=NOW,**kwargs)


def test_consent_gated_dedupe_and_sessions_remain_simulation():
    items=[event(idx=1),event(idx=1),event("engagement",idx=2),
           event("cta_click",idx=3),event("form_start",idx=4),
           event("form_submit_attempt",idx=5)]
    d=calculate(items)
    assert d["status"]=="OFFLINE_CONSENT_GATED_CONTRACT_SIMULATION"
    assert d["simulated_sessions"]==1
    assert d["simulated_page_views"]==1
    assert d["simulated_engaged_sessions"]==1
    assert d["simulated_form_submit_attempts"]==1
    assert d["duplicate_retries_discarded"]==1
    assert d["accepted_event_count"]==5
    assert d["browser_collector_enabled"] is False
    assert d["production_ingestion_enabled"] is False
    for key in ("real_visitors_verified","real_leads_verified","crm_conversion_verified",
                "realised_revenue_verified","revenue_attribution_verified","database_writes",
                "paid_provider_requests","outbound_sent"):
        assert d[key] is False
    dumped=json.dumps(d)
    assert SESSION not in dumped
    assert "event_nonce" not in dumped
    assert "page_path" not in dumped
    assert "organic_search" not in dumped


@pytest.mark.parametrize("field,value",[
    ("event_type","purchase"),("event_type","lead_verified"),
    ("acquisition_channel","google/cpc?email=someone"),
    ("acquisition_channel","tiktok_ads"),
    ("page_path","/prospect/person-alice/"),
    ("page_path","/industries/roofing/?email=user@example.com"),
    ("page_path","https://empire-ai.co.uk/"),
    ("session_nonce","user@example.com"),
    ("session_nonce","0"*32),
    ("session_nonce","f"*31),
    ("event_nonce","user@example.com"),
    ("event_nonce","g"*32),
    ("occurred_at","2026-10-19T12:00:00"),
    ("occurred_at","2026-10-19T12:00:00+01:00"),
    ("occurred_at","2026-10-19T12:00:00Z?foo=bar"),
    ("occurred_at","2026-10-22T12:00:00Z"),
    ("occurred_at","2026-10-14T12:00:00Z"),
])
def test_payload_rejects_non_allowlisted_or_pii_risky_values(field,value):
    row=event()
    row[field]=value
    with pytest.raises(EventContractHeld):
        calculate([row])


@pytest.mark.parametrize("extra",[
    {"email":"user@example.com"},
    {"user_agent":"Mozilla/5.0"},
    {"ip":"198.51.100.1"},
    {"consent":True},
    {"referrer":"https://bad.example/?secret=abc"},
    {"utm_campaign":"email-of-a-buyer"},
    {"raw_url":"https://empire-ai.co.uk/?auth_token=secret"},
    {"revenue_cents":999999},
    {"form_fields":{"name":"A Person"}},
    {"cookie":"_ga=..."},
])
def test_no_pii_or_browser_consent_or_revenue_fields_admitted(extra):
    with pytest.raises(EventContractHeld):
        calculate([{**event(),**extra}])


def test_replayed_event_with_conflicting_content_fails_closed():
    with pytest.raises(EventContractHeld,match="REPLAY_CONFLICT"):
        calculate([event(),event("cta_click")])


def test_browser_channel_claim_is_rejected_not_trusted():
    other={**event(idx=2),"acquisition_channel":"organic_search"}
    with pytest.raises(EventContractHeld,match="FIELDS_NOT_ALLOWLISTED"):
        calculate([event(),other])


def test_server_source_resolver_is_required_and_fail_closed():
    with pytest.raises(EventContractHeld,match="ACQUISITION_RESOLVER_REQUIRED"):
        simulate_verified_batch([event()],approved_paths=["/"],
            resolve_server_consent=lambda _:True,
            resolve_server_channel=None,now=NOW)
    for resolver in (lambda _:"made-up-source",lambda _:None,
                     lambda _:(_ for _ in ()).throw(RuntimeError("secret"))):
        with pytest.raises(EventContractHeld):
            simulate_verified_batch([event()],approved_paths=["/"],
                resolve_server_consent=lambda _:True,
                resolve_server_channel=resolver,now=NOW)


def test_different_sessions_are_counted_only_with_server_consent():
    d=calculate([event(session=SESSION),event(idx=2,session="b"*32)])
    assert d["simulated_sessions"]==2
    assert d["simulated_page_views"]==2


@pytest.mark.parametrize("consent",[
    None,
    lambda _:False,
    lambda _:None,
    lambda _:1,
    lambda _:(_ for _ in ()).throw(RuntimeError("hidden-database-password")),
])
def test_unknown_server_verified_consent_cannot_be_overridden_by_browser(consent):
    with pytest.raises(EventContractHeld) as exc:
        simulate_verified_batch([event()],approved_paths=["/"],
            resolve_server_consent=consent,
            resolve_server_channel=lambda _:"direct",now=NOW)
    assert "hidden-database-password" not in str(exc.value)


def test_more_than_500_events_bounded():
    with pytest.raises(EventContractHeld):
        calculate([event(idx=i+1) for i in range(MAX_BATCH+1)])


@pytest.mark.parametrize("invalid_paths",[
    [],["/","/users/personal-email/?"],["https://empire-ai.co.uk/"],
    ["/valid/","/valid/../"],["/good/%40email/"],
    ["/good/"*8],["/user@domain/"],
])
def test_owner_approved_page_register_must_be_static_and_bounded(invalid_paths):
    with pytest.raises(EventContractHeld):
        simulate_verified_batch([event()],approved_paths=invalid_paths,
            resolve_server_consent=lambda _:True,
            resolve_server_channel=lambda _:"direct",now=NOW)


def test_real_time_clock_must_be_timezone_aware():
    with pytest.raises(EventContractHeld):
        simulate_verified_batch([event()],approved_paths=["/"],
            resolve_server_consent=lambda _:True,
            resolve_server_channel=lambda _:"direct",now=NOW.replace(tzinfo=None))


def test_multiple_owner_approved_paths_can_be_aggregated_without_exposing_urls():
    d=calculate([event(path="/"),event(idx=2,path="/industries/roofing/")])
    assert d["simulated_page_views"]==2
    assert "/industries/roofing/" not in json.dumps(d)
