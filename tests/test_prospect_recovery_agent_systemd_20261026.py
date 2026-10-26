"""Agent deployment must not execute mutable repo code as root."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_recovery_agent_uses_root_owned_isolated_copy_and_one_timer():
    svc = (ROOT / "deploy/systemd/empire-prospect-recovery-agent.service").read_text()
    timer = (ROOT / "deploy/systemd/empire-prospect-recovery-agent.timer").read_text()
    assert "Type=oneshot" in svc
    assert "User=root" in svc
    assert "/usr/local/libexec/empire-prospect-recovery-agent.py" in svc
    assert "/usr/bin/python3 -I -B " in svc
    assert "PYTHONPATH=" not in svc
    assert "EnvironmentFile=" not in svc
    assert "StateDirectory=empire-prospect-recovery-agent" in svc
    assert "ProtectSystem=strict" in svc
    assert "NoNewPrivileges=true" in svc
    assert "OnUnitInactiveSec=15min" in timer
    assert "empire-prospect-recovery-agent.service" in timer


def test_activation_installs_pinned_root_copy_with_no_gates_changed():
    script = (ROOT / "scripts/activate_prospect_recovery_agent_20261026.sh").read_text()
    assert "sha256sum --check --status" in script
    assert "install -m 0555 -o root -g root" in script
    assert 'systemctl enable --now "$TIMER_NAME"' in script
    assert "empire-prospect-recovery-agent.py" in script
    assert "BUYER_ACTIVATION" not in script
    assert "run_qualification_cycle.py --" not in script


def test_agent_imports_no_untrusted_repository_code():
    source = (ROOT / "empire_os/prospect_recovery_agent.py").read_text()
    assert "from empire_os." not in source
    assert "from scripts." not in source
    assert "subprocess.run(" in source
    assert '("/usr/bin/systemctl", "start", "--no-block", unit)' in source
    assert 'MAX_REPAIR_REQUESTS = 2' in source


def test_owner_upgrade_keeps_existing_timer_and_preserves_root_checksum_gate():
    script = (ROOT / "scripts/upgrade_prospect_recovery_search_health_20261026.sh").read_text()
    assert "sha256sum --check --status" in script
    assert "installed agent differs from prior reviewed version" in script
    assert "systemctl stop \"$TIMER\"" in script
    assert "systemctl start \"$TIMER\"" in script
    assert "systemctl start \"$SERVICE\"" in script
    assert "restoring previously verified agent" in script
    assert "PROSPECT_RECOVERY_SEARCH_HEALTH_ACTIVE" in script
    assert "automatic_additional_search_requests" in script
    assert "empire-prospect-recovery-agent.service" in script
    assert "empire-prospect-recovery-agent.timer" in script
    assert "systemctl enable" not in script
    assert "systemctl disable" not in script
