from pathlib import Path

MIGRATION=Path("supabase/migrations/20260920101011_typed_decision_shadow_evidence.sql")


def sql():
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_migration_is_private_and_not_public_data_api_surface():
    text=sql()
    assert "create schema if not exists empire_eval" in text
    assert "create table empire_eval.shadow_observations" in text
    assert "create table public." not in text
    assert "revoke all on schema empire_eval from public, anon, authenticated" in text


def test_all_eval_tables_enable_rls_and_anon_authenticated_are_revoked():
    text=sql()
    tables=[
        "shadow_observations",
        "reviewed_labels",
        "provider_outputs",
        "dataset_manifests",
        "eval_reports",
        "shadow_decisions",
    ]
    for table in tables:
        assert f"alter table empire_eval.{table} enable row level security" in text
    assert "revoke all on all tables in schema empire_eval" in text
    assert "from public, anon, authenticated" in text


def test_service_role_is_append_only():
    text=sql()
    assert "grant select, insert on" in text
    assert "to service_role" in text
    assert "revoke update, delete, truncate on all tables in schema empire_eval" in text


def test_migration_contains_no_execution_rpc_or_security_definer():
    text=sql()
    assert "security definer" not in text
    assert "create function" not in text
    assert "create or replace function" not in text
