from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.inbound_recovery_api import create_inbound_recovery_router
from empire_os.inbound_revenue_recovery import (
    RecoveryEvent, RecoveryLedger, TenantReceptionProfile, plan_reception_response,
)


def event(kind, *, event_id=None, call_id="call-1", tenant_id="tenant-a", minute=0,
          origin=None, evidence_ref="", amount_minor=None, currency="",
          verified=False, synthetic=False):
    origins = {
        "ringing": "provider", "answered": "provider", "unanswered": "provider",
        "busy": "provider", "rejected": "provider", "completed": "provider",
        "callback_connected": "provider", "booking_confirmed": "calendar",
        "booking_cancelled": "calendar",
        "invoice_paid": "payments",
    }
    return RecoveryEvent(
        tenant_id=tenant_id, event_id=event_id or f"{call_id}-{kind}-{minute}",
        call_id=call_id, occurred_at=f"2026-10-20T09:{minute:02d}:00+00:00",
        kind=kind, origin=origin or origins.get(kind, "operator"),
        evidence_ref=evidence_ref, amount_minor=amount_minor, currency=currency,
        verified=verified, synthetic=synthetic,
    )


def test_evidence_recovered_and_paid_only_after_verified_reconnection():
    ledger = RecoveryLedger()
    for item in (
        event("ringing", minute=0),
        event("unanswered", minute=1),
        event("callback_requested", minute=2),
        event("callback_connected", minute=3, verified=True, evidence_ref="vonage-connected-1"),
        event("booking_confirmed", minute=4, verified=True, evidence_ref="calendar-res-1"),
        event("invoice_paid", minute=5, verified=True, evidence_ref="stripe-receipt-1",
              amount_minor=25900, currency="GBP"),
    ):
        assert ledger.append(item)
    report = ledger.report("tenant-a")
    assert report["missed_calls"] == 1
    assert report["verified_recovered_calls"] == 1
    assert report["confirmed_bookings"] == 1
    assert report["verified_paid_recovery_minor_by_currency"] == {"GBP": 25900}
    assert report["database_writes"] is False
    assert report["outbound_sent"] is False


def test_duplicate_replay_is_idempotent_and_conflicting_payload_rejected():
    ledger = RecoveryLedger()
    original = event("unanswered", minute=1)
    assert ledger.append(original)
    assert not ledger.append(original)
    with pytest.raises(ValueError, match="conflicting_duplicate"):
        ledger.append(replace(original, kind="busy"))


@pytest.mark.parametrize("kind,kwargs,reason", [
    ("callback_connected", {}, "callback_connected_requires_verified_provider"),
    ("booking_confirmed", {"origin": "operator", "verified": True, "evidence_ref": "fake"},
     "booking_confirmed_requires_verified_calendar"),
    ("invoice_paid", {"verified": True, "evidence_ref": "fake", "amount_minor": -1, "currency": "GBP"},
     "paid_amount_minor_required"),
    ("invoice_paid", {"verified": True, "evidence_ref": "fake", "amount_minor": 100, "currency": "gbp"},
     "iso_currency_required"),
    ("unanswered", {"origin": "operator"}, "call_status_requires_provider"),
])
def test_unverified_events_rejected(kind, kwargs, reason):
    with pytest.raises(ValueError, match=reason):
        event(kind, minute=1, **kwargs)


def test_cross_tenant_and_synthetic_events_are_not_counted():
    ledger = RecoveryLedger()
    ledger.append(event("unanswered", minute=1, tenant_id="a"))
    ledger.append(event("callback_connected", minute=2, tenant_id="b",
                        evidence_ref="provider-2", verified=True))
    ledger.append(event("unanswered", minute=3, call_id="synthetic",
                        tenant_id="a", synthetic=True))
    assert ledger.report("a")["verified_recovered_calls"] == 0
    assert ledger.report("a")["missed_calls"] == 1
    assert ledger.report("b")["missed_calls"] == 0


def test_money_requires_a_recovered_call():
    ledger = RecoveryLedger()
    ledger.append(event("unanswered", minute=1))
    ledger.append(event("invoice_paid", minute=3, verified=True,
                        evidence_ref="receipt-1", amount_minor=50000, currency="GBP"))
    assert ledger.report("tenant-a")["verified_paid_recovery_minor_by_currency"] == {}


def test_booking_request_is_not_confirmed():
    ledger = RecoveryLedger()
    ledger.append(event("unanswered", minute=1))
    ledger.append(event("booking_requested", minute=2))
    assert ledger.report("tenant-a")["confirmed_bookings"] == 0
    assert ledger.report("tenant-a")["verified_recovered_calls"] == 0


def test_same_payment_receipt_never_double_counts_across_calls():
    ledger = RecoveryLedger()
    for call in ("first", "second"):
        ledger.append(event("unanswered", call_id=call, minute=1))
        ledger.append(event("callback_connected", call_id=call, minute=2,
                            evidence_ref=f"conn-{call}", verified=True))
        ledger.append(event("invoice_paid", call_id=call, minute=3,
                            evidence_ref="same-receipt", verified=True,
                            amount_minor=30000, currency="GBP"))
    assert ledger.report("tenant-a")["verified_paid_recovery_minor_by_currency"] == {"GBP": 30000}


def test_reception_refuses_unverified_booking_confirmation():
    profile = TenantReceptionProfile("a", "Empire Plumbers", vertical="home_services")
    decision = plan_reception_response(profile, "book")
    assert decision.action == "booking_request_only"
    assert decision.booking_confirmed is False
    assert decision.outbound_authorized is False


def test_reception_discloses_ai_and_escalates_emergencies():
    profile = TenantReceptionProfile("a", "Empire Plumbers")
    assert "AI assistant" in plan_reception_response(profile, "hello").spoken_text
    urgent = plan_reception_response(profile, "emergency")
    assert urgent.action == "urgent_human_escalation"
    assert "emergency services" in urgent.spoken_text


def test_reception_optout_never_triggers_outbound():
    profile = TenantReceptionProfile("a", "Empire Plumbers")
    decision = plan_reception_response(profile, "stop")
    assert decision.action == "honour_opt_out"
    assert not decision.outbound_authorized


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(create_inbound_recovery_router())
    return TestClient(app)


def test_preview_denied_by_default(monkeypatch, client):
    monkeypatch.delenv("EMPIRE_INBOUND_RECOVERY_PREVIEW_ENABLED", raising=False)
    response = client.post("/v1/inbound-recovery/preview", json={
        "tenant_id": "a", "business_name": "Acme", "intent": "book",
    })
    assert response.status_code == 404


def test_preview_requires_token_even_when_enabled(monkeypatch, client):
    monkeypatch.setenv("EMPIRE_INBOUND_RECOVERY_PREVIEW_ENABLED", "true")
    monkeypatch.setenv("EMPIRE_INBOUND_RECOVERY_PREVIEW_TOKEN", "only-inside-tests")
    body = {"tenant_id": "a", "business_name": "Acme", "intent": "book"}
    assert client.post("/v1/inbound-recovery/preview", json=body).status_code == 401
    assert client.post("/v1/inbound-recovery/preview", json=body,
                       headers={"x-empire-preview-token": "wrong"}).status_code == 401
    allowed = client.post("/v1/inbound-recovery/preview", json=body,
                          headers={"x-empire-preview-token": "only-inside-tests"})
    assert allowed.status_code == 200
    assert allowed.json()["mode"] == "nonlive_preview_only"
    assert not allowed.json()["provider_connected"]
    assert not allowed.json()["booking_confirmed"]


def test_unsupported_vertical_fails_closed(monkeypatch, client):
    monkeypatch.setenv("EMPIRE_INBOUND_RECOVERY_PREVIEW_ENABLED", "true")
    monkeypatch.setenv("EMPIRE_INBOUND_RECOVERY_PREVIEW_TOKEN", "only-inside-tests")
    response = client.post("/v1/inbound-recovery/preview", json={
        "tenant_id": "a", "business_name": "Acme", "intent": "book", "vertical": "medical",
    }, headers={"x-empire-preview-token": "only-inside-tests"})
    assert response.status_code == 422


def test_revenue_is_not_backdated_to_before_verified_recovery():
    ledger = RecoveryLedger()
    ledger.append(event("unanswered", minute=1))
    ledger.append(event("invoice_paid", minute=2, verified=True,
                        evidence_ref="payment-before-contact", amount_minor=10000, currency="GBP"))
    ledger.append(event("callback_connected", minute=3, verified=True,
                        evidence_ref="provider-connected-1"))
    assert ledger.report("tenant-a")["verified_recovered_calls"] == 1
    assert ledger.report("tenant-a")["verified_paid_recovery_minor_by_currency"] == {}


def test_same_callback_receipt_does_not_recover_two_calls():
    ledger = RecoveryLedger()
    for cid in ("first", "second"):
        ledger.append(event("unanswered", call_id=cid, minute=1))
        ledger.append(event("callback_connected", call_id=cid, minute=2,
                            verified=True, evidence_ref="same-provider-receipt"))
    assert ledger.report("tenant-a")["verified_recovered_calls"] == 1


def test_default_event_is_synthetic_until_explicitly_attested():
    item = RecoveryEvent(
        "tenant-a", "e1", "c1", "2026-10-20T09:00:00+00:00",
        "unanswered", "provider",
    )
    assert item.synthetic
    ledger = RecoveryLedger()
    ledger.append(item)
    assert ledger.report("tenant-a")["calls_observed"] == 0


def test_hours_preview_after_hours_does_not_offer_live_human_transfer(monkeypatch, client):
    monkeypatch.setenv("EMPIRE_INBOUND_RECOVERY_PREVIEW_ENABLED", "true")
    monkeypatch.setenv("EMPIRE_INBOUND_RECOVERY_PREVIEW_TOKEN", "only-inside-tests")
    response = client.post("/v1/inbound-recovery/preview", json={
        "tenant_id": "plumber-1",
        "business_name": "Acme Plumbers",
        "intent": "human",
        "human_transfer_configured": True,
        "staffed_hours": {
            "timezone_name": "Europe/London",
            "when_iso": "2026-10-20T20:00:00+00:00",
            "simulated_verified": True,
            "windows": [
                {"weekday": d, "opens": "09:00", "closes": "17:30"}
                for d in range(5)
            ],
        },
    }, headers={"x-empire-preview-token": "only-inside-tests"})
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "request_human_followup"
    assert body["staffed_hours"]["origin"] == "operator_supplied_simulation_only"
    assert body["staffed_hours"]["open_now"] is False
    assert body["booking_confirmed"] is False
    assert body["provider_connected"] is False


def test_hours_preview_rejects_invalid_or_naive_datetime(monkeypatch, client):
    monkeypatch.setenv("EMPIRE_INBOUND_RECOVERY_PREVIEW_ENABLED", "true")
    monkeypatch.setenv("EMPIRE_INBOUND_RECOVERY_PREVIEW_TOKEN", "only-inside-tests")
    for when_iso in ("not-a-date", "2026-10-20T09:00:00"):
        response = client.post("/v1/inbound-recovery/preview", json={
            "tenant_id": "plumber-1",
            "business_name": "Acme Plumbers",
            "intent": "human",
            "staffed_hours": {
                "timezone_name": "Europe/London",
                "when_iso": when_iso,
                "simulated_verified": True,
            },
        }, headers={"x-empire-preview-token": "only-inside-tests"})
        assert response.status_code == 422


def test_cancelled_booking_not_reported_as_active_recovery_or_paid_money():
    ledger = RecoveryLedger()
    for item in (
        event("unanswered", minute=1),
        event("booking_confirmed", minute=2, verified=True, evidence_ref="calendar-appt-1"),
        event("booking_cancelled", minute=3, verified=True, evidence_ref="calendar-appt-1"),
        event("invoice_paid", minute=4, verified=True, evidence_ref="receipt-after-cancel",
              amount_minor=19000, currency="GBP"),
    ):
        ledger.append(item)
    report = ledger.report("tenant-a")
    assert report["missed_calls"] == 1
    assert report["confirmed_bookings"] == 0
    assert report["verified_recovered_calls"] == 0
    assert report["verified_paid_recovery_minor_by_currency"] == {}


def test_callback_connected_still_counts_when_appointment_cancelled():
    ledger = RecoveryLedger()
    for item in (
        event("unanswered", minute=1),
        event("booking_confirmed", minute=2, verified=True, evidence_ref="calendar-appt-1"),
        event("booking_cancelled", minute=3, verified=True, evidence_ref="calendar-appt-1"),
        event("callback_connected", minute=4, verified=True, evidence_ref="provider-connect-1"),
    ):
        ledger.append(item)
    report = ledger.report("tenant-a")
    assert report["confirmed_bookings"] == 0
    assert report["verified_recovered_calls"] == 1


def test_calendar_cancel_requires_calendar_provenance():
    with pytest.raises(ValueError, match="booking_cancelled_requires_verified_calendar_receipt"):
        event("booking_cancelled", minute=3, origin="operator", verified=True,
              evidence_ref="calendar-appt-1")


def test_calendar_reconfirmation_restores_booking_after_cancel():
    ledger = RecoveryLedger()
    for item in (
        event("unanswered", minute=1),
        event("booking_confirmed", minute=2, verified=True,
              evidence_ref="calendar-appt-1"),
        event("booking_cancelled", minute=3, verified=True,
              evidence_ref="calendar-appt-1"),
        event("booking_confirmed", minute=4, verified=True,
              evidence_ref="calendar-appt-1"),
    ):
        ledger.append(item)
    assert ledger.report("tenant-a")["confirmed_bookings"] == 1
    assert ledger.report("tenant-a")["verified_recovered_calls"] == 1
