"""Booking workflow CLI and prepared migration boundaries."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

from empire_os.inbound_booking_store import OfflineBookingWorkflowStore
from empire_os.inbound_booking_workflow import InboundWorkflowEvent
from empire_os.inbound_contact_identity import pseudonymise_inbound_contact

NOW = datetime(2026, 10, 20, 13, tzinfo=timezone.utc)
CONTACT_KEY = pseudonymise_inbound_contact(
    "+442071234567", tenant_id="customer-a",
    signing_key="some-test-private-contact-key-minimum-32",
)


def event(tenant="customer-a", call="a-call"):
    return InboundWorkflowEvent(
        tenant_id=tenant, call_id=call, event_id="request-1",
        contact_key=CONTACT_KEY, kind="callback_requested",
        occurred_at=NOW.isoformat(), origin="verified_inbound",
        evidence_ref="caller-approval-test", verified=True, synthetic=False,
    )


def test_cli_existing_workflow_store_is_read_only_and_tenant_scoped(tmp_path):
    file = tmp_path / "workflows.db"
    with OfflineBookingWorkflowStore(file) as store:
        store.append_offline(event())
        store.append_offline(event("customer-b", "b-call"))
    baseline = file.stat().st_size
    args = [
        sys.executable, "-B", "-m",
        "scripts.review_inbound_booking_workflow_20261020",
        "--workflow-db", str(file), "--tenant-id", "customer-a",
        "--as-of", (NOW + timedelta(minutes=20)).isoformat(),
        "--read-only",
    ]
    process = subprocess.run(args, capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert report["call_workflows_total"] == 1
    assert report["workflows"][0]["call_id"] == "a-call"
    assert "b-call" not in process.stdout
    assert CONTACT_KEY not in process.stdout
    assert report["outbound_sent"] is False
    assert file.stat().st_size == baseline


def test_cli_nonexistent_file_does_not_create_database(tmp_path):
    path = tmp_path / "no-db.db"
    args = [
        sys.executable, "-B", "-m",
        "scripts.review_inbound_booking_workflow_20261020",
        "--workflow-db", str(path), "--tenant-id", "customer-a",
        "--as-of", (NOW + timedelta(minutes=2)).isoformat(),
        "--read-only",
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode != 0
    assert not path.exists()


def test_prepared_migration_restricts_direct_client_access_and_keeps_suppression():
    migrations = list(Path("supabase/migrations").glob(
        "*_inbound_booking_workflow_prepared_20261020.sql"
    ))
    assert len(migrations) == 1
    sql = migrations[0].read_text().lower()
    assert "inbound_recovery_contact_suppression" in sql
    assert "inbound_booking_workflow_events" in sql
    assert "force row level security" in sql
    assert "from public, anon, authenticated" in sql
    assert "grant select" not in sql
    assert "grant insert" not in sql
    assert "create trigger" not in sql
    assert "create or replace function" not in sql
    assert "appointment_ends_at > appointment_starts_at" in sql
    assert "booking_cancelled" in sql
    assert "commit;" in sql
    prefix = migrations[0].name.split("_")[0]
    assert prefix > "20261020124501"
