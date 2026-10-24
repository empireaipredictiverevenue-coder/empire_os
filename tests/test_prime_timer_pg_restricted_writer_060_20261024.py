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


def test_060_independent_scram_login_grant_is_disposable_test_only():
    fixture=SHELL.read_text()
    assert "GRANT EXECUTE ON FUNCTION public.empire_prime_timer_receipt_record_held" in fixture
    assert "CREATE ROLE timer_fixture_gateway_login LOGIN PASSWORD" in fixture
    assert "NOINHERIT NOBYPASSRLS" in fixture
    assert "scram-sha-256" in fixture
    assert "pg_reload_conf()" in fixture
    assert "SCRAM_WRONG_PASSWORD_AND_HIGH_PRIVILEGES_DENIED=true" in fixture
    assert "SCRAM_OTHER_DATABASES_REJECTED=true" in fixture
    assert "<<FIXTURE_SQL" in fixture
    assert "REAL_SCRAM_LOGIN_NO_TABLE_PERMISSIONS=true" in fixture
    assert "SCRAM_LOGIN_DIRECT_TABLE_SELECT_DENIED=true" in fixture
    assert "SCRAM_LOGIN_TWO_WORKERS_ONE_CALLBACK=true" in fixture
    assert "060_flagship_timer_receipt_restricted_writer_held" in fixture
    assert "SET ROLE timer_fixture_gateway_exec" not in fixture


def test_original_migrations_unchanged_and_reader_permissions_fixture_only():
    fixture=SHELL.read_text()
    assert "CREATE POLICY timer_fixture_reader_request_held" in fixture
    assert "CREATE POLICY timer_fixture_reader_event_held" in fixture
    assert "CREATE POLICY timer_fixture_reader_receipt_held" in fixture
    assert "CREATE POLICY timer_fixture_reader_consent_held" in fixture
    assert "CREATE FUNCTION public.fixture_lock_current_test_consent" in fixture
    assert "session_user<>'timer_fixture_identity_reader_login'" in fixture
    assert "TO timer_fixture_identity_reader_login" in fixture
    for i in ("057_", "058_", "059_", "060_"):
        assert i in fixture
    assert "RESTRICTED_GATEWAY_FIXTURE_ROLE_NO_TABLE_PERMISSIONS" not in fixture
