"""Founder-approved REV052 identity: precise role, binding, HBA, no revenue writes."""
from __future__ import annotations
from pathlib import Path
import os
from types import SimpleNamespace

import pytest

from scripts import provision_revenue_event_evidence_login_20261018 as rev


def test_only_exact_flags_and_root_operator_can_activate(monkeypatch,capsys):
    assert rev.main(["--wrong-flag"])==3
    assert "HOLD_EXACT_APPROVAL_FLAG_REQUIRED" in capsys.readouterr().out
    monkeypatch.setattr(rev.os,"geteuid",lambda:1000)
    assert rev.main(["--apply-approved-one-tenant-login"])==3
    assert "HOLD_ROOT_LOCAL_SESSION_REQUIRED" in capsys.readouterr().out


def test_one_exact_existing_tenant_and_singular_role_only():
    assert rev.LOGIN=="empire_predictive_revenue_evidence_login"
    assert rev.ROLE=="empire_predictive_revenue_evidence_reader"
    assert rev.TENANT=="708efd4b-53b2-43d7-961d-1cecab67f17a"
    assert rev.SUBJECT=="founder:phil_livesley"
    assert rev.PREFIX.count("local empiredb")==1
    assert "scram-sha-256" in rev.PREFIX
    sql=rev.readiness_sql()
    for required in (
        "'login_absent'","'capability_unassigned'","'tenant_bind_absent'",
        "'one_active_founder_owner'","'known_existing_tenant'",
        "'capability_table_read_denied'","'hba_valid'","'reader_function'",
        "'data_directory_matches'","'hba_file_matches'",
    ):
        assert required in sql
    assert sql.startswith("BEGIN READ ONLY;")
    assert sql.rstrip().endswith("ROLLBACK;")


def test_atomic_db_change_only_one_login_one_grant_one_binding():
    sql=rev.provision_sql("SCRAM-SHA-256$4096:salt$stored:server")
    assert sql.startswith("BEGIN;") and sql.rstrip().endswith("COMMIT;")
    assert sql.count("CREATE ROLE "+rev.LOGIN)==1
    assert "LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE" in sql
    assert "NOREPLICATION NOBYPASSRLS PASSWORD" in sql
    assert "GRANT "+rev.ROLE+" TO "+rev.LOGIN+" WITH INHERIT FALSE, SET TRUE, ADMIN FALSE" in sql
    assert "INSERT INTO public.empire_tenant_role_bindings" in sql
    assert "'founder:approved-one-revenue-evidence-login-20261018'" in sql
    assert "GRANT CONNECT ON DATABASE empiredb TO "+rev.LOGIN in sql
    for disallowed in (
        "GRANT SELECT ON", "GRANT INSERT ON","GRANT UPDATE ON",
        "GRANT DELETE ON","INSERT INTO public.commercial_events",
        "UPDATE public.commercial_events","DELETE FROM public.commercial_events",
        "CREATE DATABASE","CREATE FUNCTION","DROP ROLE","DROP TABLE",
        "CREATE ROLE empire_predictive_revenue_evidence_reader",
    ):
        assert disallowed not in sql
    assert "SESSION_USER" not in sql.upper()  # identity binding, never altered
    with pytest.raises(ValueError):
        rev.provision_sql("plaintext-password")


def test_root_private_credential_permissions_no_stdout(tmp_path,monkeypatch,capsys):
    vault=tmp_path/"private"
    monkeypatch.setattr(rev,"VAULT",vault)
    monkeypatch.setattr(rev,"PASSFILE",vault/"reader.pgpass")
    monkeypatch.setattr(rev.os,"chown",lambda *a:None)
    pw="fictionaltestonly"*5
    rev.private_credential(pw)
    assert oct(vault.stat().st_mode & 0o777)=="0o700"
    assert oct((vault/"reader.pgpass").stat().st_mode & 0o777)=="0o600"
    assert pw in (vault/"reader.pgpass").read_text()
    assert pw not in capsys.readouterr().out
    with pytest.raises(FileExistsError):
        rev.private_credential(pw)


def test_release_rejects_unapproved_source_in_apply(monkeypatch,capsys,tmp_path):
    # A staged but uncommitted script must not be allowed to activate.
    monkeypatch.setattr(rev.os,"geteuid",lambda:0)
    monkeypatch.setattr(rev,"VAULT",tmp_path/"not-present")
    monkeypatch.setattr(rev,"catalog",lambda:{k:True for k in (
        "canonical","postgres18","tenant_resolver","reader_capability",
        "reader_function","login_absent","capability_unassigned",
        "tenant_bind_absent","one_active_founder_owner","known_existing_tenant",
        "financial_tables_exist","capability_table_read_denied",
        "hba_valid","hba_file_matches","data_directory_matches")})
    monkeypatch.setattr(rev,"strict_hba",lambda:(
        SimpleNamespace(st_uid=os.getuid(),st_gid=os.getgid(),st_mode=0o640),b"original"))
    monkeypatch.setattr(rev,"backup_ready",lambda:True)
    monkeypatch.setattr(rev,"archive_matches_active_repository",lambda:True)
    monkeypatch.setattr(rev,"reviewed_script",lambda:False)
    monkeypatch.setattr(rev,"LOCK",tmp_path/"test.lock")
    assert rev.main(["--apply-approved-one-tenant-login"])==2
    output=capsys.readouterr().out
    assert "HOLD_UNREVIEWED_RELEASE_SOURCE" in output
    assert not (tmp_path/"not-present").exists()


def test_root_readonly_preflight_does_not_make_changes(monkeypatch,capsys,tmp_path):
    monkeypatch.setattr(rev.os,"geteuid",lambda:0)
    keys=(
        "canonical","postgres18","tenant_resolver","reader_capability",
        "reader_function","login_absent","capability_unassigned",
        "tenant_bind_absent","one_active_founder_owner","known_existing_tenant",
        "financial_tables_exist","capability_table_read_denied",
        "hba_valid","hba_file_matches","data_directory_matches")
    monkeypatch.setattr(rev,"catalog",lambda:{k:True for k in keys})
    monkeypatch.setattr(rev,"VAULT",tmp_path/"private")
    monkeypatch.setattr(rev,"LOCK",tmp_path/"lock")
    monkeypatch.setattr(rev,"strict_hba",lambda:(
        SimpleNamespace(st_uid=os.getuid(),st_gid=os.getgid(),st_mode=0o640),b"original"))
    monkeypatch.setattr(rev,"backup_ready",lambda:True)
    monkeypatch.setattr(rev,"archive_matches_active_repository",lambda:True)
    monkeypatch.setattr(rev,"save_hba_backup",
                        lambda *a:pytest.fail("backup write during preflight"))
    monkeypatch.setattr(rev,"pg",lambda *a:pytest.fail("database write during preflight"))
    assert rev.main(["--preflight"])==0
    assert "READY_ONE_FOUNDER_TENANT_RESTRICTED_LOGIN" in capsys.readouterr().out
    assert not (tmp_path/"private").exists()


def test_missing_source_authority_does_not_create_login(monkeypatch,capsys,tmp_path):
    monkeypatch.setattr(rev.os,"geteuid",lambda:0)
    monkeypatch.setattr(rev,"LOCK",tmp_path/"lock")
    monkeypatch.setattr(rev,"catalog",lambda:{"canonical":True,"reader_function":False})
    assert rev.main(["--apply-approved-one-tenant-login"])==2
    assert "HOLD_DATABASE_SCOPE_OR_FOUNDER_TENANT_NOT_PROVEN" in capsys.readouterr().out


def test_only_local_active_pgbackrest_and_exact_archive_command_used():
    import inspect
    source=inspect.getsource(rev)
    assert "--config=/etc/pgbackrest/empiredb.conf" in source
    assert "--stanza=empiredb" in source
    assert "archive-push %p" in source
    assert "private_credential(password)" in source
    assert "secrets.token_urlsafe(48)" in source
    assert "scram_verifier(password)" in source
    assert "pg(provision_sql(verifier))" in source
    assert "SET TRANSACTION READ ONLY" in source
    assert "SET LOCAL ROLE "+'"'+"+ROLE" in source
    assert "read_predictive_revenue_event_v1(" in source
    assert "REV052_REVENUE_EVENT_FETCHED=NO" in source


def test_admin_psql_uses_quiet_local_stdin(monkeypatch):
    calls=[]
    def fake_run(argv,**kwargs):
        calls.append((argv,kwargs))
        return SimpleNamespace(returncode=0,stdout="1\n",stderr="")
    monkeypatch.setattr(rev.subprocess,"run",fake_run)
    assert rev.pg("SELECT 1")=="1"
    argv,kwargs=calls[0]
    assert argv[:5]==["/usr/sbin/runuser","-u","postgres","--","/usr/bin/psql"]
    assert "-q" in argv
    assert argv[-2:]==["-d","empiredb"]
    assert kwargs["input"]=="SELECT 1"
    assert kwargs["capture_output"] is True
    assert "SELECT 1" not in " ".join(argv)


def test_pinned_runuser_exec_starts_under_restricted_path():
    # Exercise the actual executable, not just the monkeypatched call.
    # --version is unprivileged, read-only, and cannot touch EmpireDB.
    import subprocess
    assert os.path.isfile("/usr/sbin/runuser")
    assert os.path.isfile("/usr/bin/psql")
    result=subprocess.run(
        ["/usr/sbin/runuser","--version"],
        env={"PATH":"/usr/bin:/bin","HOME":"/var/lib/postgresql"},
        capture_output=True,text=True,timeout=4,
    )
    assert result.returncode==0
    assert "runuser" in result.stdout.lower()


def test_readonly_preflight_reports_stage_not_exception_or_credentials(monkeypatch,tmp_path,capsys):
    monkeypatch.setattr(rev.os,"geteuid",lambda:0)
    monkeypatch.setattr(rev,"LOCK",tmp_path/"rev052.lock")
    monkeypatch.setattr(rev,"catalog",lambda:(_ for _ in ()).throw(
        FileNotFoundError("private secret path that must not be printed")))
    assert rev.main(["--preflight"])==4
    output=capsys.readouterr().out
    assert "REV052_FAILURE_STAGE=CATALOG_READONLY" in output
    assert "REV052_STATUS=HOLD_OR_UNVERIFIED_NO_BLIND_RETRY" in output
    assert "private secret path" not in output


def test_role_names_strictly_decode_postgres_bytes_without_broadening_access():
    assert rev.role_name_text(b"empire_predictive_revenue_evidence_login")==rev.LOGIN
    assert rev.role_name_text(rev.LOGIN)==rev.LOGIN
    assert rev.role_name_text(b"\xff") is None
    assert rev.role_name_text(None) is None
    assert rev.role_name_text(12345) is None
