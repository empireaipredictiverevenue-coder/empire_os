from pathlib import Path

import empire_os.data_cloud_tenant_security as tenant


def test_tenant_migration_uses_trusted_role_binding():
    root = Path(__file__).resolve().parents[1]
    sql = (
        root / "migrations/empiredb/018_tenant_context_foundation.sql"
    ).read_text(encoding="utf-8")

    assert "empiredb_tenant_reader" in sql
    assert "public.empire_tenant_role_bindings" in sql
    assert "session_user" in sql
    assert "b.role_name = session_user" in sql
    assert "public.empire_current_tenant_id()" in sql
    assert "current_setting('empire.tenant_id'" not in sql
    assert "org_id IS NOT NULL" in sql
    assert "GRANT SELECT ON" in sql
    assert "GRANT INSERT" not in sql
    assert "GRANT UPDATE" not in sql
    assert "GRANT DELETE" not in sql
    assert "UPDATE public.buyers" not in sql
    assert "DELETE FROM public.buyers" not in sql


def test_tenant_reader_cannot_mutate_binding_table():
    root = Path(__file__).resolve().parents[1]
    sql = (
        root / "migrations/empiredb/018_tenant_context_foundation.sql"
    ).read_text(encoding="utf-8")

    assert "REVOKE ALL ON TABLE public.empire_tenant_role_bindings" in sql
    assert "FROM empiredb_app, empiredb_readonly, empiredb_tenant_reader" in sql


def test_tenant_reader_bootstrap_role_exists_in_script():
    root = Path(__file__).resolve().parents[1]
    script = (
        root / "scripts/bootstrap_empiredb_runtime_roles.sh"
    ).read_text(encoding="utf-8")

    assert "'empiredb_tenant_reader'" in script
    assert "GRANT empiredb_tenant_reader TO empiredb_migrator" in script


def test_tenant_canary_is_rollback_only_and_checks_binding_mutation():
    source = Path(tenant.__file__).read_text(encoding="utf-8")

    assert "rollback_only" in source
    assert "tenant_binding_write_check" in source
    assert "binding_mutation_denied" in source
    assert "missing_binding_fails_closed" in source
    assert "production_cutover_authority" in source
    assert "SET ROLE empiredb_tenant_reader" in source



def test_tenant_migration_does_not_require_database_schema_create():
    root = Path(__file__).resolve().parents[1]
    sql = (
        root / "migrations/empiredb/018_tenant_context_foundation.sql"
    ).read_text(encoding="utf-8")

    assert "CREATE SCHEMA" not in sql
    assert "public.empire_tenant_role_bindings" in sql



def test_tenant_canary_binds_authenticated_session_user():
    source = Path(tenant.__file__).read_text(encoding="utf-8")

    assert "SELECT session_user" in source
    assert "authenticated_db_session_user_binding" in source
