"""Read-only calendar report and prepared SQL protection contract."""
import json
from pathlib import Path
import subprocess
import sys

from empire_os.inbound_calendar_registry import OfflineCalendarRegistry
from empire_os.inbound_google_calendar_adapter import (
    ApprovedCalendarBinding, TrackedCalendarAppointment,
)
from empire_os.inbound_contact_identity import pseudonymise_inbound_contact


def test_calendar_cli_reads_only_own_customer_and_never_creates_db(tmp_path):
    path = tmp_path / "provider-history.db"
    with OfflineCalendarRegistry(path) as store:
        for tenant in ("alpha", "beta"):
            owned_calendar = f"{tenant}@example.org"
            store.register_binding_offline(ApprovedCalendarBinding(
                tenant_id=tenant, calendar_id=owned_calendar,
                provider_account_ref=f"auth-account-{tenant}",
                owner_approved=True, account_access_verified=True,
            ), approval_ref=f"customer-{tenant}-approval")
            store.register_appointment_offline(TrackedCalendarAppointment(
                tenant_id=tenant, calendar_id=owned_calendar,
                event_id="appointment-1", call_id=f"inbound-{tenant}",
                contact_key=pseudonymise_inbound_contact(
                    "+442077771234", tenant_id=tenant,
                    signing_key="offline-cli-calendar-test-secret-32",
                ), tracked_ref=f"client-approved-{tenant}",
            ))
    size = path.stat().st_size
    args = [
        sys.executable, "-B", "-m", "scripts.review_inbound_calendar_20261020",
        "--calendar-db", str(path), "--tenant-id", "alpha", "--read-only",
    ]
    p = subprocess.run(args, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout)
    assert data["tenant_id"] == "alpha"
    assert data["tracked_appointments"] == 1
    assert data["not_verified"] == 1
    assert data["customer_contact_authorized"] is False
    assert "beta@" not in p.stdout
    assert path.stat().st_size == size
    missing = tmp_path / "nonexistent.db"
    args[args.index(str(path))] = str(missing)
    p = subprocess.run(args, capture_output=True, text=True)
    assert p.returncode != 0 and not missing.exists()


def test_prepared_calendar_schema_is_default_deny_and_has_tenant_fks():
    sql_paths = sorted(Path("supabase/migrations").glob(
        "*_inbound_calendar_registry_prepared_20261020.sql"
    ))
    assert len(sql_paths) == 1
    p = sql_paths[0]
    assert p.name > "20261020124502_inbound_booking_workflow_prepared_20261020.sql"
    sql = p.read_text().lower()
    for table in (
        "inbound_recovery_calendar_bindings",
        "inbound_recovery_calendar_links",
        "inbound_recovery_calendar_status_evidence",
    ):
        assert "alter table public." + table + " force row level security" in sql
        assert "revoke all on public." + table + " from public, anon, authenticated" in sql
    assert "references public.inbound_recovery_tenants" in sql
    assert "foreign key(calendar_id, tenant_id)" in sql
    assert "adapter_evidence_verified boolean not null default false" in sql
    assert "synthetic boolean not null default true" in sql
    assert "refresh_token" not in sql
    assert "grant select" not in sql
    assert "security definer" not in sql
    assert "create trigger" not in sql
