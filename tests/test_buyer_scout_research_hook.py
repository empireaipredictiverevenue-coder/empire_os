from pathlib import Path

from scripts import run_buyer_acquisition_scout as scout


class Done:
    returncode = 0
    stdout = '{"status":"PASS"}'
    stderr = ""


def test_existing_scout_invokes_governed_evidence_without_new_timer(tmp_path):
    seen = []
    def runner(args, **kwargs):
        seen.append((args, kwargs))
        return Done()
    result = scout.research_network_after_scout(str(tmp_path), runner=runner)
    assert result["status"] == "PASS"
    assert result["mode"] == "OBSERVE"
    assert len(seen) == 1
    args, options = seen[0]
    assert args[1] == str(tmp_path / "scripts/run_buyer_network_evidence_cycle.py")
    assert options["timeout"] <= 300
    assert options["env"]["LIVE_OUTBOUND"] == "0"
    assert options["env"]["EMPIRE_EXECUTION_AUTHORITY"] == "OBSERVE"


def test_optional_research_failure_does_not_claim_success(tmp_path):
    class Failure:
        returncode = 7
        stdout = "no buyer"
        stderr = "private-error"
    result = scout.research_network_after_scout(
        str(tmp_path), runner=lambda *a, **k: Failure(),
    )
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 7
    assert "private-error" not in str(result)


def test_existing_systemd_timer_is_reused_without_new_unit():
    root = Path(__file__).resolve().parents[1]
    unit = (root / "deploy/systemd/empire-buyer-acquisition-scout.service").read_text()
    timer = (root / "deploy/systemd/empire-buyer-acquisition-scout.timer").read_text()
    src = (root / "scripts/run_buyer_acquisition_scout.py").read_text()
    assert "run_buyer_acquisition_scout.py" in unit
    assert "OnUnitInactiveSec=30min" in timer
    assert "research_network_after_scout(args.repo_root)" in src
    assert "--skip-buyer-network-research" in src
    assert "OUTBOUND_ENABLED" in src
