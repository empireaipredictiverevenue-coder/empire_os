"""Isolated consent-governor shadow contract; never call systemd or send mail."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_consent_suppression_governor_shadow as runner
from empire_os.consent_suppression_governor_shadow import SourceNode


def setup_runner(tmp_path, monkeypatch, *, allow=0, mode="OBSERVE",
                 live_authority=False, governor_active=True,
                 timer_active=True, safe_governance=True):
    root = tmp_path / "empire"
    root.mkdir()
    control = tmp_path / "read_only_control.json"
    dest = tmp_path / "governor_shadow.json"
    control.write_text(json.dumps({
        "semantic_coverage": {"effectiveness": "EFFECTIVE_IDENTITY_BINDING"},
        "mode": mode,
        "live_action_authority_verified": live_authority,
        "output_quality": {"block_count": 7, "hold_count": 0,
                           "allow_decision_count": allow},
        "governance": {"db_write": False, "outbound": False,
                       "traffic": False, "funds": False}
            if safe_governance else {"outbound": True},
    }))
    entry = root / "scripts" / "outbound_governor_worker.py"
    entry.parent.mkdir(parents=True)
    entry.write_text("print('mock')\n")
    calls = []

    def fake_props(unit):
        calls.append(unit)
        active = (
            governor_active if unit.endswith(".service") else timer_active
        )
        return {
            "ActiveState": "active" if active else "inactive",
            "SubState": "running" if active else "dead",
            "UnitFileState": "enabled",
            "ExecStart": str(entry),
        }

    def fake_trace(path):
        assert path == entry
        return [
            SourceNode(
                path="scripts/outbound_governor_worker.py",
                imports=(),
                suppression_signals=("outbound_suppressions", "is_suppressed"),
            )
        ]

    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "CONTROL", control)
    monkeypatch.setattr(runner, "OUT", dest)
    monkeypatch.setattr(runner, "unit_props", fake_props)
    monkeypatch.setattr(runner, "python_paths_from_execstart", lambda _x: [entry])
    monkeypatch.setattr(runner, "trace_local_graph", fake_trace)
    return control, dest, calls


def test_shadow_can_pass_static_proof_but_never_live_authority(
    tmp_path, monkeypatch, capsys
):
    _, dest, calls = setup_runner(tmp_path, monkeypatch)
    runner.main()
    summary = json.loads(capsys.readouterr().out)
    result = json.loads(dest.read_text())
    assert summary["status"] == "PASS"
    assert summary["shadow_allow"] == 0
    assert result["shadow_action_authority"] == {
        "verified": True,
        "live_execution_authority": False,
        "reason": result["shadow_action_authority"]["reason"],
    }
    assert result["governance"]["outbound"] is False
    assert result["governance"]["db_write"] is False
    assert calls == [
        "empire-outbound-governor.service",
        "empire-outbound-governor.timer",
    ]


@pytest.mark.parametrize("overrides", [
    {"allow": 1},
    {"mode": "EXECUTE"},
    {"live_authority": True},
    {"safe_governance": False},
    {"timer_active": False},
])
def test_shadow_never_passes_if_upstream_or_runtime_is_unsafe(
    tmp_path, monkeypatch, capsys, overrides
):
    _, dest, _ = setup_runner(tmp_path, monkeypatch, **overrides)
    runner.main()
    summary = json.loads(capsys.readouterr().out)
    result = json.loads(dest.read_text())
    assert summary["status"] == "HOLD"
    assert summary["shadow_authority_verified"] is False
    assert summary["live_authority"] is False
    assert result["shadow_action_authority"]["verified"] is False
    assert result["shadow_action_authority"]["live_execution_authority"] is False
    assert result["governance"]["outbound"] is False


def test_unverified_control_stops_without_talking_to_systemd_or_writing(
    tmp_path, monkeypatch
):
    control, dest, calls = setup_runner(tmp_path, monkeypatch)
    data = json.loads(control.read_text())
    data["semantic_coverage"]["effectiveness"] = "INSUFFICIENT_EVIDENCE"
    control.write_text(json.dumps(data))
    with pytest.raises(SystemExit, match="identity coverage not effective"):
        runner.main()
    assert calls == []
    assert not dest.exists()
