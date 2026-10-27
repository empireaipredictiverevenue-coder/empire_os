"""Empire AI original Analytics: privacy-guarded offline channel stage review.

Synthetic test fixtures ONLY. No Lead Smart, live collector or revenue events.
"""
import json
from datetime import datetime, timezone
from collections import Counter
import pytest

from empire_os.analytics.first_party_event_contract import (
    EventContractHeld, ALLOWED_EVENTS, ALLOWED_CHANNELS,
    simulate_channel_stage_presence, simulate_verified_batch,
)

NOW = datetime(2026, 10, 27, 18, 0, tzinfo=timezone.utc)
CHANNELS = ("organic_search", "organic_social", "email", "direct",
            "referral", "unknown")
PATHS = ["/", "/commercial/", "/industries/solar/"]


def row(session_index, kind, event_index, path="/commercial/"):
    return {
        "session_nonce": f"{session_index:032x}",
        "event_nonce": f"{event_index:032x}",
        "event_type": kind, "page_path": path,
        "occurred_at": "2026-10-27T18:00:00Z",
    }


def review(items, owners, *, consent=None, source=None):
    return simulate_channel_stage_presence(
        items, approved_paths=PATHS,
        resolve_server_consent=consent or (lambda _: True),
        resolve_server_channel=source or (lambda session: owners[session]),
        now=NOW,
    )


def test_six_channel_offline_cohorts_are_session_not_click_counts():
    rows = []
    owner = {}
    idx = 1
    for group, channel in enumerate(CHANNELS):
        for n in range(5):
            sid = group * 10 + n + 1
            owner[f"{sid:032x}"] = channel
            rows.append(row(sid, "page_view", idx)); idx += 1
            # One session may have repeated events without becoming two leads.
            if n < 3:
                rows.append(row(sid, "engagement", idx)); idx += 1
                rows.append(row(sid, "cta_click", idx)); idx += 1
            if n < 2:
                rows.append(row(sid, "form_start", idx)); idx += 1
                rows.append(row(sid, "form_submit_attempt", idx)); idx += 1
    rows.append(dict(rows[0]))  # Retransmission of the same event nonce.
    result = review(rows, owner)
    assert result["mode"] == "SIMULATION_ONLY"
    assert result["original_allowlisted_channel_count"] == 6
    assert result["original_allowlisted_stage_count"] == 5
    assert result["small_cohorts_suppressed_count"] == 0
    assert result["simulated_duplicate_retries_discarded"] == 1
    assert set(x["channel"] for x in result["channels"]) == set(ALLOWED_CHANNELS)
    for cohort in result["channels"]:
        assert cohort["status"] == "SIMULATED_DISPLAYABLE_COHORT"
        assert cohort["simulated_unique_sessions"] == 5
        stage = cohort["simulated_sessions_with_stage"]
        assert stage == {"cta_click": 3, "engagement": 3, "form_start": 2,
                         "form_submit_attempt": 2, "page_view": 5}
        assert cohort["form_submit_attempt_is_confirmed_lead"] is False
        assert cohort["revenue_attributed"] is False
    assert result["actual_sessions_verified"] is False
    assert result["actual_leads_verified"] is False
    assert result["actual_revenue_verified"] is False
    assert result["website_collector_enabled"] is False
    assert result["paid_campaign_execution_authorized"] is False
    assert result["execution_authority"] == "NONE"
    dumped = json.dumps(result)
    assert "/commercial/" not in dumped
    assert "session_nonce" not in dumped
    assert "event_nonce" not in dumped
    assert f"{1:032x}" not in dumped


def test_display_suppression_does_not_report_small_channel_counts():
    owners = {}
    items = []
    for index in range(1, 8):
        sid = f"{index:032x}"
        owners[sid] = "organic_search" if index < 6 else "email"
        items.append(row(index, "page_view", index))
    out = review(items, owners)
    grouped = {r["channel"]: r for r in out["channels"]}
    assert grouped["organic_search"]["simulated_unique_sessions"] == 5
    assert grouped["email"]["status"] == "SUPPRESSED_SMALL_SIMULATED_COHORT"
    assert grouped["email"]["simulated_unique_sessions"] is None
    assert grouped["email"]["simulated_sessions_with_stage"] is None
    assert grouped["direct"]["status"] == "NO_SIMULATED_EVENTS"
    assert grouped["direct"]["simulated_unique_sessions"] is None
    assert out["small_cohorts_suppressed_count"] == 1
    # Never reveal hidden source activity by subtracting global totals.
    assert out["simulated_accepted_event_count"] is None
    assert out["simulated_duplicate_retries_discarded"] is None


def test_owner_channel_and_consent_resolvers_evaluated_once_per_unique_session():
    src = Counter()
    approved = Counter()
    items = [row(1, "page_view", 1), row(1, "cta_click", 2),
             row(2, "page_view", 3)]
    def channel(k):
        src[k] += 1
        return "organic_search"
    def consent(k):
        approved[k] += 1
        return True
    out = review(items, {}, consent=consent, source=channel)
    assert len(src) == len(approved) == 2
    assert all(v == 1 for v in src.values())
    assert all(v == 1 for v in approved.values())
    assert out["session_source_resolved_once_via_server_simulation"] is True


@pytest.mark.parametrize("change", [
    lambda e: e.update(ip="198.51.100.2"),
    lambda e: e.update(email="example@example.invalid"),
    lambda e: e.update(acquisition_channel="organic_search"),
    lambda e: e.update(revenue_cents=50000),
    lambda e: e.update(consent=True),
    lambda e: e.update(page_path="/commercial/?utm_email=secret"),
    lambda e: e.update(event_type="purchase"),
])
def test_rejects_untrusted_browser_source_identity_payment_or_pii(change):
    r = row(1, "page_view", 1)
    change(r)
    with pytest.raises(EventContractHeld):
        review([r], {r["session_nonce"]: "email"})


def test_unverified_source_and_consent_denied_entire_batch():
    items = [row(1, "page_view", 1), row(2, "page_view", 2)]
    owners = {f"{i:032x}": "direct" for i in (1, 2)}
    with pytest.raises(EventContractHeld):
        review(items, owners, consent=lambda k: False if k == f"{2:032x}" else True)
    with pytest.raises(EventContractHeld):
        review(items, owners, source=lambda k: "paid_search")
    with pytest.raises(EventContractHeld):
        review(items, owners, source=lambda k: (_ for _ in ()).throw(
            RuntimeError("private-original-source-token")))


def test_replayed_nonce_conflict_rejected_and_attempt_not_revenue():
    owners = {f"{1:032x}": "direct"}
    with pytest.raises(EventContractHeld, match="REPLAY_CONFLICT"):
        review([row(1, "page_view", 1), row(1, "cta_click", 1)], owners)
    result = review([row(1, "form_submit_attempt", 1)], owners)
    assert result["actual_leads_verified"] is False
    assert result["stage_presence_is_not_ordered_conversion_funnel"] is True
    assert result["actual_revenue_verified"] is False


def test_original_overall_contract_unchanged_and_never_leaks_channel():
    d = simulate_verified_batch(
        [row(1, "page_view", 1)], approved_paths=PATHS,
        resolve_server_consent=lambda _: True,
        resolve_server_channel=lambda _: "organic_social", now=NOW,
    )
    assert d["simulated_sessions"] == 1
    assert d["simulated_page_views"] == 1
    assert "organic_social" not in json.dumps(d)
    assert d["mode"] == "SIMULATION_ONLY"


def test_original_offline_session_authority_revocation_holds_entire_channel_review():
    from empire_os.analytics.offline_session_authority import (
        OfflineSessionAuthority, ORIGIN,
    )
    iterator = iter(
        [("organic_search", "server_verified_referral")] * 5
        + [("email", "signed_campaign_binding")] * 5
    )
    authority = OfflineSessionAuthority(
        policy_revision="analytics-proof-20261027",
        resolve_trusted_acquisition=lambda: next(iterator),
        clock=lambda: NOW,
        enable_offline_simulation=True,
    )
    receipts = []
    for _ in range(10):
        token = authority.open_session(site=ORIGIN)
        authority.decide(
            session_nonce=token, decision="granted",
            trusted_server_decision=True,
            policy_revision="analytics-proof-20261027",
        )
        receipts.append(token)
    events = [
        {
            "session_nonce": token, "event_nonce": f"{index:032x}",
            "event_type": "page_view", "page_path": "/",
            "occurred_at": "2026-10-27T18:00:00Z",
        } for index, token in enumerate(receipts, start=1)
    ]
    def projected(batch):
        return simulate_channel_stage_presence(
            batch, approved_paths=PATHS,
            resolve_server_consent=authority.resolve_consent,
            resolve_server_channel=authority.resolve_acquisition,
            now=NOW,
        )
    before = projected(events)
    counts = {r["channel"]: r["simulated_unique_sessions"]
              for r in before["channels"]}
    assert counts["organic_search"] == 5
    assert counts["email"] == 5
    assert all(token not in json.dumps(before) for token in receipts)
    authority.revoke(
        session_nonce=receipts[0], trusted_server_decision=True,
        policy_revision="analytics-proof-20261027",
    )
    with pytest.raises(EventContractHeld, match="CONSENT_NOT_PROVEN"):
        projected(events)
    after = projected(events[1:])
    groups = {r["channel"]: r for r in after["channels"]}
    assert groups["organic_search"]["simulated_unique_sessions"] is None
    assert groups["organic_search"]["status"] == "SUPPRESSED_SMALL_SIMULATED_COHORT"
    assert groups["email"]["simulated_unique_sessions"] == 5
    assert after["simulated_accepted_event_count"] is None
    assert after["actual_sessions_verified"] is False
