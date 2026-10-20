"""Run the ACTUAL existing Ops Control main with sandboxed source and output roots.

Mocks unrelated systemd/network/repair readers. Commercial inputs and adaptive
decision/journal code are real. Production is never accessed or modified.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from test_commercial_adaptive_intelligence_cli import _test_sources


SCRIPT = Path("scripts/run_ops_control_cycle.py")


def _load_ops():
    spec = importlib.util.spec_from_file_location("sandbox_ops_cycle", SCRIPT)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _configure_sandbox(monkeypatch, m, root):
    _test_sources(root)
    original_path = Path

    def sandbox_path(value):
        name = str(value)
        if name == "/srv/empire_os":
            return root
        if name.startswith("/srv/empire_os/"):
            return root / name[len("/srv/empire_os/"):]
        return original_path(value)

    monkeypatch.setattr(m, "Path", sandbox_path)
    ops = root / "runtime/ops_control"
    ops.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(m, "OUTPUT", ops / "latest.json")
    monkeypatch.setenv("EMPIRE_OPS_HEAL_MODE", "OBSERVE")
    monkeypatch.setattr(m, "supabase_egress_contained", lambda: False)
    monkeypatch.setattr(m, "run_runtime_self_heal",
                        lambda **_: {"status": "HEALTHY"})
    monkeypatch.setattr(m, "observe",
                        lambda *_: {"findings": [], "repair_plan": []})
    monkeypatch.setattr(m, "collect_sovereign_infrastructure_health",
                        lambda: {"status": "HEALTHY", "service_findings": []})
    monkeypatch.setattr(m, "build_engineering_health_report", lambda *_: None)
    monkeypatch.setattr(m, "build_incident_report", lambda *_: {
        "diagnoses": [], "incident_count": 0, "requires_escalation": False,
        "highest_priority": None,
    })
    monkeypatch.setattr(m, "read_commercial_loop", lambda *_: {})
    monkeypatch.setattr(m, "build_conveyor", lambda *_: {
        "loop_complete": False, "current_blocker": "NO_VERIFIED_ORDER",
        "owner_component": "commercial_loop_observer",
        "authority": "observe", "stages": [],
    })
    monkeypatch.setattr(m, "observe_leadgen_truth", lambda *_a, **_kw: {
        "status": "BLOCKED", "preflight_checks_clear": False,
        "integrity_findings": [], "readiness_blockers": ["NO_REAL_BUYER"],
    })
    monkeypatch.setattr(m, "observe_user_workers", lambda: {
        "status": "HEALTHY", "workers": [], "confirmed_failed_worker_count": 0,
    })
    return ops


def test_original_ops_main_first_then_repeated_cycle_uses_durable_memory(
        monkeypatch, tmp_path, capsys):
    m = _load_ops()
    ops = _configure_sandbox(monkeypatch, m, tmp_path)
    assert m.main() == 0
    capsys.readouterr()
    latest = json.loads((ops / "latest.json").read_text())
    assert latest["adaptive_commercial_summary"]["available"] is True
    assert latest["adaptive_commercial_summary"]["material_evidence_changed"] is True
    assert latest["adaptive_commercial_review"]["execution_authority"] == "none"
    assert latest["health_domains"]["adaptive_commercial_intelligence"] == "COMMERCIAL_EVIDENCE_REVIEW_HOLD"
    ledger = ops / "adaptive_commercial_transitions.jsonl"
    assert len(ledger.read_text().splitlines()) == 1
    assert m.main() == 0
    capsys.readouterr()
    latest = json.loads((ops / "latest.json").read_text())
    assert latest["adaptive_commercial_summary"]["material_evidence_changed"] is False
    assert latest["adaptive_commercial_summary"]["repeated_work_suppressed"] is True
    assert latest["adaptive_commercial_review"]["transition"] == "UNCHANGED_COMMERCIAL_HOLD"
    assert len(ledger.read_text().splitlines()) == 1
    assert not (tmp_path / "runtime/incidents/latest.json").is_symlink()


def test_original_ops_main_source_revision_change_while_buyer_stays_unverified(
        monkeypatch, tmp_path, capsys):
    m = _load_ops()
    ops = _configure_sandbox(monkeypatch, m, tmp_path)
    assert m.main() == 0
    capsys.readouterr()
    original = tmp_path / "runtime/conversation_recovery/latest.json"
    data = json.loads(original.read_text())
    data["producer_revision"] = "new-but-no-authenticated-reply"
    original.write_text(json.dumps(data))
    assert m.main() == 0
    capsys.readouterr()
    latest = json.loads((ops / "latest.json").read_text())
    s = latest["adaptive_commercial_summary"]
    assert s["material_evidence_changed"] is False
    assert s["original_source_changed_without_proof"] is True
    assert latest["adaptive_commercial_review"]["outbound_authorized"] is False
    assert latest["adaptive_sales_review"]["case_local_provider_authentication_attested"] is False
    journal = [json.loads(s) for s in (ops / "adaptive_commercial_transitions.jsonl").read_text().splitlines()]
    assert len(journal) == 2
    assert journal[-1]["event_code"] == "ORIGINAL_SOURCE_RECEIPT_CHANGED_ONLY"
    assert journal[-1]["outbound_sent"] is False
    assert m.main() == 0
    capsys.readouterr()
    assert len((ops / "adaptive_commercial_transitions.jsonl").read_text().splitlines()) == 2


def test_original_ops_main_crash_after_journal_before_snapshot_is_retry_safe(
        monkeypatch, tmp_path, capsys):
    m = _load_ops()
    ops = _configure_sandbox(monkeypatch, m, tmp_path)
    original_append = m.append_change_once
    attempts = {"count": 0}

    def interrupted_after_durable_journal(*args):
        result = original_append(*args)
        if attempts["count"] == 0:
            attempts["count"] += 1
            raise OSError("simulated interruption after successful journal append")
        return result

    monkeypatch.setattr(m, "append_change_once", interrupted_after_durable_journal)
    with pytest.raises(OSError, match="simulated interruption"):
        m.main()
    capsys.readouterr()
    ledger = ops / "adaptive_commercial_transitions.jsonl"
    assert len(ledger.read_text().splitlines()) == 1
    assert not (ops / "latest.json").exists()
    assert m.main() == 0
    capsys.readouterr()
    assert len(ledger.read_text().splitlines()) == 1
    snap = json.loads((ops / "latest.json").read_text())
    assert snap["adaptive_commercial_summary"]["available"] is True
    assert snap["adaptive_commercial_review"]["outbound_authorized"] is False


def test_source_failure_does_not_echo_untrusted_old_checkpoint(monkeypatch, tmp_path, capsys):
    m = _load_ops()
    ops = _configure_sandbox(monkeypatch, m, tmp_path)
    first = m.main()
    assert first == 0
    capsys.readouterr()
    old = json.loads((ops / "latest.json").read_text())
    old["adaptive_sales_review"]["recipient"] = "private@example.invalid"
    old["adaptive_commercial_review"]["secret_company"] = "Private Ltd"
    (ops / "latest.json").write_text(json.dumps(old))
    (tmp_path / "runtime/predictive_revenue/commercial_offer_book/latest.json").unlink()
    assert m.main() == 0
    capsys.readouterr()
    after = json.loads((ops / "latest.json").read_text())
    assert after["adaptive_commercial_summary"]["available"] is False
    assert "private@example.invalid" not in json.dumps(after)
    assert "Private Ltd" not in json.dumps(after)
    assert after["adaptive_commercial_summary"]["outbound_authorized"] is False
