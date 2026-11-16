"""Single-operation original EmpireDB release; no live privilege in tests."""
import json
from pathlib import Path
import pytest

from scripts.release_predictive_empiredb_native_once_20261116 import (
    MIGRATIONS, REQUIRED, ReleaseHold, ROOT, READBACK_SQL, build_atomic_sql,
    check_catalogue, load_pinned_migrations, main,
)


def test_all_original_migrations_pinned_and_atomic():
    parts = load_pinned_migrations(root=Path(__file__).resolve().parents[1])
    assert len(parts) == 3
    sql = build_atomic_sql(parts)
    assert sql.startswith("BEGIN;\n")
    assert sql.rstrip().endswith("COMMIT;")
    assert sql.count("CREATE ROLE empire_predictive_") == 2
    assert sql.count("RESET ROLE;") >= 3
    assert "NATIVE_RELEASE_REGISTRY_RLS_OR_OWNER_HOLD" in sql
    assert "NATIVE_RELEASE_PRIVATE_READER_OR_REGISTRAR_HOLD" in sql
    assert "NATIVE_RELEASE_UNEXPECTED_REGISTRY_ROWS" in sql
    assert "NATIVE_PREDICTIVE_RELEASE_COMMITTED_SCHEMA_ONLY" in sql


def test_pinned_source_drift_fails_closed(tmp_path):
    filename, _ = MIGRATIONS[0]
    target = tmp_path / filename
    target.parent.mkdir(parents=True)
    target.write_text("BEGIN;\nCREATE TABLE public.unreviewed(id int);\nCOMMIT;\n")
    with pytest.raises(ReleaseHold, match="SOURCE_DIGEST_DRIFT"):
        load_pinned_migrations(root=tmp_path)


def test_catalogue_proof_is_schema_locked_and_untrusted_gates_hold():
    good = {key: True for key in REQUIRED}
    assert check_catalogue(json.dumps(good)) == good
    false = {**good, "archiver_healthy": False, "registry_absent": False}
    with pytest.raises(ReleaseHold,
                       match="archiver_healthy.*registry_absent"):
        check_catalogue(json.dumps(false))
    with pytest.raises(ReleaseHold, match="SCHEMA_MISMATCH"):
        check_catalogue("{}")
    with pytest.raises(ReleaseHold, match="PROOF_INVALID"):
        check_catalogue(json.dumps({**good, "canonical": "true"}))
    with pytest.raises(ReleaseHold, match="UNAVAILABLE"):
        check_catalogue("not JSON")


def test_nonroot_execution_cannot_query_or_release(monkeypatch, capsys):
    import scripts.release_predictive_empiredb_native_once_20261116 as module

    monkeypatch.setattr(module.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(module, "pg", lambda *_: (_ for _ in ()).throw(
        AssertionError("no DB query or release from unprivileged session")
    ))
    for mode in ("--preflight", "--apply-founder-approved"):
        assert main([mode]) == 2
    result = capsys.readouterr().out
    assert result.count("EXPLICIT_ROOT_OPERATOR") == 2


def test_production_does_not_gain_a_backup_or_service_restart_path():
    source=(ROOT / "scripts/release_predictive_empiredb_native_once_20261116.py")
    # In isolated source checkout the script is not yet installed.
    if not source.exists():
        source=Path(__file__).resolve().parents[1] / (
            "scripts/release_predictive_empiredb_native_once_20261116.py")
    text=source.read_text()
    assert "pg(CATALOG_SQL)" in text
    assert "pg(sql)" in text
    assert "backup_" not in text.replace("existing_backup_copies_created","").replace(
        "new_backup_created","")
    assert "systemctl restart" not in text
    assert "pg_ctlcluster" not in text
    assert "INSERT INTO public.commercial_events" not in text
    assert "ALTER ROLE" not in text


def test_independent_readback_is_strictly_read_only_and_rbac_scoped():
    assert READBACK_SQL.startswith("BEGIN READ ONLY;")
    assert READBACK_SQL.rstrip().endswith("ROLLBACK;")
    assert "has_table_privilege" in READBACK_SQL
    assert "has_function_privilege" in READBACK_SQL
    assert "relforcerowsecurity" in READBACK_SQL
    assert "count(*)=0 FROM public.predictive_forecasts" in READBACK_SQL
