from pathlib import Path

from scripts.run_opportunity_loop import run_opportunity_loop


def test_opportunity_loop_runs_in_order_and_stays_noncommercial(tmp_path):
    calls = []

    def radar(root: Path):
        calls.append(("radar", root))
        return {"candidate_count": 3}

    def research(root: Path):
        calls.append(("research", root))
        return {
            "researched_candidate_count": 2,
            "observation_count": 5,
            "error_count": 0,
        }

    def intake(root: Path):
        calls.append(("intake", root))
        return {
            "candidate_count": 3,
            "factory_ready_count": 0,
            "blocked_count": 3,
        }

    result = run_opportunity_loop(
        tmp_path,
        radar_fn=radar,
        research_fn=research,
        intake_fn=intake,
    )
    assert [name for name, _ in calls] == [
        "radar",
        "research",
        "intake",
    ]
    assert result["ok"] is True
    assert result["automatic_internal_research"] is True
    assert result["automatic_external_execution_allowed"] is False
    assert result["outreach_sent"] is False
    assert result["payment_action"] is False
    assert result["revenue_recognized"] is False
    assert result["execution_authority"] == "none"


def test_opportunity_loop_fails_closed_and_stops_on_step_error(tmp_path):
    calls = []

    def radar(_root):
        calls.append("radar")
        raise RuntimeError("radar failed")

    def should_not_run(_root):
        calls.append("unexpected")
        return {}

    result = run_opportunity_loop(
        tmp_path,
        radar_fn=radar,
        research_fn=should_not_run,
        intake_fn=should_not_run,
    )
    assert calls == ["radar"]
    assert result["ok"] is False
    assert result["steps"][0]["step"] == "opportunity_radar"
