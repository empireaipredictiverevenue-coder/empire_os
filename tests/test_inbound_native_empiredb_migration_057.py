"""Native EmpireDB 057 DDL must remain held, tenant-scoped and default-deny."""
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "migrations/empiredb/057_inbound_recovery_native_schema_held.sql"
EXPECTED = (
    "inbound_recovery_tenants",
    "inbound_recovery_events",
    "inbound_recovery_signed_callbacks",
    "inbound_recovery_management_access_audit",
    "inbound_booking_workflow_events",
    "inbound_recovery_contact_suppression",
    "inbound_recovery_calendar_bindings",
    "inbound_recovery_calendar_links",
    "inbound_recovery_calendar_status_evidence",
    "inbound_recovery_calendar_projection_delivery",
)


def test_native_migration_has_existing_crm_authority_no_new_customer_login():
    sql = SQL.read_text().lower()
    assert "empire_crm_tenant_memberships" in sql
    assert "empire_crm_read_member(text,uuid)" in sql
    assert "empire_current_tenant_id()" in sql
    assert "set local role empiredb_migrator" in sql
    assert "inbound_recovery_057_fixture" in sql
    assert "force row level security" in sql
    executed_sql = "\n".join(
        line for line in sql.splitlines()
        if not line.lstrip().startswith("--")
    )
    for forbidden in (
        "auth.users", "auth.uid()", "from public, anon",
        "to authenticated", "to anon", "create role ",
        "create login", "create policy", "create trigger",
        "security definer", "create function", "create or replace function",
        "grant select", "grant insert", "grant update",
        "grant delete", "create extension", "pg_net",
        "http_", "create subscription", "create publication",
        "create event trigger",
    ):
        assert forbidden not in executed_sql
    assert sql.startswith("-- empiredb 057:")
    assert "do not apply to production" in sql
    assert sql.strip().endswith("commit;")


def test_every_native_table_forced_rls_and_nobody_gets_privileges():
    sql = SQL.read_text().lower()
    for table in EXPECTED:
        assert f"create table public.{table} (" in sql
        assert f"alter table public.{table} enable row level security;" in sql
        assert f"alter table public.{table} force row level security;" in sql
        assert f"  public.{table}" in sql
    assert "from public;" in sql
    assert "no policies = default-deny" in sql


def test_all_calendar_fk_components_start_with_tenant():
    sql = SQL.read_text().lower()
    assert "primary key(tenant_id,calendar_id)" in sql
    assert "primary key(tenant_id,calendar_id,appointment_id)" in sql
    assert "primary key(tenant_id,calendar_id,appointment_id,provider_revision_ref)" in sql
    assert "foreign key(tenant_id,calendar_id)" in sql
    assert "foreign key(tenant_id,calendar_id,appointment_id)" in sql
    assert "foreign key(tenant_id,calendar_id,appointment_id,provider_revision_ref)" in sql
    assert "tenant_id uuid not null" in sql
    assert "synthetic boolean not null default true" in sql
    assert "lifecycle_state text not null default 'draft'" in sql
    assert "booking_integration_verified boolean not null default false" in sql
    assert "callback_capture_allowed boolean not null default false" in sql


def test_no_google_tokens_or_payments_are_stored_in_native_schema():
    sql = SQL.read_text().lower()
    for name in ("access_token", "refresh_token", "google_client_secret",
                 "scw_secret_key", "payment_private_key", "wallet_private_key"):
        assert name not in sql
    assert "amount_minor > 0" in sql
    assert "synthetic is false" in sql
    assert "origin='payments'" in sql


@pytest.mark.skipif(
    not Path("/usr/lib/postgresql/18/bin/initdb").exists(),
    reason="PostgreSQL 18 temporary-server test utilities not installed",
)
def test_real_isolated_postgres_applies_native_schema_and_denies_app_roles():
    completed = subprocess.run([
        sys.executable, "-B", "-m",
        "scripts.verify_inbound_native_schema_ephemeral_20261020",
        "--ephemeral-only",
    ], cwd=ROOT, capture_output=True, text=True, timeout=90, check=False)
    assert completed.returncode == 0, completed.stdout[-600:]
    import json
    evidence = json.loads(completed.stdout)
    assert evidence["ephemeral_fixture_result"] == "PASS"
    assert evidence["native_tables_force_rls"] == len(EXPECTED)
    assert evidence["app_role_denials"] == 2
    assert evidence["production_database_changed"] is False
    assert evidence["cloud_credentials_used"] is False
