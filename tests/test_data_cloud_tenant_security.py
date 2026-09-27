from pathlib import Path

import empire_os.data_cloud_tenant_security as tenant


def test_tenant_migration_is_fail_closed_and_read_only():
    root = Path(__file__).resolve().parents[1]
    sql = (
        root / "migrations/empiredb/018_tenant_context_foundation.sql"
    ).read_text(encoding="utf-8")

    assert "empiredb_tenant_reader" in sql
    assert "empire_current_tenant_id" in sql
    assert "current_setting('empire.tenant_id', true)" in sql
    assert "org_id IS NOT NULL" in sql
    assert "GRANT SELECT ON" in sql
    assert "GRANT INSERT" not in sql
    assert "GRANT UPDATE" not in sql
    assert "GRANT DELETE" not in sql
    assert "UPDATE public.buyers" not in sql
    assert "DELETE FROM public.buyers" not in sql


def test_tenant_reader_bootstrap_role_exists_in_script():
    root = Path(__file__).resolve().parents[1]
    script = (
        root / "scripts/bootstrap_empiredb_runtime_roles.sh"
    ).read_text(encoding="utf-8")

    assert "'empiredb_tenant_reader'" in script
    assert (
        "GRANT empiredb_tenant_reader TO empiredb_migrator"
        in script
    )


def test_tenant_canary_is_rollback_only_and_uses_savepoint():
    source = Path(tenant.__file__).read_text(encoding="utf-8")

    assert "rollback_only" in source
    assert "SAVEPOINT tenant_write_check" in source
    assert "ROLLBACK TO SAVEPOINT tenant_write_check" in source
    assert "production_cutover_authority" in source
    assert "SET ROLE empiredb_tenant_reader" in source
