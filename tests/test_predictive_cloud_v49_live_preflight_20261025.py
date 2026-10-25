"""V4.9 read-only owner-activation preflight; no service changes permitted."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from scripts import inspect_predictive_cloud_v49_live_preflight_20261025 as v49


def test_v49_preflight_has_no_privileged_write_or_service_restart():
    src = Path(v49.__file__).read_text()
    assert '"systemctl", "show"' in src
    for forbidden in ("systemctl restart", "systemctl stop", "systemctl start",
                      "daemon-reload", "sudo ", "os.system(", "os.chmod(",
                      "subprocess.Popen(", "os.unlink(", ".write_text(",
                      ".write_bytes(", "urlopen(Request("):
        assert forbidden not in src
    assert "http://127.0.0.1:8766" in src
    assert "V49_READ_ONLY_FLAG_REQUIRED" in src
    assert "ROOT" not in src or "root_owned" in src


def test_candidate_dropin_preserves_original_unit_configuration():
    candidate = Path(__file__).resolve().parents[1] / "scripts/empire-founder-dashboard-api-v49-readonly.conf"
    contents = candidate.read_text()
    assert contents.splitlines()[0] == "[Service]"
    assert contents.count("ExecStart=") == 2
    assert "--host 127.0.0.1 --port 8766" in contents
    assert "predictive_cloud_v49_existing_api_overlay_20261025:app" in contents
    for forbidden in ("Environment=", "ExecStartPre=", "OnFailure=", "User=root",
                      "ExecStartPost=", "sudo", "systemctl", "redis-server",
                      "postgres", "--host 0.0.0.0"):
        assert forbidden not in contents


def test_read_only_cli_flag_required_before_inspection():
    outcome = subprocess.run(
        [sys.executable, "-B", str(v49.__file__)],
        capture_output=True, text=True, timeout=5,
    )
    assert outcome.returncode != 0
    assert "V49_READ_ONLY_FLAG_REQUIRED" in outcome.stderr


def test_readiness_helpers_reject_missing_or_unsafe_deployment(monkeypatch, tmp_path):
    module = tmp_path / "code.py"
    module.write_text("nothing")
    assert v49.sha256(module) is not None
    assert v49.sha256(tmp_path / "absent.py") is None
    monkeypatch.setattr(v49, "MODULE", module)
    monkeypatch.setattr(v49, "WRAPPER", tmp_path / "no-wrapper.py")
    monkeypatch.setattr(v49, "CANDIDATE", tmp_path / "no-candidate.conf")
    monkeypatch.setattr(v49, "STAGE", tmp_path / "no-stage")
    monkeypatch.setattr(v49, "DROP_DIR", tmp_path)
    monkeypatch.setattr(v49, "DROPIN", tmp_path / "no-systemd.conf")
    monkeypatch.setattr(v49, "service_properties",
                        lambda: {"MainPID":"999","ActiveState":"active",
                                 "ExecStart":"synthetic-noncanonical-service"})
    monkeypatch.setattr(v49, "response", lambda _: (404, {}))
    report = v49.inspect()
    assert report["status"] == "V49_ACTIVATION_PREFLIGHT_HELD"
    assert report["root_service_activation_executed"] is False
    assert report["funds_or_trading_activated"] is False
    assert report["checks"]["original_or_v49_pinned_service"] is False
    assert report["checks"]["pinned_v49_overlay_hash"] is False
