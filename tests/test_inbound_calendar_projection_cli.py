"""Calendar projection CLI must never trigger live contact or calendar writes."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys

from empire_os.inbound_booking_store import OfflineBookingWorkflowStore
from empire_os.inbound_calendar_registry import OfflineCalendarRegistry
from empire_os.inbound_contact_identity import pseudonymise_inbound_contact
from empire_os.inbound_google_calendar_adapter import (
    ApprovedCalendarBinding, TrackedCalendarAppointment,
)
from empire_os.inbound_recovery_store import OfflineRecoveryStore

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
CAL = "owner-example@example.org"


class FakeGoogle:
    def fetch(self, *, method, path, token, body=None):
        assert token == "local-test-token" and method == "GET"
        return {
            "id": "appt-1", "status": "confirmed",
            "updated": "2026-10-20T11:59:00Z",
            "transparency": "opaque",
            "start": {"dateTime": "2026-10-21T10:00:00+01:00"},
            "end": {"dateTime": "2026-10-21T10:30:00+01:00"},
            "extendedProperties": {"private": {
                "empire_recovery_tenant": "alpha",
                "empire_recovery_call": "call-1",
                "empire_recovery_ref": "owner-tracked",
            }},
        }


def fixture(tmp_path):
    a, b, c = (tmp_path / n for n in ("calendar.db", "recovery.db", "workflow.db"))
    with OfflineCalendarRegistry(a) as registry:
        registry.register_binding_offline(ApprovedCalendarBinding(
            tenant_id="alpha", calendar_id=CAL,
            provider_account_ref="owner-authorized",
            owner_approved=True, account_access_verified=True,
        ), approval_ref="owner-consent")
        registry.register_appointment_offline(TrackedCalendarAppointment(
            tenant_id="alpha", calendar_id=CAL,
            event_id="appt-1", call_id="call-1",
            contact_key=pseudonymise_inbound_contact(
                "+442071234567", tenant_id="alpha",
                signing_key="private-cli-calendar-key-minimum-32",
            ), tracked_ref="owner-tracked",
        ))
        registry.verified_readback_offline(
            tenant_id="alpha", calendar_id=CAL, event_id="appt-1",
            token="local-test-token", transport=FakeGoogle(), observed_at=NOW,
        )
    with OfflineRecoveryStore(b), OfflineBookingWorkflowStore(c):
        pass
    return a, b, c


def call(*args):
    return subprocess.run(
        [sys.executable, "-B", "-m",
         "scripts.review_inbound_calendar_projection_20261020",
         *map(str, args)],
        capture_output=True, text=True,
    )


def test_cli_readonly_backlog_and_explicit_local_ack(tmp_path):
    a, b, c = fixture(tmp_path)
    before = a.stat().st_size
    read_args = ("--calendar-db", a, "--tenant-id", "alpha", "--read-only")
    state = call(*read_args)
    assert state.returncode == 0, state.stderr
    assert json.loads(state.stdout)["pending"] == 1
    assert a.stat().st_size == before

    apply = call(
        "--calendar-db", a, "--recovery-db", b,
        "--workflow-db", c, "--tenant-id", "alpha",
        "--as-of", (NOW + timedelta(minutes=5)).isoformat(),
        "--apply-local-evidence-replay",
    )
    assert apply.returncode == 0, apply.stderr
    result = json.loads(apply.stdout)
    assert result["acknowledged"] == 1
    assert result["recovery_events_added"] == 1
    assert result["workflow_events_added"] == 1
    assert result["live_calendar_writes"] is False
    assert result["messages_sent"] is False

    repeat = call(
        "--calendar-db", a, "--recovery-db", b,
        "--workflow-db", c, "--tenant-id", "alpha",
        "--as-of", (NOW + timedelta(minutes=10)).isoformat(),
        "--apply-local-evidence-replay",
    )
    assert repeat.returncode == 0, repeat.stderr
    assert json.loads(repeat.stdout)["acknowledged"] == 0
    assert json.loads(call(*read_args).stdout)["complete"] == 1


def test_cli_rejects_invalid_or_equal_storage_paths(tmp_path):
    a, b, c = fixture(tmp_path)
    assert call(
        "--calendar-db", a, "--recovery-db", a,
        "--workflow-db", c, "--tenant-id", "alpha",
        "--as-of", NOW.isoformat(),
        "--apply-local-evidence-replay",
    ).returncode != 0
    nonexistent = tmp_path / "missing.db"
    assert call(
        "--calendar-db", nonexistent, "--tenant-id", "alpha", "--read-only"
    ).returncode != 0
    assert not nonexistent.exists()
    assert call(
        "--calendar-db", a, "--tenant-id", "alpha",
        "--apply-local-evidence-replay",
    ).returncode != 0


def test_readonly_other_tenant_lookups_do_not_surface_contact(tmp_path):
    a, b, c = fixture(tmp_path)
    result = call(
        "--calendar-db", a, "--tenant-id", "beta", "--read-only",
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["pending"] == 0
    assert "appt-1" not in result.stdout
