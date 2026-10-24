"""Held original EmpireDB 060 function-security boundary, zero live providers."""
from __future__ import annotations
from pathlib import Path

SQL=Path(__file__).resolve().parents[1]/"migrations/empiredb/060_flagship_timer_receipt_restricted_writer_held.sql"
SHELL=Path(__file__).resolve().parents[1]/"scripts/rehearse_prime_signed_gateway_pg_fixture_20261024.sh"


def test_original_060_no_public_or_service_execution_rights_installed():
    contents=SQL.read_text()
    lines=[x.strip().lower() for x in contents.splitlines()
           if x.strip() and not x.lstrip().startswith("--")]
    all_sql="\n".join(lines)
    assert "timer060_wrong_database" in all_sql
    assert "timer060_predecessors_057_058_059_required" in all_sql
    assert "timer060_unreviewed_migrator_members" in all_sql
    assert "set local role empiredb_migrator;" in lines
    assert "security definer" in all_sql
    assert "set search_path=''" in all_sql
    assert "set row_security=on" in all_sql
    assert "for update" in all_sql
    assert "timer060_missing_original_atomic_claim" in all_sql
    assert "timer060_original_tenant_or_source_mismatch" in all_sql
    assert "timer060_terminal_custody_stream" in all_sql
    assert "revoke all on function public.empire_prime_timer_receipt_record_held(" in all_sql
    # The INSERT exists ONLY inside the restricted SECURITY DEFINER
    # function, not as a migration-time data write or a runtime GRANT.
    assert "insert into public.empire_prime_timer_provider_receipts(" in all_sql
    assert not any(line.startswith(("grant ","create role","create user","create extension"))
                   for line in lines)
    assert "NO runtime" in contents


def test_060_explicit_grant_is_disposable_test_only():
    fixture=SHELL.read_text()
    assert "GRANT EXECUTE ON FUNCTION public.empire_prime_timer_receipt_record_held" in fixture
    assert "CREATE ROLE timer_fixture_gateway_exec NOLOGIN" in fixture
    assert "RESTRICTED_GATEWAY_FIXTURE_ROLE_NO_TABLE_PERMISSIONS=true" in fixture
    assert "RESTRICTED_060_DIRECT_TABLE_SELECT_DENIED=true" in fixture
    assert "RESTRICTED_060_TWO_WORKERS_ONE_CALLBACK=true" in fixture
    assert "060_flagship_timer_receipt_restricted_writer_held" in fixture
