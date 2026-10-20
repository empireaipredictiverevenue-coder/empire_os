"""No synthetic workflow becomes a real booking or contact authority."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.inbound_booking_workflow import (
    InboundWorkflowEvent, WorkflowPolicy, summarise_inbound_workflow,
)
from empire_os.inbound_contact_identity import pseudonymise_inbound_contact

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
SECRET = "tenant-private-test-pseudonym-key-minimum32"
KEY = pseudonymise_inbound_contact("+442071234567", tenant_id="tenant-a", signing_key=SECRET)
OTHER = pseudonymise_inbound_contact("+442079876543", tenant_id="tenant-a", signing_key=SECRET)
CAL = "calendar-tenant-a-01"


def event(kind, *, minute=0, call="call-1", tenant="tenant-a", contact=KEY,
          eid=None, verified=True, synthetic=False, appointment_id="appt-1"):
    booking = kind.startswith("calendar_booking_")
    return InboundWorkflowEvent(
        tenant_id=tenant, call_id=call, contact_key=contact,
        event_id=eid or f"{call}:{kind}:{minute}",
        kind=kind,
        occurred_at=(NOW + timedelta(minutes=minute)).isoformat(),
        origin=(
            "calendar_adapter" if booking else
            "voice_provider" if kind == "callback_connected" else
            "operator_review"
        ),
        evidence_ref=f"evidence:{call}:{kind}:{minute}",
        verified=verified, synthetic=synthetic,
        consent_expires_at=(
            (NOW + timedelta(hours=2)).isoformat()
            if kind == "callback_consent_granted" else None
        ),
        appointment_id=appointment_id if booking else None,
        calendar_ref=CAL if booking else None,
        appointment_starts_at=(NOW + timedelta(days=1)).isoformat() if booking else None,
        appointment_ends_at=(NOW + timedelta(days=1, minutes=30)).isoformat() if booking else None,
    )


def report(events, *, at=NOW + timedelta(minutes=30), **kwargs):
    return summarise_inbound_workflow(
        events, policy=WorkflowPolicy("tenant-a", **kwargs), as_of=at
    )


def test_callback_request_without_explicit_consent_never_eligible():
    result = report([event("callback_requested")])
    assert result["call_workflows_total"] == 1
    assert result["operator_callback_reviews"] == 0
    assert result["workflows"][0]["callback_state"] == "hold_consent_unverified_or_expired"
    assert result["outbound_sent"] is False


def test_explicit_scoped_consent_enables_operator_review_not_contact():
    result = report([
        event("callback_requested", minute=0),
        event("callback_consent_granted", minute=2),
    ])
    assert result["operator_callback_reviews"] == 1
    assert result["workflows"][0]["callback_state"] == "operator_review_eligible"
    assert result["workflows"][0]["no_customer_contact_authority"] is True


def test_expired_consent_blocks_outreach_even_if_request_remains():
    result = report([
        event("callback_requested", minute=0),
        event("callback_consent_granted", minute=1),
    ], at=NOW + timedelta(hours=4))
    assert result["workflows"][0]["callback_state"] == "hold_consent_unverified_or_expired"


def test_explicit_revocation_supersedes_earlier_consent():
    result = report([
        event("callback_requested"),
        event("callback_consent_granted", minute=1),
        event("callback_consent_revoked", minute=2),
    ])
    assert result["operator_callback_reviews"] == 0


def test_optout_applies_across_calls_and_newer_consent_cannot_override():
    result = report([
        event("followup_opt_out", minute=-10, call="old"),
        event("callback_requested", minute=0, call="new"),
        event("callback_consent_granted", minute=1, call="new"),
    ])
    lookup = {x["call_id"]: x for x in result["workflows"]}
    assert lookup["new"]["callback_state"] == "suppressed_opt_out"
    assert result["operator_callback_reviews"] == 0
    assert result["suppressed_callback_workflows"] == 2


def test_old_optout_persists_beyond_general_lookback():
    result = report([
        event("followup_opt_out", minute=-60 * 24 * 200, call="older"),
        event("callback_requested", minute=0, call="recent"),
        event("callback_consent_granted", minute=2, call="recent"),
    ], max_age_days=90)
    lookup = {x["call_id"]: x for x in result["workflows"]}
    assert lookup["recent"]["callback_state"] == "suppressed_opt_out"


def test_booking_request_is_not_calendar_confirmation():
    result = report([event("appointment_requested")])
    assert result["appointment_requests"] == 1
    assert result["active_calendar_confirmations"] == 0
    assert result["bookings_created"] is False


def test_independently_attested_calendar_confirmation_is_counted_offline():
    result = report([
        event("appointment_requested", minute=0),
        event("calendar_booking_confirmed", minute=5),
    ])
    assert result["active_calendar_confirmations"] == 1
    assert result["workflows"][0]["appointment_requested"] is True
    assert result["revenue_inferred"] is False
    assert result["bookings_created"] is False


def test_calendar_cancellation_reverts_active_confirmation():
    result = report([
        event("appointment_requested"),
        event("calendar_booking_confirmed", minute=3),
        event("calendar_booking_cancelled", minute=4),
    ])
    assert result["active_calendar_confirmations"] == 0
    assert result["calendar_cancellations"] == 1


def test_reconfirmation_after_cancel_updates_current_state():
    result = report([
        event("calendar_booking_confirmed", minute=3),
        event("calendar_booking_cancelled", minute=4),
        event("calendar_booking_confirmed", minute=5),
    ])
    assert result["active_calendar_confirmations"] == 1
    assert result["calendar_cancellations"] == 0


def test_same_calendar_appointment_attributed_to_two_calls_is_quarantined():
    result = report([
        event("calendar_booking_confirmed", minute=1, call="c1", appointment_id="a1"),
        event("calendar_booking_confirmed", minute=2, call="c2", appointment_id="a1"),
    ])
    assert result["calendar_identity_conflicts"] == 1
    assert result["active_calendar_confirmations"] == 0


def test_different_customer_contact_keys_block_call_suggestion():
    result = report([
        event("callback_requested", minute=0),
        event("callback_consent_granted", minute=2, contact=OTHER),
    ])
    assert result["workflows"][0]["callback_state"] == "hold_conflicting_contact_identity"


def test_unverified_and_synthetic_events_are_excluded():
    result = report([
        event("callback_requested", verified=False),
        event("callback_consent_granted", minute=1, synthetic=True),
    ])
    assert result["call_workflows_total"] == 0
    assert result["unverified_events_excluded"] == 2


def test_future_events_and_cross_tenant_are_excluded():
    result = report([
        event("callback_requested", minute=90),
        event("callback_requested", call="outsider", tenant="tenant-b"),
    ])
    assert result["call_workflows_total"] == 0
    assert result["future_events_excluded"] == 1


def test_contact_keys_not_in_report():
    result = report([event("callback_requested")])
    assert KEY not in str(result)
    assert "+442071234567" not in str(result)
    assert result["contact_keys_returned"] is False


def test_replayed_event_id_is_idempotent_and_conflicts_fail():
    first = event("callback_requested")
    assert report([first, first])["call_workflows_total"] == 1
    with pytest.raises(ValueError, match="conflicting_workflow_event"):
        report([first, replace(first, call_id="other")])


def test_invalid_calendar_receipts_fail_validation():
    first = event("calendar_booking_confirmed")
    with pytest.raises(ValueError, match="invalid_workflow_event_origin"):
        InboundWorkflowEvent(
            tenant_id=first.tenant_id, event_id=first.event_id, call_id=first.call_id,
            contact_key=first.contact_key, kind=first.kind, occurred_at=first.occurred_at,
            origin="operator_review", evidence_ref=first.evidence_ref,
            appointment_id="appt", calendar_ref=CAL,
            appointment_starts_at=first.appointment_starts_at,
            appointment_ends_at=first.appointment_ends_at,
        )
    with pytest.raises(ValueError, match="calendar_booking_receipt_fields"):
        replace(first, appointment_id=None)


def test_consent_duration_must_be_no_more_than_thirty_days():
    granted = event("callback_consent_granted")
    with pytest.raises(ValueError, match="duration_exceeded"):
        replace(granted, consent_expires_at=(NOW + timedelta(days=31)).isoformat())


def test_pseudonymous_contact_is_scoped_and_hardened():
    one = pseudonymise_inbound_contact("+442071234567", tenant_id="tenant-a", signing_key=SECRET)
    two = pseudonymise_inbound_contact("+442071234567", tenant_id="tenant-b", signing_key=SECRET)
    assert one != two
    assert one == KEY and len(one) == 64
    assert "+442071234567" not in one
    with pytest.raises(ValueError, match="valid_e164_phone"):
        pseudonymise_inbound_contact("020 7123 4567", tenant_id="tenant-a", signing_key=SECRET)
    with pytest.raises(ValueError, match="key_not_configured"):
        pseudonymise_inbound_contact("+442071234567", tenant_id="tenant-a", signing_key="short")


def test_policy_bounds_and_timezone_required():
    with pytest.raises(ValueError, match="policy"):
        WorkflowPolicy("tenant-a", max_calls=0)
    with pytest.raises(ValueError, match="timezone_required"):
        report([event("callback_requested")], at=datetime(2026, 10, 20, 12))
