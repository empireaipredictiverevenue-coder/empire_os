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
    assert Path(called[1][0][1]).name == 'observe_buyer_first_party_due_diligence.py'
    assert called[2][0][-1] == "--write"
    assert called[3][0][2:] == ["--write", "--repo-root", str(tmp_path)]
    assert result["buyer_recovery_desk_refresh_attempted"] is True
    assert result['first_party_due_diligence_refresh_attempted'] is True
    assert result["founder_qualification_snapshot_refresh_attempted"] is True
    assert result["founder_review_automatic_approval"] is False
    assert all(kw["timeout"] <= 120 for _, kw in called)
    assert all(kw['timeout'] <= 90 for args,kw in called if 'observe_buyer_' in args[1])
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
        return FakeDone() if len(calls) < 3 else Error()

    source = tmp_path / "runtime/buyer_network_intelligence"
    source.mkdir(parents=True)
    result = task.run(root=tmp_path, call=runner)
    assert result["status"] == "FAILED"
    assert [r["status"] for r in result["steps"]] == ["PASS", "PASS", "FAILED"]
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


def test_prior_stage_failure_prevents_recovery_desk_stage(tmp_path):
    class Error:
        returncode = 3
        stdout = "blocked"
        stderr = "private"
    calls = []
    def runner(args, **kwargs):
        calls.append(Path(args[1]).name)
        return FakeDone() if len(calls) < 2 else Error()
    directory = tmp_path / "runtime/buyer_network_intelligence"
    directory.mkdir(parents=True)
    result = task.run(root=tmp_path, call=runner)
    assert result["status"] == "FAILED"
    assert calls == list(task.STEPS[:2])
    assert result["buyer_recovery_desk_refresh_attempted"] is False
    assert result["execution_authority"] == "NONE"
    assert result["outbound_sent"] is False


def test_original_cycle_creates_safe_effectiveness_snapshot_without_duplicate_workers(tmp_path):
    source = tmp_path / "runtime/buyer_network_intelligence"
    source.mkdir(parents=True)
    files = {
        "verification_backlog_latest.json": {"candidates": []},
        "research_ledger_latest.json": {"domains": {}},
        "direct_site_verification_latest.json": {"results": []},
        "research_progress_latest.json": {"latest_batch_domains": [], "latest_batch_count": 0},
    }
    for name, value in files.items():
        (source / name).write_text(json.dumps(value))
    result = task.run(root=tmp_path, call=lambda args, **kwargs: FakeDone())
    assert result["status"] == "PASS"
    assert result["scout_effectiveness_status"] == "UNMEASURABLE_MISSING_OR_UNSAFE_SOURCE"
    record = json.loads((source / "scout_effectiveness_latest.json").read_text())
    assert record["company_research_evidence_improvement_count"] == 0
    assert record["status"] == "UNMEASURABLE_MISSING_OR_UNSAFE_SOURCE"
    assert record["database_writes"] is False
    assert record["outbound_sent"] is False


def test_recovery_desk_failure_does_not_hide_valid_effectiveness_measurement(tmp_path):
    source = tmp_path / "runtime/buyer_network_intelligence"
    source.mkdir(parents=True)
    source_data = {
        "verification_backlog_latest.json": {"candidates": []},
        "research_ledger_latest.json": {"domains": {}},
        "direct_site_verification_latest.json": {"results": []},
        "research_progress_latest.json": {"latest_batch_count": 0,
                                          "latest_batch_domains": []},
    }
    for name, data in source_data.items():
        (source / name).write_text(json.dumps(data))
    class Block:
        returncode = 2
        stdout = '{"status":"BLOCKED","reason":"UNSAFE_OR_CHANGING_BUYER_EVIDENCE"}'
        stderr = ''
    calls=[]
    def run(args, **kwargs):
        calls.append(args)
        return FakeDone() if len(calls) < 4 else Block()
    outcome = task.run(root=tmp_path, call=run)
    assert outcome["status"] == "FAILED"
    assert outcome["scout_effectiveness_status"] == "UNMEASURABLE_MISSING_OR_UNSAFE_SOURCE"
    assert (source / "scout_effectiveness_latest.json").exists()
    assert outcome["outbound_sent"] is False
