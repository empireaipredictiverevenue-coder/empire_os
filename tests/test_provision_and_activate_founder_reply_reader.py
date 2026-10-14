"""Dedicated Founder reply-view login is explicit, scoped and reversible."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts import provision_and_activate_founder_reply_reader as provision
from scripts import deploy_founder_canonical_reply_view as release


def test_dry_run_does_not_touch_database(monkeypatch, capsys):
    monkeypatch.setattr(provision, "provision_and_activate", lambda: (_ for _ in ()).throw(AssertionError("MUST_NOT_RUN")))
    assert provision.main([]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "REVIEW_ONLY"
    assert out["database_role_created"] is False
    assert out["mail_sent"] is False


def test_explicit_approval_required(monkeypatch, capsys):
    monkeypatch.setattr(provision, "provision_and_activate", lambda: (_ for _ in ()).throw(AssertionError("MUST_NOT_RUN")))
    assert provision.main(["--apply"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["reason"] == "EXPLICIT_DEDICATED_LOGIN_APPROVAL_REQUIRED"
    assert out["secrets_printed"] is False


def test_nonroot_prevents_credential_inspection(monkeypatch):
    monkeypatch.setattr(provision.os, "geteuid", lambda: 1000)
    with pytest.raises(provision.ProvisionHeld, match="ROOT_ACCESS_REQUIRED"):
        provision.provision_and_activate()


def test_canonical_database_and_endpoint_validation(monkeypatch, tmp_path):
    env = tmp_path / "empiredb.env"
    env.write_text("EMPIREDB_DSN=postgresql://local_reader:fixture@127.0.0.1:5432/empiredb\n")
    env.chmod(0o600)
    monkeypatch.setattr(release, "DB_ENV", env)
    monkeypatch.setattr(provision.os, "geteuid", lambda: 0)
    monkeypatch.setattr(provision.os, "geteuid", lambda: 0)
    # CI files are not root-owned; simulate only stat ownership for this fixture.
    original_stat = Path.stat
    class FixtureStat:
        st_uid = 0
        st_mode = 0o100600
    monkeypatch.setattr(provision, "dotenv_values", lambda path: {"EMPIREDB_DSN": "postgresql://reader:fixture@127.0.0.1:5432/empiredb"})
    monkeypatch.setattr(provision.Path, "stat", lambda self: FixtureStat() if self == env else original_stat(self))
    base = provision._canonical_base_conninfo()
    assert base["dbname"] == "empiredb"
    assert base["host"] == "127.0.0.1"
    for bad in ("postgresql://reader:fixture@external.example.com:5432/empiredb",
                "postgresql://reader:fixture@127.0.0.1:5432/postgres",
                "postgresql://reader:fixture@127.0.0.1:6432/empiredb"):
        monkeypatch.setattr(provision, "dotenv_values", lambda path, value=bad: {"EMPIREDB_DSN": value})
        with pytest.raises(provision.ProvisionHeld, match="CANONICAL_LOCAL_EMPIREDB_ENDPOINT_REQUIRED"):
            provision._canonical_base_conninfo()


def test_new_login_dsn_has_only_dedicated_user_and_valid_secret():
    base = {"dbname": "empiredb", "host": "127.0.0.1", "port": "5432",
            "user": "admin", "password": "oldpriv", "application_name": "oldname"}
    dsn = provision._new_reader_dsn(base, "a" * 64)
    assert "empire_founder_reply_reader_login" in dsn
    assert "oldpriv" not in dsn
    assert "oldname" not in dsn
    assert "password=" in dsn
    with pytest.raises(provision.ProvisionHeld, match="UNSAFE_READER_SECRET"):
        provision._new_reader_dsn(base, "untrusted' value")


def test_sql_stays_within_dedicated_login_and_observer_membership(monkeypatch):
    calls = []
    monkeypatch.setattr(provision, "_pg_sql", lambda script: calls.append(script))
    provision._create_login("ab" * 32)
    assert len(calls) == 1
    sql = calls[0]
    assert "CREATE ROLE empire_founder_reply_reader_login LOGIN NOINHERIT NOSUPERUSER" in sql
    assert "GRANT empire_closer_observer TO empire_founder_reply_reader_login WITH INHERIT FALSE, SET TRUE" in sql
    assert "NOBYPASSRLS" in sql
    assert "GRANT CONNECT ON DATABASE empiredb" in sql
    assert "DROP TABLE" not in sql
    assert "GRANT empire_outbound_sender" not in sql
    calls.clear()
    provision._revoke_new_login()
    assert "DROP ROLE IF EXISTS empire_founder_reply_reader_login" in calls[0]


def _mock_release(monkeypatch, tmp_path, *, should_fail=False):
    monkeypatch.setattr(provision.os, "geteuid", lambda: 0)
    private = tmp_path / "reader.dsn"
    unit = tmp_path / "reader.conf"
    monkeypatch.setattr(release, "PRIVATE_DSN_FILE", private)
    monkeypatch.setattr(release, "SYSTEMD_DROPIN", unit)
    monkeypatch.setattr(release, "_json_probe", lambda url: {"provider": "owned_imap"})
    monkeypatch.setattr(provision, "_check_existing_provider_selection", lambda: None)
    monkeypatch.setattr(provision, "_canonical_base_conninfo",
                        lambda: {"dbname": "empiredb", "host": "127.0.0.1"})
    monkeypatch.setattr(provision.secrets, "token_hex", lambda n: "a" * 64)
    calls = []
    monkeypatch.setattr(provision, "_create_login", lambda secret: calls.append(("create", secret)))
    monkeypatch.setattr(provision, "_revoke_new_login", lambda: calls.append(("revoke",)))
    def activate(*, verified_dsn):
        calls.append(("activate", "empire_founder_reply_reader_login" in verified_dsn))
        if should_fail:
            raise release.ReleaseHeld("CANONICAL_REPLY_RELEASE_ROLLED_BACK")
        return {"status": "CANONICAL_REPLY_VIEW_ACTIVE"}
    monkeypatch.setattr(release, "activate", activate)
    return calls


def test_one_shot_provisions_verifies_and_activates(monkeypatch, tmp_path):
    calls = _mock_release(monkeypatch, tmp_path)
    result = provision.provision_and_activate()
    assert result["status"] == "CANONICAL_REPLY_VIEW_ACTIVE"
    assert result["email_sent"] is False
    assert result["outbound_enabled"] is False
    assert result["login_is_write_capable"] is False
    assert [x[0] for x in calls] == ["create", "activate"]


def test_failed_activation_revokes_new_reader_login(monkeypatch, tmp_path):
    calls = _mock_release(monkeypatch, tmp_path, should_fail=True)
    with pytest.raises(provision.ProvisionHeld, match="CANONICAL_REPLY_RELEASE_ROLLED_BACK"):
        provision.provision_and_activate()
    assert [x[0] for x in calls] == ["create", "activate", "revoke"]


def test_preexisting_release_files_are_not_overwritten(monkeypatch, tmp_path):
    calls = _mock_release(monkeypatch, tmp_path)
    file = release.PRIVATE_DSN_FILE
    file.write_text("EXISTING")
    with pytest.raises(provision.ProvisionHeld, match="EXISTING_FOUNDER_REPLY_RELEASE_REQUIRES_REVIEW"):
        provision.provision_and_activate()
    assert file.read_text() == "EXISTING"
    assert calls == []

def test_explicit_existing_imap_setting_blocks_before_creating_login(monkeypatch, tmp_path):
    monkeypatch.setattr(provision.os, "geteuid", lambda: 0)
    cfg = tmp_path / "existing.env"
    cfg.write_text("EMPIRE_FOUNDER_MAILBOX_PROVIDER=owned_imap\n")
    monkeypatch.setattr(release, "EXISTING_FOUNDER_ENV", (cfg,))
    with pytest.raises(provision.ProvisionHeld, match="CONFLICTING_FOUNDER_PROVIDER_SETTING"):
        provision._check_existing_provider_selection()
    cfg.write_text("EMPIRE_FOUNDER_MAILBOX_PROVIDER=empiredb_canonical_replies\n")
    provision._check_existing_provider_selection()
    cfg.unlink()
    cfg.symlink_to(tmp_path / "not-real")
    with pytest.raises(provision.ProvisionHeld, match="UNSAFE_EXISTING_FOUNDER_ENV_SYMLINK"):
        provision._check_existing_provider_selection()


def test_privileged_verified_dsn_override_is_required(monkeypatch):
    monkeypatch.setattr(release.os, "geteuid", lambda: 1000)
    with pytest.raises(release.ReleaseHeld, match="ROOT_ACCESS_REQUIRED"):
        release.activate(verified_dsn="postgresql://fixture")

def test_uncertain_partial_release_keeps_login_for_privileged_recovery(monkeypatch, tmp_path):
    calls = _mock_release(monkeypatch, tmp_path, should_fail=True)
    file = release.PRIVATE_DSN_FILE
    def partial_failure(*, verified_dsn):
        file.write_text("PRIVATE_RUNTIME_CREDENTIAL")
        raise release.ReleaseHeld("ROLLBACK_NEEDS_PRIVILEGED_REPAIR")
    monkeypatch.setattr(release, "activate", partial_failure)
    with pytest.raises(provision.ProvisionHeld, match="READER_RELEASE_NEEDS_PRIVILEGED_REPAIR"):
        provision.provision_and_activate()
    assert file.exists()
    assert [x[0] for x in calls] == ["create"]


def test_provisioner_main_success_does_not_expose_secret(monkeypatch, capsys):
    monkeypatch.setattr(provision, "provision_and_activate", lambda: {
        "status": "CANONICAL_REPLY_VIEW_ACTIVE",
        "login": provision.LOGIN,
        "email_sent": False,
        "outbound_enabled": False,
    })
    assert provision.main([
        "--apply", "--approved-dedicated-reader-and-reply-view-only"
    ]) == 0
    value = json.loads(capsys.readouterr().out)
    assert value["status"] == "CANONICAL_REPLY_VIEW_ACTIVE"
    assert value["database_role_created"] is True
    assert value["secrets_printed"] is False
    assert "private" not in str(value)
