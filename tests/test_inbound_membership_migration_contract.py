"""Prepared SQL ownership contract checks (not a Postgres migration test)."""
from pathlib import Path

BASE = Path("supabase/migrations")


def _prepared_sql():
    files = sorted(BASE.glob("*_inbound_recovery_tenant_access_prepared_20261020.sql"))
    assert len(files) == 1
    existing = sorted(BASE.glob("*_inbound_revenue_recovery_prepared.sql"))
    assert len(existing) == 1
    assert files[0].name > existing[0].name, "tenant policies must follow core schema"
    return files[0].read_text()


def test_prepared_tenant_membership_security_intent():
    sql = _prepared_sql().lower()
    assert "references auth.users(id)" in sql
    assert "force row level security" in sql
    assert "for select to authenticated" in sql
    assert "(select auth.uid())" in sql
    assert "membership_status = 'active'" in sql
    assert "lifecycle_state = 'approved'" in sql
    assert "raw_user_meta_data" not in sql
    assert "security definer" not in sql


def test_prepared_events_receipts_and_audit_remain_private():
    sql = _prepared_sql().lower()
    for table in (
        "inbound_recovery_events", "inbound_recovery_signed_callbacks",
        "inbound_recovery_management_access_audit",
    ):
        assert ("revoke all on public." + table) in sql
    assert "grant select on public.inbound_recovery_events to authenticated" not in sql
    assert "grant select on public.inbound_recovery_signed_callbacks to authenticated" not in sql
    assert "grant insert on public.inbound_recovery_memberships to authenticated" not in sql


def test_prepared_migration_does_not_execute_external_operations():
    sql = _prepared_sql().lower()
    assert "create trigger" not in sql
    assert "create or replace function" not in sql
    assert "http_" not in sql
    assert "pg_net" not in sql
    assert "commit;" in sql
