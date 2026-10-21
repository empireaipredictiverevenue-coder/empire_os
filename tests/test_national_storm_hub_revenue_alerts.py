from datetime import datetime, timedelta, timezone

from empire_os.national_storm_hub_revenue_alerts import review_nsh_revenue_alerts


NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)


def review(**overrides):
    params = {
        "now": NOW,
        "site_probe": {"homepage_http": 200, "weather_api_http": 200},
        "current_revenue_pulse": {
            "schema_version": "empire.revenue-pulse.v3",
            "generated_at": (NOW - timedelta(minutes=5)).isoformat(),
            "recognized_revenue_truth": {"recognized_revenue_cents": 900000},
            "current_window": {"commercial_replies": 500},
        },
    }
    params.update(overrides)
    return review_nsh_revenue_alerts(**params)


def event(kind="contractor_enquiry", **overrides):
    fields = dict(
        event_id="order-1", tenant_id="national-storm-hub",
        kind=kind, evidence_ref="empiredb:nsh:receipt:1",
        source="canonical_empiredb_postgres", verified=True,
        occurred_at=NOW.isoformat(),
        homeowner_initiated=True, purpose_consent="contractor_connection",
        consent_verified=True, amount_minor=2000, currency="USD",
        settlement_ref="chain:tx:receipt", accounting_ref="revenue:journal:42",
    )
    fields.update(overrides)
    return fields


def test_fresh_global_pulse_not_misattributed_as_nsh_revenue():
    r = review()
    assert r["empire_pulse_state"] == "FRESH_ORGANISATION_WIDE"
    assert r["nsh_commercial_events_state"] == "UNCONNECTED"
    assert r["nsh_enquiries"] is None
    assert r["nsh_payments_verified"] is None
    assert r["nsh_recognized_revenue"] is None
    assert r["web_traffic"] is None
    assert r["new_alerts"] == []


def test_public_endpoint_failures_create_review_alert_not_outbound():
    r = review(site_probe={"homepage_http": 503, "weather_api_http": 503})
    assert {a["kind"] for a in r["alerts"]} == {
        "site_unavailable", "weather_feed_unavailable"
    }
    assert r["notification_sent"] is False
    assert r["execution_authority"] == "none"


def test_expired_global_snapshot_alerts_on_freshness_not_as_sale():
    r = review(current_revenue_pulse={
        "schema_version": "empire.revenue-pulse.v3",
        "generated_at": (NOW - timedelta(minutes=35)).isoformat(),
    })
    assert any(a["kind"] == "pulse_stale" for a in r["new_alerts"])


def test_only_scope_verified_optin_and_payment_evidence_eligible():
    events = [
        event(),
        event(event_id="duplicate", evidence_ref="empiredb:nsh:receipt:2", consent_verified=False),
        event(event_id="different-tenant", evidence_ref="empiredb:nsh:receipt:3", tenant_id="empire-main"),
        event(event_id="pay-1", evidence_ref="empiredb:nsh:paid:1", kind="payment_verified"),
        event(event_id="fake-pay", evidence_ref="empiredb:nsh:paid:2", kind="payment_verified", settlement_ref=""),
        event(event_id="rev-1", evidence_ref="empiredb:nsh:rev:1", kind="revenue_recognized"),
    ]
    r = review(tenant_events=events)
    assert r["nsh_verified_commercial_event_count"] == 3
    assert r["rejected_unverified_events"] == 3
    assert {a["kind"] for a in r["new_alerts"]} == {
        "contractor_enquiry", "payment_verified", "revenue_recognized"
    }
    assert all(a["send_authority"] == "none" for a in r["new_alerts"])


def test_dedupe_uses_canonical_evidence_ref_not_theoretical_value():
    first = review(tenant_events=[event()])
    k = first["new_alerts"][0]["key"]
    second = review(tenant_events=[event()], previously_seen_keys={k})
    assert second["alerts"] and second["new_alerts"] == []
    assert not second["notification_sent"]


def test_expired_and_future_unsupported_evidence_rejected():
    r = review(tenant_events=[
        event(occurred_at=(NOW + timedelta(minutes=1)).isoformat()),
        event(evidence_ref="different", occurred_at=(NOW - timedelta(days=60)).isoformat()),
        event(evidence_ref="third", source="web_form_unverified"),
    ])
    assert r["nsh_verified_commercial_event_count"] == 0
    assert r["new_alerts"] == []
