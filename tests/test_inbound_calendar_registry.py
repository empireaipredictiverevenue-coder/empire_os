"""Calendar ownership, status history and immutable offline evidence tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.inbound_calendar_registry import OfflineCalendarRegistry
from empire_os.inbound_google_calendar_adapter import (
    ApprovedCalendarBinding, CalendarVerificationError, TrackedCalendarAppointment,
    calendar_proof_to_recovery_event,
)
from empire_os.inbound_contact_identity import pseudonymise_inbound_contact
from empire_os.inbound_revenue_recovery import RecoveryEvent, RecoveryLedger

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
CAL = "tenant-owner-calendar@example.org"
CONTACT = pseudonymise_inbound_contact(
    "+442071234567", tenant_id="tenant-a",
    signing_key="calendar-test-pseudonym-seed-32bytes",
)


def binding(tenant="tenant-a"):
    return ApprovedCalendarBinding(
        tenant_id=tenant, calendar_id=CAL,
        provider_account_ref="provisioned-owner-oauth-ref",
        owner_approved=True, account_access_verified=True,
    )


def link(tenant="tenant-a", call="call-1"):
    return TrackedCalendarAppointment(
        tenant_id=tenant, calendar_id=CAL, event_id="event-a",
        call_id=call, contact_key=CONTACT, tracked_ref="operator-source-ref",
    )


def raw(status="confirmed"):
    if status == "cancelled":
        return {"id": "event-a", "status": "cancelled"}
    return {
        "id": "event-a", "status": status,
        "updated": "2026-10-20T11:59:00Z", "transparency": "opaque",
        "start": {"dateTime": "2026-10-21T10:00:00+01:00"},
        "end": {"dateTime": "2026-10-21T10:30:00+01:00"},
        "extendedProperties": {"private": {
            "empire_recovery_tenant": "tenant-a",
            "empire_recovery_call": "call-1",
            "empire_recovery_ref": "operator-source-ref",
        }},
    }


class FakeCalendar:
    def __init__(self, payload):
        self.payload = payload
        self.count = 0

    def fetch(self, *, method, path, token, body=None):
        self.count += 1
        assert method == "GET" and path.endswith("/events/event-a")
        assert token == "fixture-token"
        return self.payload


def configure(store):
    assert store.register_binding_offline(binding(), approval_ref="approval-by-owner")
    assert store.register_appointment_offline(link())


def test_provisioning_is_durable_and_tenant_owned(tmp_path):
    path = tmp_path / "calendar.db"
    with OfflineCalendarRegistry(path) as store:
        configure(store)
        assert not store.register_binding_offline(binding(), approval_ref="approval-by-owner")
        assert not store.register_appointment_offline(link())
        assert store.tenant_summary("tenant-a")["not_verified"] == 1
        assert store.tenant_summary("tenant-b")["tracked_appointments"] == 0
    with OfflineCalendarRegistry(path, read_only=True) as store:
        assert store.get_binding(CAL).tenant_id == "tenant-a"
        assert store.get_link(calendar_id=CAL, event_id="event-a").call_id == "call-1"
        with pytest.raises(ValueError, match="read_only"):
            store.register_appointment_offline(link())


def test_cannot_reassign_same_owned_calendar_to_another_tenant(tmp_path):
    with OfflineCalendarRegistry(tmp_path / "calendar.db") as store:
        configure(store)
        with pytest.raises(ValueError, match="cannot_be_reassigned"):
            store.register_binding_offline(binding("tenant-b"), approval_ref="new-operator")


def test_cross_tenant_or_wrong_calendar_appointment_fails_closed(tmp_path):
    with OfflineCalendarRegistry(tmp_path / "calendar.db") as store:
        configure(store)
        with pytest.raises(ValueError, match="cross_tenant"):
            store.register_appointment_offline(link("tenant-b"))
        with pytest.raises(ValueError, match="conflicting_calendar_appointment_owner"):
            store.register_appointment_offline(link(call="other-call"))
        with pytest.raises(CalendarVerificationError, match="unregistered"):
            store.verified_readback_offline(
                tenant_id="tenant-b", calendar_id=CAL, event_id="event-a",
                token="fixture-token", transport=FakeCalendar(raw()), observed_at=NOW,
            )


def test_confirm_and_cancel_sparse_then_idempotent_repeat(tmp_path):
    path = tmp_path / "calendar.db"
    with OfflineCalendarRegistry(path) as store:
        configure(store)
        original, created = store.verified_readback_offline(
            tenant_id="tenant-a", calendar_id=CAL, event_id="event-a",
            token="fixture-token", transport=FakeCalendar(raw()), observed_at=NOW,
        )
        assert created and original.status == "confirmed"
        assert store.tenant_summary("tenant-a")["current_confirmed"] == 1
        retry, inserted = store.verified_readback_offline(
            tenant_id="tenant-a", calendar_id=CAL, event_id="event-a",
            token="fixture-token", transport=FakeCalendar(raw()),
            observed_at=NOW + timedelta(minutes=1),
        )
        assert retry.canonical_ref == original.canonical_ref
        assert not inserted  # unchanged Google event revision
        cancel, inserted = store.verified_readback_offline(
            tenant_id="tenant-a", calendar_id=CAL, event_id="event-a",
            token="fixture-token", transport=FakeCalendar(raw("cancelled")),
            observed_at=NOW + timedelta(minutes=2),
        )
        assert inserted and cancel.status == "cancelled"
        assert store.tenant_summary("tenant-a")["current_cancelled"] == 1
        repeat, inserted = store.verified_readback_offline(
            tenant_id="tenant-a", calendar_id=CAL, event_id="event-a",
            token="fixture-token", transport=FakeCalendar(raw("cancelled")),
            observed_at=NOW + timedelta(minutes=3),
        )
        assert inserted and repeat.status == "cancelled"
        assert store.tenant_summary("tenant-a")["current_confirmed"] == 0
    with OfflineCalendarRegistry(path, read_only=True) as store:
        assert store.tenant_summary("tenant-a")["current_cancelled"] == 1
        assert store.current_proof(calendar_id=CAL, event_id="event-a").status == "cancelled"


def test_no_orphaned_cancellation_or_untrusted_provider_response(tmp_path):
    path = tmp_path / "calendar.db"
    with OfflineCalendarRegistry(path) as store:
        configure(store)
        with pytest.raises(CalendarVerificationError, match="cancel_not_linked"):
            store.verified_readback_offline(
                tenant_id="tenant-a", calendar_id=CAL, event_id="event-a",
                token="fixture-token", transport=FakeCalendar(raw("cancelled")),
                observed_at=NOW,
            )
        with pytest.raises(CalendarVerificationError, match="provenance_missing"):
            data = raw()
            data["extendedProperties"]["private"]["empire_recovery_call"] = "forged"
            store.verified_readback_offline(
                tenant_id="tenant-a", calendar_id=CAL, event_id="event-a",
                token="fixture-token", transport=FakeCalendar(data),
                observed_at=NOW,
            )
        assert store.tenant_summary("tenant-a")["not_verified"] == 1


def test_verified_readback_bridges_into_revenue_ledger_without_booking_write(tmp_path):
    with OfflineCalendarRegistry(tmp_path / "calendar.db") as store:
        configure(store)
        proof, created = store.verified_readback_offline(
            tenant_id="tenant-a", calendar_id=CAL, event_id="event-a",
            token="fixture-token", transport=FakeCalendar(raw()), observed_at=NOW,
        )
    missed = RecoveryEvent(
        tenant_id="tenant-a", event_id="missed-1", call_id="call-1",
        occurred_at=(NOW - timedelta(minutes=5)).isoformat(),
        kind="unanswered", origin="provider", synthetic=False, verified=True,
    )
    ledger = RecoveryLedger()
    ledger.append(missed)
    ledger.append(calendar_proof_to_recovery_event(proof))
    score = ledger.report("tenant-a")
    assert score["confirmed_bookings"] == 1
    assert score["verified_recovered_calls"] == 1
    assert score["verified_paid_recovery_minor_by_currency"] == {}
    assert score["live_routing_modified"] is False


def test_missing_read_only_db_must_not_be_created(tmp_path):
    file = tmp_path / "none.db"
    with pytest.raises(ValueError, match="existing_calendar_registry"):
        OfflineCalendarRegistry(file, read_only=True)
    assert not file.exists()


def test_readback_integrity_detects_corruption(tmp_path):
    with OfflineCalendarRegistry(tmp_path / "calendar.db") as store:
        configure(store)
        store.verified_readback_offline(
            tenant_id="tenant-a", calendar_id=CAL, event_id="event-a",
            token="fixture-token", transport=FakeCalendar(raw()), observed_at=NOW,
        )
        store.db.execute("UPDATE calendar_status_reads SET proof_json='{}'")
        store.db.commit()
        with pytest.raises(ValueError, match="integrity_failure"):
            store.current_proof(calendar_id=CAL, event_id="event-a")


def test_proof_is_not_account_token_or_customer_pii(tmp_path):
    with OfflineCalendarRegistry(tmp_path / "calendar.db") as store:
        configure(store)
        store.verified_readback_offline(
            tenant_id="tenant-a", calendar_id=CAL, event_id="event-a",
            token="fixture-token", transport=FakeCalendar(raw()), observed_at=NOW,
        )
        report = store.tenant_summary("tenant-a")
        assert "fixture-token" not in str(report)
        assert CONTACT not in str(report)
        assert not report["revenue_inferred"]
        assert not report["bookings_created"]


def test_history_uses_actual_time_across_timezone_offsets(tmp_path):
    from datetime import timezone
    path = tmp_path / "timezones.db"
    with OfflineCalendarRegistry(path) as registry:
        configure(registry)
        registry.verified_readback_offline(
            tenant_id="tenant-a", calendar_id=CAL, event_id="event-a",
            token="fixture-token", transport=FakeCalendar(raw()),
            observed_at=NOW.astimezone(timezone(timedelta(hours=2))),
        )
        registry.verified_readback_offline(
            tenant_id="tenant-a", calendar_id=CAL, event_id="event-a",
            token="fixture-token", transport=FakeCalendar(raw("cancelled")),
            observed_at=NOW + timedelta(minutes=30),
        )
        assert registry.current_proof(
            calendar_id=CAL, event_id="event-a"
        ).status == "cancelled"
        assert registry.tenant_summary("tenant-a")["current_cancelled"] == 1
