"""Deny-by-default, explicitly SIMULATED session/consent/source authority."""
from datetime import datetime, timedelta, timezone
import json
import re
from threading import Thread

import pytest

from empire_os.analytics.first_party_event_contract import (
    EventContractHeld, simulate_verified_batch,
)
from empire_os.analytics.offline_session_authority import (
    AuthorityHeld, MAX_SESSIONS, OfflineSessionAuthority, ORIGIN, PURPOSE,
)

POLICY="analytics-prototype-20261019"
NOW=datetime(2026,10,19,11,0,tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.current=NOW
    def __call__(self):
        return self.current


def make(*, source=("organic_search","server_verified_referral"),
         clock=None, enabled=True, policy=POLICY):
    clock = Clock() if clock is None else clock
    a=OfflineSessionAuthority(policy_revision=policy,
        resolve_trusted_acquisition=lambda:source,
        clock=clock,
        enable_offline_simulation=enabled)
    return a,clock


def allow(a, nonce):
    return a.decide(session_nonce=nonce, decision="granted",
        policy_revision=POLICY,trusted_server_decision=True)


def event(nonce, *, idx=1, kind="page_view"):
    return {"event_nonce":f"{idx:032x}","session_nonce":nonce,
            "event_type":kind,"page_path":"/",
            "occurred_at":"2026-10-19T11:00:00Z"}


def simulate(a, events):
    return simulate_verified_batch(events,approved_paths=["/"],
        resolve_server_consent=a.resolve_consent,
        resolve_server_channel=a.resolve_acquisition, now=NOW)


def test_issuance_is_opaque_and_consent_denied_by_default():
    a,_=make()
    nonce=a.open_session(site=ORIGIN)
    assert re.fullmatch(r"[a-f0-9]{32}",nonce)
    assert a.resolve_consent(nonce) is False
    with pytest.raises(EventContractHeld):
        simulate(a,[event(nonce)])
    assert a.readiness()["website_consent_legally_verified"] is False
    assert a.readiness()["session_cookie_set"] is False
    assert nonce not in json.dumps(a.readiness())


def test_server_grant_allows_offline_simulation_not_real_metrics():
    a,_=make()
    nonce=a.open_session(site=ORIGIN)
    receipt=allow(a,nonce)
    assert receipt.status=="SIMULATED_SERVER_CONSENT_GRANTED"
    assert receipt.consent_revision==1
    assert receipt.lawful_consent_verified is False
    d=simulate(a,[event(nonce),event(nonce,idx=2,kind="engagement"),
                  event(nonce,idx=3,kind="form_submit_attempt")])
    assert d["status"]=="OFFLINE_CONSENT_GATED_CONTRACT_SIMULATION"
    assert d["simulated_sessions"]==1
    assert d["simulated_engaged_sessions"]==1
    assert d["simulated_form_submit_attempts"]==1
    assert d["real_visitors_verified"] is False
    assert d["real_leads_verified"] is False
    assert d["realised_revenue_verified"] is False
    assert nonce not in json.dumps(d)


def test_revocation_is_immediate_terminal_and_denies_existing_retries():
    a,_=make()
    nonce=a.open_session(site=ORIGIN)
    allow(a,nonce)
    assert simulate(a,[event(nonce)])["simulated_page_views"]==1
    result=a.revoke(session_nonce=nonce,policy_revision=POLICY,
                   trusted_server_decision=True)
    assert result.status=="SIMULATED_SERVER_CONSENT_REVOKED"
    assert result.consent_revision==2
    assert not a.resolve_consent(nonce)
    with pytest.raises(EventContractHeld):
        simulate(a,[event(nonce)])
    with pytest.raises(AuthorityHeld,match="NEW_SESSION_REQUIRED"):
        allow(a,nonce)


def test_denied_decision_does_not_grant_and_can_be_reconsidered():
    a,_=make()
    nonce=a.open_session(site=ORIGIN)
    a.decide(session_nonce=nonce,decision="denied",
        trusted_server_decision=True,policy_revision=POLICY)
    assert not a.resolve_consent(nonce)
    allow(a,nonce)
    assert a.resolve_consent(nonce)


def test_policy_mismatch_rejected_and_old_grant_not_usable_under_new_policy():
    a,_=make()
    nonce=a.open_session(site=ORIGIN)
    with pytest.raises(AuthorityHeld,match="POLICY_MISMATCH"):
        a.decide(session_nonce=nonce,decision="granted",
                 trusted_server_decision=True,policy_revision="other-policy-v2")
    assert not a.resolve_consent(nonce)


@pytest.mark.parametrize("trust", [None,False,1,0,"true"])
def test_browser_boolean_cannot_directly_grant(trust):
    a,_=make()
    n=a.open_session(site=ORIGIN)
    with pytest.raises(AuthorityHeld,match="SERVER_DECISION_REQUIRED"):
        a.decide(session_nonce=n,decision="granted",
                 trusted_server_decision=trust,policy_revision=POLICY)
    assert not a.resolve_consent(n)


def test_expiry_and_clock_rollback_do_not_resurrect_session():
    a,clock=make()
    n=a.open_session(site=ORIGIN)
    allow(a,n)
    clock.current=NOW+timedelta(minutes=30)
    assert not a.resolve_consent(n)
    with pytest.raises(AuthorityHeld,match="EXPIRED"):
        a.revoke(session_nonce=n,trusted_server_decision=True,policy_revision=POLICY)
    clock.current=NOW-timedelta(seconds=1)
    assert not a.resolve_consent(n)


def test_erasure_is_immediate_and_unverified_events_denied():
    a,_=make()
    n=a.open_session(site=ORIGIN)
    allow(a,n)
    a.erase(session_nonce=n)
    assert not a.resolve_consent(n)
    with pytest.raises(AuthorityHeld,match="UNKNOWN_SESSION"):
        a.erase(session_nonce=n)
    with pytest.raises(EventContractHeld):
        simulate(a,[event(n)])


def test_independent_sessions_maintain_separate_consent():
    a,_=make()
    yes=a.open_session(site=ORIGIN)
    no=a.open_session(site=ORIGIN)
    assert yes!=no
    allow(a,yes)
    assert a.resolve_consent(yes) is True
    assert a.resolve_consent(no) is False
    with pytest.raises(EventContractHeld):
        simulate(a,[event(yes),event(no,idx=2)])


def test_source_is_server_sourced_not_browser_label():
    a,_=make(source=("organic_social","server_verified_referral"))
    n=a.open_session(site=ORIGIN)
    allow(a,n)
    assert a.resolve_acquisition(n)=="organic_social"
    raw=event(n)
    raw["acquisition_channel"]="organic_search"
    with pytest.raises(EventContractHeld):
        simulate(a,[raw])
    assert simulate(a,[event(n)])["simulated_sessions"]==1


@pytest.mark.parametrize("source",[
    ("adwords","signed_campaign_binding"),
    ("direct","server_verified_referral"),
    ("email","server_observed_direct"),
    ("unknown","server_verified_referral"),
    ("organic_social","server_unknown"),
    ("direct","browser_unverified_referrer"),
    ("email","server_verified_referral"),
    ("organic_search","signed_campaign_binding"),
    ("referral","signed_campaign_binding"),
    ("direct",""),
    (123,"server_observed_direct"),
])
def test_invalid_or_mismatched_server_attribution_fails(source):
    a,_=make(source=source)
    with pytest.raises(AuthorityHeld):
        a.open_session(site=ORIGIN)


@pytest.mark.parametrize("origin",[
    "http://empire-ai.co.uk","https://empire-ai.co.uk/",
    "https://evil.example","https://empire-ai.co.uk.evil",
    "https://empire-ai.co.uk/?token=abc",
    None,
])
def test_cross_property_session_creation_denied(origin):
    a,_=make()
    with pytest.raises(AuthorityHeld,match="SITE_ORIGIN_UNAPPROVED"):
        a.open_session(site=origin)


@pytest.mark.parametrize("policy",["","p","TEST","2026 consent","ga/analytics","a"*80])
def test_invalid_consent_policy_rejected(policy):
    with pytest.raises(AuthorityHeld,match="POLICY_REVISION_INVALID"):
        make(policy=policy)


def test_source_authority_failure_does_not_print_secret():
    def broken():
        raise RuntimeError("secret-analytics-policy-token")
    a=OfflineSessionAuthority(policy_revision=POLICY,
        resolve_trusted_acquisition=broken,
        clock=lambda:NOW,enable_offline_simulation=True)
    with pytest.raises(AuthorityHeld) as exc:
        a.open_session(site=ORIGIN)
    assert "secret-analytics-policy-token" not in str(exc.value)


def test_lifecycle_not_activated_without_explicit_offline_guard():
    with pytest.raises(AuthorityHeld,match="OFFLINE_ONLY"):
        make(enabled=False)


def test_offline_memory_quota_fail_closed():
    a,_=make()
    for _ in range(MAX_SESSIONS):
        a.open_session(site=ORIGIN)
    with pytest.raises(AuthorityHeld,match="QUOTA"):
        a.open_session(site=ORIGIN)


def test_concurrent_session_issuance_stays_unique():
    a,_=make()
    results=[]
    def worker():
        results.append(a.open_session(site=ORIGIN))
    threads=[Thread(target=worker) for _ in range(20)]
    for t in threads:t.start()
    for t in threads:t.join()
    assert len(results)==len(set(results))==20


def test_does_not_use_http_db_or_session_storage():
    a,_=make()
    n=a.open_session(site=ORIGIN)
    assert n not in json.dumps(a.readiness())
    assert a.readiness()["backend_store"]=="process_memory_simulation"
    assert a.readiness()["database_writes"] is False
    assert a.readiness()["execution_authority"]=="NONE"


def test_decision_type_validation():
    a,_=make()
    n=a.open_session(site=ORIGIN)
    with pytest.raises(AuthorityHeld):
        a.decide(session_nonce=n,decision="purchase",
                 trusted_server_decision=True,policy_revision=POLICY)
