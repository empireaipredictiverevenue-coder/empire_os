from pathlib import Path
import json
import subprocess

from scripts import run_buyer_network_evidence_cycle as task


class FakeDone:
    returncode = 0
    stdout = '{"mode":"OBSERVE","status":"PASS"}'
    stderr = ""


def test_bounded_cycle_reuses_existing_stages_without_outbound(tmp_path):
    called = []
    def call(args, **kwargs):
        called.append((args, kwargs))
        return FakeDone()

    source = tmp_path / "runtime/buyer_network_intelligence"
    source.mkdir(parents=True)
    for file, data in (
        ("verification_backlog_latest.json", {
            "generated_at": "2026-10-09T20:00:00Z", "candidates": []
        }),
        ("research_ledger_latest.json", {"domains": {}}),
        ("direct_site_verification_latest.json", {"results": []}),
        ("research_progress_latest.json", {"latest_batch_domains": [], "latest_batch_count": 0}),
    ):
        (source / file).write_text(json.dumps(data))
    result = task.run(root=tmp_path, call=call)
    assert result["status"] == "PASS"
    assert result["execution_authority"] == "NONE"
    assert result["outbound_sent"] is False
    assert result["db_write"] is False
    assert result["founder_review_automatic_approval"] is False
    assert [Path(args[0][1]).name for args in called] == list(task.STEPS)
    assert called[1][0][-1] == "--write"
    assert result["founder_qualification_snapshot_refresh_attempted"] is True
    assert result["founder_review_automatic_approval"] is False
    assert all(kw["timeout"] <= 120 for _, kw in called)
    assert all(kw["env"]["LIVE_OUTBOUND"] == "0" for _, kw in called)
    assert (tmp_path / "runtime/buyer_network_intelligence/research_cycle_latest.json").is_file()


def test_qualification_refresh_failure_is_visible_and_cannot_approve(tmp_path):
    class Error:
        returncode = 2
        stdout = "BLOCKED"
        stderr = "private information"

    calls = []
    def runner(args, **kwargs):
        calls.append(args)
        return FakeDone() if len(calls) == 1 else Error()

    source = tmp_path / "runtime/buyer_network_intelligence"
    source.mkdir(parents=True)
    result = task.run(root=tmp_path, call=runner)
    assert result["status"] == "FAILED"
    assert [r["status"] for r in result["steps"]] == ["PASS", "FAILED"]
    assert calls[-1][-1] == "--write"
    assert result["founder_review_automatic_approval"] is False
    assert result["outbound_sent"] is False
    assert "private information" not in str(result)


def test_plan_only_no_file_mutation(tmp_path):
    called = []
    def call(args, **kwargs):
        called.append(args)
        return FakeDone()
    result = task.run(root=tmp_path, plan_only=True, call=call)
    assert result["status"] == "PASS"
    assert len(called) == 1
    assert called[0][-1] == "--plan-only"
    assert not (tmp_path / "runtime").exists()


def test_cycle_failure_stops_before_promotion(tmp_path):
    class FakeFailed:
        returncode = 1
        stdout = ""
        stderr = "blocked"
    seen = []
    def call(args, **kwargs):
        seen.append(args)
        return FakeFailed()
    result = task.run(root=tmp_path, call=call)
    assert result["status"] == "FAILED"
    assert len(seen) == 1
    assert result["steps"][0]["stderr_type"] == "PRESENT"
    assert "blocked" not in str(result)
