"""Isolated root-vault and SCRAM provisioner tests; never touches live DB."""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import stat
from types import SimpleNamespace

import pytest

SOURCE=pathlib.Path(__file__).resolve().parents[1]/"scripts/provision_consumer_private_identity_20261021.py"
spec=importlib.util.spec_from_file_location("private_consumer_identity_source",SOURCE)
p=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(p)


def test_role_sql_never_contains_password_and_limits_privileges():
    password="f"*64
    verifier=p.scram_verifier(password)
    assert password not in verifier
    assert verifier.startswith("SCRAM-SHA-256$4096:")
    script=p.role_statement(verifier)
    assert password not in script
    assert "CREATE ROLE empire_consumer_optin_login LOGIN NOINHERIT" in script
    assert "NOSUPERUSER NOBYPASSRLS" in script
    assert "WITH INHERIT FALSE, SET TRUE, ADMIN FALSE" in script
    assert "ALTER DEFAULT PRIVILEGES" not in script
    assert "GRANT empire_consumer_optin_writer" in script
    assert "GRANT empiredb_app" not in script
    assert "INSERT INTO" not in script
    assert "COMMIT;" in script


def test_bad_scram_verifier_rejected():
    for item in ("abc","SCRAM-SHA-256$4096:salt$garbage';DROP ROLE hi;--"):
        with pytest.raises(RuntimeError):
            p.role_statement(item)


def test_preflight_denies_unprivileged_shell(monkeypatch):
    monkeypatch.setattr(p.os,"geteuid",lambda:1000)
    monkeypatch.setattr(p,"check_state",lambda:pytest.fail("checked DB"))
    with pytest.raises(RuntimeError,match="ROOT_OPERATOR_REQUIRED"):
        p.report_read_only()


def test_apply_must_be_root_and_match_new_exact_code_digest(monkeypatch):
    monkeypatch.setattr(p.os,"geteuid",lambda:1000)
    with pytest.raises(RuntimeError,match="ROOT_OPERATOR_REQUIRED"):
        p.provision(p.release_sha256())
    monkeypatch.setattr(p.os,"geteuid",lambda:0)
    monkeypatch.setattr(p.pwd,"getpwuid",
                        lambda uid:SimpleNamespace(pw_name="root"))
    monkeypatch.setattr(p,"check_state",lambda:pytest.fail("preflight ran"))
    with pytest.raises(RuntimeError,match="EXACT_PRIVATE_IDENTITY_RELEASE_APPROVAL_REQUIRED"):
        p.provision("not-approved")


def _local_environment(tmp_path,monkeypatch,*,ready=True,postcommit=True):
    secret_root=tmp_path/"secret-vault"
    monkeypatch.setattr(p,"ROOT",secret_root)
    monkeypatch.setattr(p,"PASSFILE",secret_root/"subscriber.pgpass")
    monkeypatch.setattr(p,"KEYFILE",secret_root/"subscriber-keys.json")
    monkeypatch.setattr(p,"LOCKFILE",tmp_path/"locker")
    monkeypatch.setattr(p.os,"geteuid",lambda:0)
    monkeypatch.setattr(p.pwd,"getpwuid",
                        lambda uid:SimpleNamespace(pw_name="root"))
    monkeypatch.setattr(p,"check_state",
                        lambda:{"postgres_schema_valid":ready})
    seen=[]
    def fake_sql(script):
        seen.append(script)
        if script.lstrip().startswith("SELECT jsonb_build_object"):
            return json.dumps({"all_good":postcommit})
        return ""
    monkeypatch.setattr(p,"_admin",fake_sql)
    return seen,secret_root


def test_applies_secret_files_only_to_protected_vault(tmp_path,monkeypatch):
    seen,vault=_local_environment(tmp_path,monkeypatch)
    result=p.provision(p.release_sha256())
    assert result["status"]=="PRIVATE_IDENTITY_PROVISIONED_SERVICE_HELD"
    assert result["service_activated"] is False
    assert result["subscriber_capture_enabled"] is False
    assert result["credential_details_disclosed"] is False
    assert stat.S_IMODE(vault.stat().st_mode)==0o700
    assert stat.S_IMODE((vault/"subscriber.pgpass").stat().st_mode)==0o600
    assert stat.S_IMODE((vault/"subscriber-keys.json").stat().st_mode)==0o600
    password=(vault/"subscriber.pgpass").read_text().split(":")[-1].strip()
    assert len(password)==64
    keys=json.loads((vault/"subscriber-keys.json").read_text())
    assert len({keys[k] for k in ("email_hmac","token_hmac","email_encryption")})==3
    assert all(len(keys[k])==64 for k in ("email_hmac","token_hmac","email_encryption"))
    assert len(seen)==2
    assert "CREATE ROLE" in seen[0]
    assert password not in seen[0]
    assert password not in str(result)
    assert not any(secret in seen[0] for secret in
                   (keys["email_hmac"],keys["token_hmac"],keys["email_encryption"]))


def test_provision_refuses_bad_schema_without_creating_vault(tmp_path,monkeypatch):
    seen,vault=_local_environment(tmp_path,monkeypatch,ready=False)
    with pytest.raises(RuntimeError,match="CONSUMER_IDENTITY_PREFLIGHT_HELD"):
        p.provision(p.release_sha256())
    assert not vault.exists()
    assert not seen


def test_transaction_failure_cleans_secrets(tmp_path,monkeypatch):
    seen,vault=_local_environment(tmp_path,monkeypatch)
    def reject(sql):
        raise RuntimeError("ORIGINAL_DB_ADMIN_QUERY_REJECTED")
    monkeypatch.setattr(p,"_admin",reject)
    with pytest.raises(RuntimeError,match="ORIGINAL_DB_ADMIN_QUERY_REJECTED"):
        p.provision(p.release_sha256())
    assert not (vault/"subscriber.pgpass").exists()
    assert not (vault/"subscriber-keys.json").exists()


def test_vault_second_file_failure_cleans_first(tmp_path,monkeypatch):
    seen,vault=_local_environment(tmp_path,monkeypatch)
    actual=p._write_secret
    def write(path,data):
        if path.name=="subscriber-keys.json":
            raise OSError("synthetic disk error")
        actual(path,data)
    monkeypatch.setattr(p,"_write_secret",write)
    with pytest.raises(OSError):
        p.provision(p.release_sha256())
    assert not (vault/"subscriber.pgpass").exists()
    assert not (vault/"subscriber-keys.json").exists()


def test_postcommit_failure_reports_hold_but_retains_identity_keys(tmp_path,monkeypatch):
    seen,vault=_local_environment(tmp_path,monkeypatch,postcommit=False)
    state=p.provision(p.release_sha256())
    assert state["status"]=="PRIVATE_IDENTITY_POSTCOMMIT_REVIEW_REQUIRED"
    assert state["service_activated"] is False
    assert (vault/"subscriber.pgpass").is_file()
    assert (vault/"subscriber-keys.json").is_file()
    assert len(seen)==2


def test_identity_release_fingerprint_is_stable_and_source_bound():
    assert len(p.release_sha256())==64
    assert p.release_sha256()!=p.EXPECTED_SCHEMA_SHA
    script=(SOURCE.parent/"probe_consumer_identity_scram_ephemeral_20261021.py").read_text()
    assert "production_db_modified" in script
    assert "test_plaintext_credential_in_sql" in script
