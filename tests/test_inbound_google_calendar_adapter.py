"""Read-only Google Calendar adapter checks with deterministic fake transport.

No OAuth tokens, provider accounts or network requests are made in these tests.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest

from empire_os.inbound_google_calendar_adapter import (
    ApprovedCalendarBinding, CalendarVerificationError,
    GoogleCalendarReadOnlyHTTP, TrackedCalendarAppointment,
    calendar_proof_to_recovery_event, calendar_proof_to_workflow_event,
    verify_google_booking_readback, verify_google_freebusy_readback,
)
from empire_os.inbound_revenue_recovery import RecoveryLedger
from empire_os.inbound_booking_workflow import WorkflowPolicy, summarise_inbound_workflow
from empire_os.inbound_contact_identity import pseudonymise_inbound_contact

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
SECRET = "test-contact-hmac-key-for-calendar-32-bytes"
CONTACT = pseudonymise_inbound_contact(
    "+442077771234", tenant_id="tenant-one", signing_key=SECRET
)
CAL = "owner-calendar@example.org"


def binding():
    return ApprovedCalendarBinding(
        tenant_id="tenant-one", calendar_id=CAL,
        provider_account_ref="approved-oauth-account-1",
        owner_approved=True, account_access_verified=True,
    )


def link():
    return TrackedCalendarAppointment(
        tenant_id="tenant-one", calendar_id=CAL, event_id="event-1234",
        call_id="inbound-call-1", contact_key=CONTACT,
        tracked_ref="tenant-controlled-booking-intent-1",
    )


def provider_event(*, status="confirmed", metadata=True):
    props = {
        "empire_recovery_tenant": "tenant-one",
        "empire_recovery_call": "inbound-call-1",
        "empire_recovery_ref": "tenant-controlled-booking-intent-1",
    }
    return {
        "kind": "calendar#event", "id": "event-1234",
        "status": status, "transparency": "opaque",
        "updated": "2026-10-20T11:58:00Z",
        "start": {"dateTime": "2026-10-21T10:00:00+01:00"},
        "end": {"dateTime": "2026-10-21T10:30:00+01:00"},
        "extendedProperties": {"private": props if metadata else {}},
    }


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def fetch(self, *, method, path, token, body=None):
        self.calls.append((method, path, body))
        assert token == "fixture-readonly-token"
        return self.response


def read(provider_payload=None, *, bind=None, booking=None, prior=None):
    transport = FakeTransport(provider_payload or provider_event())
    proof = verify_google_booking_readback(
        binding=bind or binding(), link=booking or link(),
        token="fixture-readonly-token", transport=transport,
        observed_at=NOW, previously_verified=prior,
    )
    assert transport.calls == [
        ("GET", f"/calendar/v3/calendars/{quote(CAL, safe='')}/events/event-1234", None)
    ]
    return proof


def test_verified_google_confirmed_booking_yields_both_evidence_contracts():
    proof = read()
    assert proof.status == "confirmed"
    assert proof.canonical_ref.startswith("gcal:")
    assert proof.live_booking_writes is False
    assert proof.customer_contact_authorized is False
    recovered = calendar_proof_to_recovery_event(proof)
    workflow = calendar_proof_to_workflow_event(proof, contact_key=CONTACT)
    assert recovered.kind == "booking_confirmed"
    assert recovered.origin == "calendar"
    assert recovered.verified and not recovered.synthetic
    assert workflow.kind == "calendar_booking_confirmed"
    assert workflow.appointment_id == "event-1234"
    assert workflow.calendar_ref == CAL
    assert workflow.evidence_ref == recovered.evidence_ref


def test_cancelled_booking_reconciles_existing_recovery_evidence():
    prior = read()
    sparse_cancel = {"id": "event-1234", "status": "cancelled"}
    cancelled = read(sparse_cancel, prior=prior)
    assert cancelled.status == "cancelled"
    first = calendar_proof_to_recovery_event(prior)
    second = calendar_proof_to_recovery_event(
        replace(cancelled, observed_at=(NOW + timedelta(minutes=1)).isoformat())
    )
    ledger = RecoveryLedger()
    from empire_os.inbound_revenue_recovery import RecoveryEvent
    ledger.append(RecoveryEvent(
        tenant_id="tenant-one", event_id="missed-1", call_id="inbound-call-1",
        occurred_at=(NOW - timedelta(minutes=10)).isoformat(),
        kind="unanswered", origin="provider", verified=True, synthetic=False,
    ))
    ledger.append(first)
    ledger.append(second)
    assert ledger.report("tenant-one")["confirmed_bookings"] == 0
    assert ledger.report("tenant-one")["verified_recovered_calls"] == 0
    w1 = calendar_proof_to_workflow_event(prior, contact_key=CONTACT)
    w2 = calendar_proof_to_workflow_event(
        replace(cancelled, observed_at=(NOW + timedelta(minutes=1)).isoformat()),
        contact_key=CONTACT,
    )
    result = summarise_inbound_workflow(
        [w1, w2], policy=WorkflowPolicy("tenant-one"), as_of=NOW + timedelta(minutes=10),
    )
    assert result["active_calendar_confirmations"] == 0
    assert result["calendar_cancellations"] == 1


def test_just_any_calendar_event_cannot_be_claimed_as_inbound_sale():
    with pytest.raises(CalendarVerificationError, match="private_call_provenance"):
        read(provider_event(metadata=False))


@pytest.mark.parametrize("wrong_field", [
    "empire_recovery_tenant", "empire_recovery_call", "empire_recovery_ref",
])
def test_tenant_call_ref_metadata_must_match(wrong_field):
    raw = provider_event()
    raw["extendedProperties"]["private"][wrong_field] = "another-business"
    with pytest.raises(CalendarVerificationError, match="private_call_provenance"):
        read(raw)


def test_cannot_use_an_unapproved_calendar_or_cross_tenant_link():
    with pytest.raises(CalendarVerificationError, match="not_owner_approved"):
        read(bind=replace(binding(), owner_approved=False))
    with pytest.raises(CalendarVerificationError, match="cross_tenant"):
        read(booking=replace(link(), tenant_id="tenant-two"))


def test_cancelled_without_prior_verified_link_is_not_a_valid_receipt():
    with pytest.raises(CalendarVerificationError, match="cancel_not_linked"):
        read({"id": "event-1234", "status": "cancelled"})
    another = replace(read(), call_id="someone-else")
    with pytest.raises(CalendarVerificationError, match="cancel_not_linked"):
        read({"id": "event-1234", "status": "cancelled"}, prior=another)


@pytest.mark.parametrize("status", ["tentative", "needsAction", "unknown"])
def test_nonconfirmed_status_does_not_claim_a_booking(status):
    with pytest.raises(CalendarVerificationError, match="status_not_verified"):
        read(provider_event(status=status))


def test_all_day_and_transparent_events_do_not_count_as_a_confirmed_booking():
    raw = provider_event()
    raw["start"] = {"date": "2026-10-21"}
    with pytest.raises(CalendarVerificationError, match="all_day"):
        read(raw)
    transparent = provider_event()
    transparent["transparency"] = "transparent"
    with pytest.raises(CalendarVerificationError, match="transparent"):
        read(transparent)


def test_invalid_event_id_or_updated_timestamp_fails_closed():
    wrong_id = provider_event()
    wrong_id["id"] = "not-the-owned-appointment"
    with pytest.raises(CalendarVerificationError, match="appointment_id_mismatch"):
        read(wrong_id)
    future = provider_event()
    future["updated"] = "2027-01-01T12:00:00Z"
    with pytest.raises(CalendarVerificationError, match="updated_time_in_future"):
        read(future)


def test_provider_response_must_be_verified_not_malformed():
    with pytest.raises(CalendarVerificationError):
        read({"id": "event-1234", "status": "confirmed", "extendedProperties": None})


def freebusy_reply(busy=None):
    return {
        "kind": "calendar#freeBusy",
        "calendars": {CAL: {"busy": busy or []}},
    }


def fb(payload=None):
    transport = FakeTransport(payload if payload is not None else freebusy_reply())
    value = verify_google_freebusy_readback(
        binding=binding(),
        time_min=NOW, time_max=NOW + timedelta(minutes=30),
        token="fixture-readonly-token", transport=transport,
    )
    assert transport.calls == [(
        "POST", "/calendar/v3/freeBusy",
        {
            "timeMin": NOW.isoformat(),
            "timeMax": (NOW + timedelta(minutes=30)).isoformat(),
            "items": [{"id": CAL}],
        },
    )]
    return value


def test_freebusy_not_busy_does_not_claim_booking_or_bookability():
    value = fb()
    assert value.calendar_busy is False
    assert value.available_slot_confirmed is False
    assert value.booking_confirmed is False
    assert value.action_authorized is False


def test_freebusy_detects_real_interval_overlap():
    value = fb(freebusy_reply([{
        "start": (NOW + timedelta(minutes=5)).isoformat(),
        "end": (NOW + timedelta(minutes=10)).isoformat(),
    }]))
    assert value.calendar_busy is True


def test_freebusy_bad_identity_or_provider_errors_are_fail_closed():
    with pytest.raises(CalendarVerificationError, match="identity_mismatch"):
        fb({"kind": "calendar#freeBusy", "calendars": {"other@corp": {"busy": []}}})
    with pytest.raises(CalendarVerificationError, match="provider_error"):
        fb({"kind": "calendar#freeBusy", "calendars": {
            CAL: {"busy": [], "errors": [{"reason": "notFound"}]}
        }})


def test_freebusy_rejects_missing_busy_and_invalid_intervals():
    with pytest.raises(CalendarVerificationError, match="interval_invalid"):
        fb({"kind": "calendar#freeBusy", "calendars": {CAL: {"errors": []}}})
    with pytest.raises(CalendarVerificationError, match="interval_invalid"):
        fb(freebusy_reply([{
            "start": NOW.isoformat(), "end": (NOW - timedelta(minutes=1)).isoformat(),
        }]))


def test_freebusy_range_and_access_must_be_valid():
    with pytest.raises(CalendarVerificationError, match="range"):
        verify_google_freebusy_readback(
            binding=binding(), time_min=NOW, time_max=NOW + timedelta(days=1),
            token="fixture-readonly-token", transport=FakeTransport(freebusy_reply()),
        )
    with pytest.raises(CalendarVerificationError, match="not_owner_approved"):
        verify_google_freebusy_readback(
            binding=replace(binding(), account_access_verified=False),
            time_min=NOW, time_max=NOW + timedelta(minutes=30),
            token="fixture-readonly-token", transport=FakeTransport(freebusy_reply()),
        )


def test_real_http_transport_rejects_all_nonlisted_endpoints_before_network():
    transport = GoogleCalendarReadOnlyHTTP()
    for method, path in [
        ("DELETE", "/calendar/v3/calendars/" + CAL + "/events/123"),
        ("POST", "/calendar/v3/calendars/" + CAL + "/events/123"),
        ("GET", "/calendar/v3/calendars/owned/events/a?evil=1"),
        ("GET", "/calendar/v3/calendars/owned/events/a//redirect"),
        ("POST", "/calendar/v3/other"),
    ]:
        with pytest.raises(CalendarVerificationError, match="method_denied"):
            transport.fetch(method=method, path=path, token="fixture-readonly-token")


def test_metadata_enforcement_cannot_be_bypassed_by_calendar_id_encoding():
    with pytest.raises(CalendarVerificationError, match="cross_tenant"):
        read(booking=replace(link(), calendar_id="unapproved@example.org"))


def test_old_calendar_confirmation_revision_cannot_resurrect_cancelled_booking():
    earlier = read()
    cancelled = read({"id": "event-1234", "status": "cancelled"}, prior=earlier)
    old_confirm = provider_event()
    with pytest.raises(CalendarVerificationError, match="stale_reconfirmation"):
        verify_google_booking_readback(
            binding=binding(), link=link(), token="fixture-readonly-token",
            transport=FakeTransport(old_confirm),
            observed_at=NOW + timedelta(minutes=5),
            previously_verified=replace(
                cancelled, observed_at=(NOW + timedelta(minutes=2)).isoformat()
            ),
        )


def test_fresh_revision_can_reconfirm_after_calendar_cancellation():
    earlier = read()
    cancelled = read({"id": "event-1234", "status": "cancelled"}, prior=earlier)
    changed = provider_event()
    changed["updated"] = (NOW + timedelta(minutes=3)).isoformat()
    reconfirmed = verify_google_booking_readback(
        binding=binding(), link=link(), token="fixture-readonly-token",
        transport=FakeTransport(changed),
        observed_at=NOW + timedelta(minutes=5),
        previously_verified=replace(
            cancelled, observed_at=(NOW + timedelta(minutes=2)).isoformat()
        ),
    )
    assert reconfirmed.status == "confirmed"
    assert reconfirmed.provider_updated_at == changed["updated"]
    assert not reconfirmed.live_booking_writes
