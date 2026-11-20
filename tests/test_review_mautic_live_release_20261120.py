"""Offline unit tests for the live, read-only Mautic release verifier."""
from __future__ import annotations

import json
import os
import subprocess

from scripts import review_mautic_live_release_20261120 as mod


def test_owner_only_external_secrets_never_get_disclosed(tmp_path, monkeypatch):
    private = tmp_path / "private.env"
    private.write_text(
        "EMPIRE_MAUTIC_DB_ROOT_PASSWORD=" + "a" * 50 + "\n"
        "EMPIRE_MAUTIC_DB_PASSWORD=" + "b" * 50 + "\n"
    )
    private.chmod(0o600)
    monkeypatch.setattr(mod, "ENV", private)
    assert mod._safe_env()
    private.chmod(0o644)
    assert not mod._safe_env()
    private.unlink()
    (tmp_path / "outside").write_text("fixture")
    private.symlink_to(tmp_path / "outside")
    assert not mod._safe_env()


def test_unauthorised_docker_and_missing_real_source_are_reported(monkeypatch):
    def mock_run(*args, **_kwargs):
        if args[0] == "systemctl":
            return subprocess.CompletedProcess(args, 0, stdout="active\n")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="denied")
    monkeypatch.setattr(mod, "_run", mock_run)
    monkeypatch.setattr(mod, "_safe_env", lambda: True)
    monkeypatch.setattr(mod, "_compose_valid", lambda: True)
    monkeypatch.setattr(mod, "_socket_listening", lambda: False)
    monkeypatch.setattr(mod, "_db_catalog", lambda: {
        "canonical_empiredb_login_confirmed": True,
        "mautic_event_inbox_exists": False,
        "mautic_writer_role_exists": False,
        "mautic_tenant_login_count": 0,
        "service_mautic_source_configured": False,
    })
    result = mod.review()
    assert result["result"] == "LIVE_NOT_READY"
    assert "DOCKER_PRIVILEGED_OWNER_REQUIRED" in result["blockers"]
    assert "DBA_GUARDED_MAUTIC_ROLE_AND_INBOX_NOT_PROVISIONED" in result["blockers"]
    assert "NO_LIVE_APPROVED_MAUTIC_SOURCE_OR_EXACT_CONTACT_BINDINGS" in result["blockers"]
    assert result["no_database_writes"] is True
    assert result["no_service_restart"] is True
    assert result["no_outbound_send"] is True
    assert "aaaaa" not in json.dumps(result)
    assert "bbbbb" not in json.dumps(result)


def test_ready_flags_do_not_claim_production_installed(monkeypatch):
    def mock_run(*args, **_kwargs):
        return subprocess.CompletedProcess(args, 0, stdout="active\n")
    monkeypatch.setattr(mod, "_run", mock_run)
    monkeypatch.setattr(mod, "_safe_env", lambda: True)
    monkeypatch.setattr(mod, "_compose_valid", lambda: True)
    monkeypatch.setattr(mod, "_socket_listening", lambda: True)
    monkeypatch.setattr(mod, "_db_catalog", lambda: {
        "canonical_empiredb_login_confirmed": True,
        "mautic_event_inbox_exists": True,
        "mautic_writer_role_exists": True,
        "mautic_tenant_login_count": 1,
        "service_mautic_source_configured": True,
    })
    result = mod.review()
    assert result["blockers"] == []
    assert result["result"] == "READINESS_PROVISIONALLY_PASS_REVIEW_REQUIRED"
