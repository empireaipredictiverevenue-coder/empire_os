from pathlib import Path
from types import SimpleNamespace
from scripts.run_buyer_gmail_evidence_cycle import run, STEPS, OPTIONAL_STEPS

def test_full_cycle_runs_in_order_and_disables_outbound(tmp_path):
    (tmp_path / "scripts").mkdir()
    calls = []
    def invoke(args, **kwargs):
        calls.append((Path(args[1]).name, args[2], kwargs["env"]["OUTBOUND_ENABLED"]))
        return SimpleNamespace(returncode=0)
    result = run(root=tmp_path, invoke=invoke)
    assert result["status"] == "PASS"
    assert calls == [(s, "--write", "0") for s in STEPS + OPTIONAL_STEPS]
    assert result["auxiliary_steps"][0]["status"] == "PASS"
    assert result["outbound_authorized"] is False

def test_failed_step_stops_before_reconciliation(tmp_path):
    (tmp_path / "scripts").mkdir()
    calls = []
    def invoke(args, **kwargs):
        calls.append(Path(args[1]).name)
        return SimpleNamespace(returncode=1 if len(calls)==2 else 0)
    result = run(root=tmp_path, invoke=invoke)
    assert result["status"] == "BLOCKED"
    assert calls == list(STEPS[:2])
    assert result["execution_authority"] == "NONE"


def test_timeout_fails_closed_and_never_starts_next_step(tmp_path):
    import subprocess
    (tmp_path / "scripts").mkdir()
    calls = []
    def timeout(args, **kwargs):
        calls.append(Path(args[1]).name)
        raise subprocess.TimeoutExpired(args, 90)
    result = run(root=tmp_path, invoke=timeout)
    assert result["status"] == "BLOCKED"
    assert result["steps"][0]["status"] == "TIMEOUT"
    assert calls == [STEPS[0]]
    assert result["outbound_authorized"] is False
    assert result["execution_authority"] == "NONE"


def test_exact_workspace_monitor_uses_existing_cycle_only(tmp_path):
    (tmp_path / "scripts").mkdir()
    calls=[]
    def invoke(args, **kwargs):
        step=Path(args[1]).name
        calls.append(step)
        return SimpleNamespace(returncode=3 if step ==
            "poll_workspace_solar_outreach_readonly.py" else 0)
    result=run(root=tmp_path, invoke=invoke)
    assert calls.count("poll_workspace_solar_outreach_readonly.py") == 1
    assert calls == list(STEPS+OPTIONAL_STEPS)
    assert all(step in calls for step in STEPS)
    assert result["status"] == "PASS"
    assert result["auxiliary_steps"][1]["status"] == "HELD"
    assert result["outbound_authorized"] is False
    assert result["execution_authority"] == "NONE"


def test_optional_workspace_outage_cannot_block_original_gmail_cycle(tmp_path):
    (tmp_path / "scripts").mkdir()
    calls=[]
    def invoke(args, **kwargs):
        step=Path(args[1]).name
        calls.append(step)
        return SimpleNamespace(returncode=2 if step in OPTIONAL_STEPS else 0)
    result=run(root=tmp_path,invoke=invoke)
    assert result["status"]=="PASS"
    assert result["outbound_authorized"] is False
    assert result["auxiliary_steps"][0]["status"]=="HELD"
    assert calls==list(STEPS+OPTIONAL_STEPS)
