"""V15 post-HOLD state inspection must remain read-only and redacted."""
import json

from scripts import inspect_data_exchange_v15_release as review


def test_refuses_non_root_without_looking_into_db(monkeypatch):
    monkeypatch.setattr(review.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(review.deploy,"postgresql",
        lambda *a,**kw: (_ for _ in ()).throw(AssertionError("not allowed")))
    result=review.inspect()
    assert result["reason_code"]=="ROOT_READONLY_INSPECTION_REQUIRED"
    assert result["database_writes"] is False
    assert result["service_started"] is False


def test_safe_empty_predeploy_state(monkeypatch,tmp_path):
    monkeypatch.setattr(review.os,"geteuid",lambda:0)
    monkeypatch.setattr(review.deploy,"checked_schema",lambda:"BEGIN;\nCOMMIT;")
    monkeypatch.setattr(review.deploy,"application_same_database",lambda:True)
    monkeypatch.setattr(review.deploy,"postgresql",lambda query:
        "empiredb|/var/lib/postgresql/18/main|PRIMARY"
        if "data_directory" in query else "0|0")
    monkeypatch.setattr(review.deploy,"ENV_FILE",tmp_path/"missing.env")
    monkeypatch.setattr(review.deploy,"UNIT_FILE",tmp_path/"missing.service")
    monkeypatch.setattr(review.deploy,"BACKUP_ROOT",tmp_path/"backups")
    # Passive systemctl query can be simulated with a tool error. This
    # must not block the database-state classification or trigger a write.
    monkeypatch.setattr(review.subprocess,"run",
        lambda *args,**kw: (_ for _ in ()).throw(FileNotFoundError("simulated")))
    result=review.inspect()
    assert result["production_state"]=="NO_V15_SCHEMA_OR_SERVICE_OBSERVED"
    assert result["safe_to_reconcile"]=="NEEDS_PREDEPLOY_CAUSE_DIAGNOSIS"
    assert result["release_sql_exact_match"] is True
    assert result["canonical_db_identity_verified"] is True
    assert result["app_dsn_same_pg_instance"] is True
    assert result["database_writes"] is False
    assert result["service_started"] is False
    assert result["migration_attempted"] is False


def test_partial_schema_is_never_cleared_for_retry(monkeypatch,tmp_path):
    monkeypatch.setattr(review.os,"geteuid",lambda:0)
    monkeypatch.setattr(review.deploy,"checked_schema",lambda:"SQL")
    monkeypatch.setattr(review.deploy,"application_same_database",lambda:False)
    monkeypatch.setattr(review.deploy,"postgresql",lambda query:
        "empiredb|/var/lib/postgresql/18/main|PRIMARY"
        if "data_directory" in query else
        "1|2" if "pg_roles" in query else "0")
    monkeypatch.setattr(review.deploy,"ENV_FILE",tmp_path/"env")
    monkeypatch.setattr(review.deploy,"UNIT_FILE",tmp_path/"unit")
    monkeypatch.setattr(review.deploy,"BACKUP_ROOT",tmp_path/"backups")
    monkeypatch.setattr(review.subprocess,"run",
        lambda *args,**kw: (_ for _ in ()).throw(FileNotFoundError()))
    report=review.inspect()
    assert report["production_state"]=="PARTIAL_OR_COMPLETE_INSTALL_NEEDS_READBACK"
    assert report["safe_to_reconcile"]=="DO_NOT_RETRY_APPLY"
    assert report["custody_table_exists"] is True
    assert report["dedicated_role_count"]==2
    assert report["canonical_observation_row_count"]==0


def test_main_without_readonly_does_not_inspect(capsys,monkeypatch):
    monkeypatch.setattr(review,"inspect",lambda:(_ for _ in ()).throw(AssertionError("no inspection")))
    assert review.main([])==2
    out=json.loads(capsys.readouterr().out)
    assert out["mode"]=="READ_ONLY"
    assert out["reason_code"]=="EXPLICIT_READ_ONLY_FLAG_REQUIRED"


def test_no_application_secrets_or_mutating_sql():
    from pathlib import Path
    code=Path(review.__file__).read_text()
    for forbidden in ("CREATE ROLE", "INSERT INTO", "DELETE FROM",
                      "UPDATE public", "SET ROLE", "systemctl start",
                      "pg_dump", "pg_restore", "subprocess.run(['sudo'"):
        assert forbidden not in code


def test_postgresql_uses_verified_absolute_runuser_even_with_restricted_path(monkeypatch):
    """Exact regression: /usr/sbin/runuser absent from child PATH /usr/bin:/bin."""
    from scripts import deploy_data_exchange_custody_v15 as deploy
    from types import SimpleNamespace
    calls=[]
    def fake_run(command, **kwargs):
        calls.append((command,kwargs))
        return SimpleNamespace(returncode=0,stdout="empiredb",stderr="")
    monkeypatch.setattr(deploy.subprocess,"run",fake_run)
    assert deploy.postgresql("SELECT current_database()")=="empiredb"
    command,kwargs=calls[0]
    assert command[:5]==["/usr/sbin/runuser","-u","postgres","--","/usr/bin/psql"]
    assert kwargs["env"]["PATH"]=="/usr/bin:/bin"
    assert kwargs["input"] is None
    assert kwargs["capture_output"] is True


def test_backup_uses_absolute_admin_binary_paths():
    from scripts import deploy_data_exchange_custody_v15 as deploy
    from pathlib import Path
    source=Path(deploy.__file__).read_text(encoding="utf-8")
    assert 'RUNUSER = "/usr/sbin/runuser"' in source
    assert '[RUNUSER, "-u", "postgres", "--", "/usr/bin/pg_dump"' in source
    assert '[RUNUSER, "-u", "postgres", "--", "/usr/bin/pg_dumpall"' in source
    assert '["runuser", "-u", "postgres"' not in source


def test_diagnostic_handles_missing_executable_as_type_not_fake_schema(monkeypatch,tmp_path):
    monkeypatch.setattr(review.os,"geteuid",lambda:0)
    monkeypatch.setattr(review.deploy,"checked_schema",lambda:"SQL")
    monkeypatch.setattr(review.deploy,"ENV_FILE",tmp_path/"env")
    monkeypatch.setattr(review.deploy,"UNIT_FILE",tmp_path/"unit")
    monkeypatch.setattr(review.deploy,"BACKUP_ROOT",tmp_path/"backup")
    monkeypatch.setattr(review.deploy,"postgresql",
        lambda query: (_ for _ in ()).throw(FileNotFoundError()))
    monkeypatch.setattr(review.deploy,"application_same_database",lambda:False)
    monkeypatch.setattr(review.subprocess,"run",
        lambda *args,**kw: (_ for _ in ()).throw(FileNotFoundError()))
    result=review.inspect()
    assert result["canonical_db_probe_error_type"]=="FileNotFoundError"
    assert result["schema_role_probe_error_type"]=="FileNotFoundError"
    assert result["production_state"]=="UNDETERMINED"
    assert "safe_to_reconcile" not in result


def test_identity_check_produces_stable_primary_or_replica_token():
    from scripts import deploy_data_exchange_custody_v15 as deploy
    assert "CASE WHEN pg_is_in_recovery()" in deploy.DB_IDENTITY_SQL
    assert "'REPLICA' ELSE 'PRIMARY'" in deploy.DB_IDENTITY_SQL
    assert deploy.EXPECTED_DB_IDENTITY.endswith("|PRIMARY")
    assert "|f" not in deploy.EXPECTED_DB_IDENTITY


def test_replica_database_fails_closed_even_with_matching_name(monkeypatch, tmp_path):
    monkeypatch.setattr(review.os, "geteuid", lambda: 0)
    monkeypatch.setattr(review.deploy,"checked_schema",lambda:"SQL")
    monkeypatch.setattr(review.deploy,"application_same_database",lambda:True)
    monkeypatch.setattr(review.deploy,"postgresql",lambda query:
        "empiredb|/var/lib/postgresql/18/main|REPLICA" if
        "pg_is_in_recovery()" in query else "0|0")
    monkeypatch.setattr(review.deploy,"ENV_FILE",tmp_path/"env")
    monkeypatch.setattr(review.deploy,"UNIT_FILE",tmp_path/"unit")
    monkeypatch.setattr(review.deploy,"BACKUP_ROOT",tmp_path/"backups")
    monkeypatch.setattr(review.subprocess,"run",
        lambda *args,**kw: (_ for _ in ()).throw(FileNotFoundError()))
    result=review.inspect()
    assert result["canonical_db_identity_verified"] is False
    assert result["app_dsn_same_pg_instance"] is True
    assert result["custody_table_exists"] is False
    assert result["dedicated_role_count"] == 0
    assert result["database_writes"] is False
