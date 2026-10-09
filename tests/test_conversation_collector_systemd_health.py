"""Systemd collector health surfaces failures without blocking department tasks."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 9, 18, tzinfo=timezone.utc)


def _module():
    p = ROOT / "scripts/check_conversation_collector_systemd_health.py"
    spec = importlib.util.spec_from_file_location("collector_monitor_unit_test", p)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write(root, *, status="READ_SUCCESS", checked_at=NOW):
    dest = root / "runtime/conversations_replies_control"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "collector_health_latest.json").write_text(json.dumps({
        "status": status, "observed_at": checked_at.isoformat(),
        "source_query_completed": status == "READ_SUCCESS",
        "database_table_count": 1,
    }))
    (dest / "latest.json").write_text(json.dumps({
        "generated_at": (checked_at-timedelta(seconds=1)).isoformat(),
        "canonical_messages": [],
    }))


def test_health_unit_passes_current_success_and_no_buyer_proof(tmp_path):
    write(tmp_path)
    assert _module().verify(tmp_path, NOW) == "PASS"


def test_health_unit_surfaces_failure_with_independent_error_code(tmp_path):
    write(tmp_path, status="DATABASE_SOURCE_READ_FAILED")
    assert _module().verify(tmp_path, NOW) == "COLLECTOR_READ_UNVERIFIED"
    write(tmp_path, checked_at=NOW-timedelta(hours=2))
    assert _module().verify(tmp_path, NOW) == "COLLECTOR_HEALTH_STALE"


def test_health_unit_requires_correlated_canonical_data(tmp_path):
    write(tmp_path)
    p = tmp_path/"runtime/conversations_replies_control/latest.json"
    p.write_text(json.dumps({"generated_at": (NOW-timedelta(hours=1)).isoformat()}))
    assert _module().verify(tmp_path, NOW) == "COLLECTOR_SOURCE_UNCORRELATED"


def test_health_unit_fails_when_source_files_missing(tmp_path):
    assert _module().verify(tmp_path, NOW) == "COLLECTOR_EVIDENCE_MISSING"


def test_dropin_is_independent_no_timer_or_dept_restart():
    unit = (ROOT/"deploy/systemd/empire-conversation-collector-health.service").read_text()
    drop = (ROOT/"deploy/systemd/empire-department-cycle-conversation-health.conf").read_text()
    installer = (ROOT/"scripts/install_conversation_collector_health.sh").read_text()
    assert "Type=oneshot" in unit
    assert "User=ubuntu" in unit
    assert "ProtectSystem=strict" in unit
    assert "ExecStartPost=-/usr/bin/systemctl start --no-block " in drop
    assert "empire-conversation-collector-health.service" in drop
    assert "ExecStartPost=" not in unit
    assert "OnCalendar=" not in unit + drop
    assert "OnBootSec=" not in unit + drop
    assert "systemctl start empire-department-cycle" not in installer
    assert "systemctl restart empire-department-cycle" not in installer
    assert "systemctl start \"$SERVICE\"" in installer


def test_package_check_only_does_not_touch_systemd():
    script = ROOT/"scripts/install_conversation_collector_health.sh"
    result = subprocess.run(
        ["bash", str(script), "--check"], cwd=ROOT,
        capture_output=True, text=True, timeout=8,
    )
    assert result.returncode == 0, result.stderr
    assert "HEALTH_MONITOR_PACKAGE_PREFLIGHT=PASS" in result.stdout
    assert "ACTIVATION=NOT_APPLIED" in result.stdout
    assert "NEW_TIMER_INSTALLED=NO" in result.stdout
    check = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert check.returncode == 0, check.stderr


def test_unauthorized_apply_never_installs_service():
    import os
    if os.geteuid() == 0:
        return
    script = ROOT/"scripts/install_conversation_collector_health.sh"
    result = subprocess.run(
        ["bash", str(script), "--apply"], cwd=ROOT,
        capture_output=True, text=True, timeout=8,
    )
    assert result.returncode == 4
    assert "approved root session required" in result.stderr
