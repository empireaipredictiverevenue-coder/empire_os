"""Crash-safe local calendar evidence forwarding, no provider writes."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from empire_os.inbound_booking_store import OfflineBookingWorkflowStore
from empire_os.inbound_calendar_projection import project_calendar_evidence_offline
from empire_os.inbound_calendar_registry import OfflineCalendarRegistry
from empire_os.inbound_contact_identity import pseudonymise_inbound_contact
from empire_os.inbound_google_calendar_adapter import (
    ApprovedCalendarBinding, TrackedCalendarAppointment,
)
from empire_os.inbound_recovery_store import OfflineRecoveryStore
from empire_os.inbound_revenue_recovery import RecoveryEvent
from empire_os.inbound_booking_workflow import WorkflowPolicy

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
CAL = "owner-approved@example.org"
SECRET = "private-calendar-projection-hmac-32-bytes"
CONTACT = pseudonymise_inbound_contact(
    "+442071234567", tenant_id="alpha", signing_key=SECRET,
)


class Readback:
    def __init__(self, status="confirmed"):
        self.status = status
        self.calls = 0

    def fetch(self, *, method, path, token, body=None):
        self.calls += 1
        assert method == "GET" and path.endswith("/events/appt-1")
        assert token == "fixture-token"
        if self.status == "cancelled":
            return {"id": "appt-1", "status": "cancelled"}
        return {
            "id": "appt-1", "status": "confirmed",
            "updated": "2026-10-20T11:59:00Z",
            "transparency": "opaque",
            "start": {"dateTime": "2026-10-21T10:00:00+01:00"},
            "end": {"dateTime": "2026-10-21T10:30:00+01:00"},
            "extendedProperties": {"private": {
                "empire_recovery_tenant": "alpha",
                "empire_recovery_call": "inbound-1",
                "empire_recovery_ref": "owner-approved-booking-intent",
            }},
        }


def provision(registry):
    registry.register_binding_offline(
        ApprovedCalendarBinding(
            tenant_id="alpha", calendar_id=CAL,
            provider_account_ref="owner-approved-account",
            owner_approved=True, account_access_verified=True,
        ),
        approval_ref="signed-owner-approval",
    )
    registry.register_appointment_offline(TrackedCalendarAppointment(
        tenant_id="alpha", calendar_id=CAL, event_id="appt-1",
        call_id="inbound-1", contact_key=CONTACT,
        tracked_ref="owner-approved-booking-intent",
    ))


def read(registry, status="confirmed", minutes=0):
    return registry.verified_readback_offline(
        tenant_id="alpha", calendar_id=CAL, event_id="appt-1",
        token="fixture-token", transport=Readback(status),
        observed_at=NOW + timedelta(minutes=minutes),
    )


def stores(tmp_path):
    return (
        OfflineCalendarRegistry(tmp_path / "calendar.db"),
        OfflineRecoveryStore(tmp_path / "recovery.db"),
        OfflineBookingWorkflowStore(tmp_path / "workflow.db"),
    )


def missed():
    return RecoveryEvent(
        tenant_id="alpha", event_id="missed-1", call_id="inbound-1",
        occurred_at=(NOW - timedelta(minutes=30)).isoformat(),
        kind="unanswered", origin="provider", verified=True, synthetic=False,
    )


def reconcile(registry, recovery, workflow, *, at=None):
    return project_calendar_evidence_offline(
        registry=registry, recovery=recovery, workflow=workflow,
        tenant_id="alpha", as_of=at or NOW + timedelta(minutes=10),
    )


def test_verified_status_replayed_to_both_stores_with_ack(tmp_path):
    with stores(tmp_path)[0] as registry, stores(tmp_path)[1] as recovery, stores(tmp_path)[2] as workflow:
        provision(registry)
        recovery.append_offline(missed())
        proof, created = read(registry)
        assert created
        assert registry.projection_counts("alpha") == {"pending": 1, "complete": 0}
        result = reconcile(registry, recovery, workflow)
        assert result.acknowledged == 1
        assert result.recovery_events_added == 1
        assert result.workflow_events_added == 1
        assert registry.projection_counts("alpha") == {"pending": 0, "complete": 1}
        assert recovery.report("alpha")["confirmed_bookings"] == 1
        assert recovery.report("alpha")["verified_recovered_calls"] == 1
        assert workflow.summary(WorkflowPolicy("alpha"), as_of=NOW + timedelta(minutes=10))["active_calendar_confirmations"] == 1
        again = reconcile(registry, recovery, workflow)
        assert again.acknowledged == 0
        assert again.recovery_events_added == 0
        assert again.workflow_events_added == 0
        assert result.live_calendar_writes is False


def test_calendar_cancellation_is_forwarded_and_reverses_recovery(tmp_path):
    registry, recovery, workflow = stores(tmp_path)
    with registry, recovery, workflow:
        provision(registry)
        recovery.append_offline(missed())
        read(registry)
        reconcile(registry, recovery, workflow)
        read(registry, "cancelled", 3)
        result = reconcile(registry, recovery, workflow)
        assert result.acknowledged == 1
        assert recovery.report("alpha")["confirmed_bookings"] == 0
        assert recovery.report("alpha")["verified_recovered_calls"] == 0
        assert workflow.summary(WorkflowPolicy("alpha"), as_of=NOW + timedelta(minutes=10))["calendar_cancellations"] == 1


def test_partial_second_store_failure_is_retried_without_double_count(tmp_path):
    registry, recovery, workflow = stores(tmp_path)
    with registry, recovery, workflow:
        provision(registry)
        recovery.append_offline(missed())
        read(registry)
        with patch.object(workflow, "append_offline", side_effect=OSError("injected offline disk failure")):
            with pytest.raises(OSError, match="disk failure"):
                reconcile(registry, recovery, workflow)
        assert registry.projection_counts("alpha") == {"pending": 1, "complete": 0}
        assert recovery.report("alpha")["confirmed_bookings"] == 1
        assert workflow.events_for_tenant("alpha") == ()
        result = reconcile(registry, recovery, workflow)
        assert result.acknowledged == 1
        assert result.recovery_events_added == 0
        assert result.workflow_events_added == 1
        assert recovery.report("alpha")["confirmed_bookings"] == 1
        assert registry.projection_counts("alpha")["pending"] == 0


def test_projection_never_reads_other_tenant_and_unknown_tenant_does_not_mutate(tmp_path):
    registry, recovery, workflow = stores(tmp_path)
    with registry, recovery, workflow:
        provision(registry)
        read(registry)
        other = project_calendar_evidence_offline(
            registry=registry, recovery=recovery, workflow=workflow,
            tenant_id="beta", as_of=NOW + timedelta(minutes=10),
        )
        assert other.acknowledged == 0
        assert registry.projection_counts("alpha")["pending"] == 1
        assert recovery.events_for_tenant("alpha") == ()
        assert workflow.events_for_tenant("alpha") == ()


def test_future_readback_is_not_projected_early(tmp_path):
    registry, recovery, workflow = stores(tmp_path)
    with registry, recovery, workflow:
        provision(registry)
        read(registry, minutes=5)
        early = reconcile(registry, recovery, workflow, at=NOW + timedelta(minutes=3))
        assert early.acknowledged == 0
        assert early.remaining_pending == 1
        later = reconcile(registry, recovery, workflow, at=NOW + timedelta(minutes=6))
        assert later.acknowledged == 1


def test_read_only_and_invalid_limits_fail_closed(tmp_path):
    registry, recovery, workflow = stores(tmp_path)
    with registry, recovery, workflow:
        provision(registry)
        read(registry)
        with pytest.raises(ValueError, match="batch_limit"):
            project_calendar_evidence_offline(
                registry=registry, recovery=recovery, workflow=workflow,
                tenant_id="alpha", as_of=NOW, limit=0,
            )
    with OfflineCalendarRegistry(tmp_path / "calendar.db", read_only=True) as ro_registry, \
         OfflineRecoveryStore(tmp_path / "recovery.db") as rec, \
         OfflineBookingWorkflowStore(tmp_path / "workflow.db") as wf:
        with pytest.raises(ValueError, match="writable_offline_stores"):
            reconcile(ro_registry, rec, wf)


def test_tampered_unprojected_proof_blocks_before_target_writes(tmp_path):
    registry, recovery, workflow = stores(tmp_path)
    with registry, recovery, workflow:
        provision(registry)
        read(registry)
        registry.db.execute("UPDATE calendar_status_reads SET proof_json='{}'")
        registry.db.commit()
        with pytest.raises(ValueError, match="integrity_failure"):
            reconcile(registry, recovery, workflow)
        assert recovery.events_for_tenant("alpha") == ()
        assert workflow.events_for_tenant("alpha") == ()
