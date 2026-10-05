from pathlib import Path

import pytest

from empire_os import remote_commander as rc


def test_remote_commander_never_exposes_general_shell():
    assert "run_shell" not in rc.OPERATIONS
    assert "run_command" not in rc.OPERATIONS
    assert rc.health()["general_shell"] is False


def test_remote_commander_protected_paths_remain_blocked():
    with pytest.raises(Exception):
        rc.execute("file_read", {"path": "recovery/secret.txt"})
    with pytest.raises(Exception):
        rc.execute("file_read", {"path": "toop/private.txt"})


def test_remote_commander_rejects_write_without_internal_authority(tmp_path, monkeypatch):
    with pytest.raises(rc.RemoteCommanderError, match="internal_write"):
        rc.execute(
            "file_write",
            {"path": "empire_os/never_write.py", "content": "x=1\n"},
            allow_write=False,
        )


def test_remote_commander_rejects_unknown_operation():
    with pytest.raises(rc.RemoteCommanderError, match="not allowlisted"):
        rc.execute("arbitrary_shell", {"command": "id"})


def test_remote_commander_check_allowlist_is_bounded():
    with pytest.raises(rc.RemoteCommanderError, match="not allowlisted"):
        rc.run_check("shell", "tests/test_remote_commander.py")


def test_remote_commander_service_and_journal_share_allowlist(monkeypatch):
    seen = []

    def fake_run(args, timeout=30):
        seen.append(args)
        return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(rc, "run_command", fake_run)
    unit = next(iter(rc.ALLOWED_UNITS))
    rc.journal_tail(unit, 50)
    assert seen[0][0] == "journalctl"
    assert unit in seen[0]

    with pytest.raises(rc.RemoteCommanderError, match="allowlisted"):
        rc.journal_tail("ssh.service", 10)


def test_remote_commander_credential_rotator_never_prints_secret():
    source = Path("scripts/rotate_empire_remote_commander_token.py").read_text()
    assert "token_sha256" in source
    assert "secret_printed=false" in source
    assert "print(token)" not in source
    assert "0o600" in source


def test_remote_commander_installer_holds_live_activation_by_default():
    source = Path("scripts/install_empire_remote_commander.sh").read_text()
    assert 'ACTIVATE=0' in source
    assert '"--activate"' in source
    assert 'activation=HELD' in source
    assert "enable --now empire-ops-mcp.service" in source


def test_cloudflare_candidate_keeps_mcp_loopback_only():
    source = Path(
        "deploy/cloudflare/empire-remote-commander-ingress.yml.example"
    ).read_text()
    assert "mcp.empire-ai.co.uk" in source
    assert "http://127.0.0.1:8765" in source



def test_external_activation_derives_live_tunnel_and_uses_tunnel_owner():
    source = Path(
        "scripts/activate_empire_remote_commander_external.sh"
    ).read_text()
    assert 'payload.get("tunnel")' in source
    assert "Empire-AI" not in source
    assert "sudo -u ubuntu" in source
    assert "mcp.empire-ai.co.uk" in source
