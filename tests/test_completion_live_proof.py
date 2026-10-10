import json
from datetime import datetime, timezone
from pathlib import Path

from empire_os.completion_live_proof import run_completion_live_proof


NOW = datetime(2026, 10, 3, 0, 15, tzinfo=timezone.utc)


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")


def test_exact_rule_writes_line_bound_checkpoint_only_on_all_pass(tmp_path):
    _write(
        tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md",
        "# Demo\n"
        "## Quant Brain / Decision Verification — ACTIVE\n"
        "- [ ] Live EmpireOS verification of Quant endpoints and opportunity Quant Review\n",
    )
    _write(
        tmp_path / "runtime/opportunity_factory/quant_review_latest.json",
        {
            "schema_version": "empire.opportunity_quant_review.v1",
            "execution_authority": "none",
        },
    )

    def http_get(url):
        if url.endswith("/health"):
            return 200, json.dumps({"ok": True})
        return 200, json.dumps({"available": True})

    result = run_completion_live_proof(
        tmp_path,
        now=NOW,
        http_get=http_get,
        systemd_probe=lambda unit, mode: False,
    )

    assert result["live_proof_pass_count"] == 1
    ref = result["checkpoints_written"][0]
    packet = json.loads((tmp_path / ref).read_text())
    assert packet["stage"] == "LIVE_VERIFY_DONE"
    assert packet["checklist_lines"] == [3]
    assert packet["synthetic_evidence_used"] is False


def test_partial_probe_does_not_write_checkpoint(tmp_path):
    _write(
        tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md",
        "# Demo\n"
        "## Autonomous Predictive Cloud / Opportunity Loop — ACTIVE\n"
        "- [ ] Install/enable autonomous Opportunity Loop timer if tests pass\n",
    )
    _write(
        tmp_path / "runtime/opportunity_radar/loop_latest.json",
        {
            "automatic_quant_review": True,
            "execution_authority": "none",
        },
    )

    result = run_completion_live_proof(
        tmp_path,
        now=NOW,
        http_get=lambda url: (0, ""),
        systemd_probe=lambda unit, mode: mode == "enabled",
    )

    assert result["live_proof_pass_count"] == 0
    assert result["live_proof_blocked_count"] == 1
    assert result["checkpoints_written"] == []


def test_unconfigured_items_are_not_guessed(tmp_path):
    _write(
        tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md",
        "# Demo\n## Other\n- [ ] Unknown feature\n",
    )

    result = run_completion_live_proof(
        tmp_path,
        now=NOW,
        http_get=lambda url: (200, "{}"),
        systemd_probe=lambda unit, mode: True,
    )

    assert result["pending_rule_match_count"] == 0
    assert result["checkpoints_written"] == []

def _fresh_recurring_fixture(root: Path, *, timestamp: datetime = NOW) -> None:
    _write(
        root / "docs/MASTER_REMAINING_CHECKLIST.md",
        "# Demo\n"
        "## Automate recurring intelligence\n"
        "- [ ] Automatic Founder snapshot refresh\n"
        "- [ ] Service/timer health\n",
    )
    _write(
        root / "runtime/astra/executive_latest.json",
        {"schema_version": "empire.astra.executive.v2",
         "generated_at": timestamp.isoformat(),
         "execution_authority": "none", "mode": "OBSERVE"},
    )
    _write(
        root / "runtime/execution_plane/empire_completion_program_progress.json",
        {"schema_version": "empire.completion-program-progress.v1",
         "updated_at": timestamp.isoformat()},
    )
    _write(
        root / "runtime/ops_control/latest.json",
        {"schema_version": "empire.ops_control_cycle.v1",
         "observed_at": timestamp.isoformat(),
         "health_domains": {"services_and_timers": "HEALTHY"},
         "mode": "OBSERVE"},
    )


def test_live_recurring_founder_refresh_and_service_health_create_exact_checkpoints(tmp_path):
    _fresh_recurring_fixture(tmp_path)
    result = run_completion_live_proof(
        tmp_path, now=NOW,
        http_get=lambda url: (0, ""),
        systemd_probe=lambda unit, mode: unit == "empire-department-cycle.timer",
    )
    assert result["pending_rule_match_count"] == 2
    assert result["live_proof_pass_count"] == 2
    assert result["live_proof_blocked_count"] == 0
    for row in result["results"]:
        assert row["passed"] is True
        packet = json.loads((tmp_path / row["checkpoint_ref"]).read_text())
        assert packet["checklist_lines"] == [row["line"]]
        assert packet["checklist_items"] == [row["item"]]
        assert packet["external_action_performed"] is False
        assert packet["synthetic_evidence_used"] is False
        assert packet["execution_authority"] == "none"
    assert not any("[x]" in line for line in (
        tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md"
    ).read_text().splitlines())


def test_stale_recurring_snapshots_do_not_generate_checkpoints(tmp_path):
    from datetime import timedelta
    _fresh_recurring_fixture(tmp_path, timestamp=NOW-timedelta(hours=1))
    result = run_completion_live_proof(
        tmp_path, now=NOW,
        http_get=lambda url: (0, ""),
        systemd_probe=lambda unit, mode: True,
    )
    assert result["pending_rule_match_count"] == 2
    assert result["live_proof_blocked_count"] == 2
    assert result["checkpoints_written"] == []


def test_future_dated_snapshot_fails_closed(tmp_path):
    from datetime import timedelta
    _fresh_recurring_fixture(tmp_path, timestamp=NOW+timedelta(hours=1))
    result = run_completion_live_proof(
        tmp_path, now=NOW,
        http_get=lambda url: (0, ""),
        systemd_probe=lambda unit, mode: True,
    )
    assert result["live_proof_pass_count"] == 0
    assert result["checkpoints_written"] == []


def test_failed_service_health_and_timer_are_independent_blockers(tmp_path):
    _fresh_recurring_fixture(tmp_path)
    ops = tmp_path / "runtime/ops_control/latest.json"
    data = json.loads(ops.read_text())
    data["health_domains"]["services_and_timers"] = "DEGRADED"
    _write(ops, data)
    result = run_completion_live_proof(
        tmp_path, now=NOW,
        http_get=lambda url: (0, ""),
        systemd_probe=lambda unit, mode: True,
    )
    assert result["live_proof_pass_count"] == 1
    assert result["live_proof_blocked_count"] == 1
    assert [r["item"] for r in result["results"] if r["passed"]] == [
        "Automatic Founder snapshot refresh",
    ]
    result2 = run_completion_live_proof(
        tmp_path, now=NOW,
        http_get=lambda url: (0, ""),
        systemd_probe=lambda unit, mode: False,
    )
    assert result2["live_proof_pass_count"] == 0
    assert result2["live_proof_blocked_count"] == 2


def test_duplicate_matching_checklist_item_names_are_not_auto_closed(tmp_path):
    _fresh_recurring_fixture(tmp_path)
    checklist = tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md"
    checklist.write_text(
        checklist.read_text() +
        "## Another department\n- [ ] Automatic Founder snapshot refresh\n"
    )
    result = run_completion_live_proof(
        tmp_path, now=NOW,
        http_get=lambda url: (0, ""),
        systemd_probe=lambda unit, mode: True,
    )
    assert result["pending_rule_match_count"] == 1
    assert [r["item"] for r in result["results"]] == ["Service/timer health"]
    assert result["live_proof_pass_count"] == 1


def test_wrong_schema_and_naive_date_never_pass_recurring_live_proof(tmp_path):
    _fresh_recurring_fixture(tmp_path)
    astra = tmp_path / "runtime/astra/executive_latest.json"
    data = json.loads(astra.read_text())
    data["schema_version"] = "unknown"
    data["generated_at"] = "2026-10-03T00:15:00"
    _write(astra, data)
    result = run_completion_live_proof(
        tmp_path, now=NOW,
        http_get=lambda url: (0, ""),
        systemd_probe=lambda unit, mode: True,
    )
    assert result["live_proof_pass_count"] == 1
    assert result["results"][0]["passed"] is False


def test_missing_recurring_proof_files_never_count_as_zero_or_pass(tmp_path):
    _fresh_recurring_fixture(tmp_path)
    (tmp_path / "runtime/ops_control/latest.json").unlink()
    result = run_completion_live_proof(
        tmp_path, now=NOW,
        http_get=lambda url: (0, ""),
        systemd_probe=lambda unit, mode: True,
    )
    assert result["live_proof_pass_count"] == 1
    assert result["live_proof_blocked_count"] == 1


def test_live_proof_revokes_earlier_auto_checkpoint_when_health_degrades(tmp_path):
    _fresh_recurring_fixture(tmp_path)
    successful = run_completion_live_proof(
        tmp_path, now=NOW,
        http_get=lambda url: (0, ""),
        systemd_probe=lambda unit, mode: True,
    )
    assert successful["live_proof_pass_count"] == 2
    for path in successful["checkpoints_written"]:
        assert (tmp_path / path).exists()
    failed = run_completion_live_proof(
        tmp_path, now=NOW,
        http_get=lambda url: (0, ""),
        systemd_probe=lambda unit, mode: False,
    )
    assert failed["live_proof_pass_count"] == 0
    assert len(failed["checkpoints_invalidated"]) == 2
    for path in successful["checkpoints_written"]:
        assert not (tmp_path / path).exists()
    assert "[ ]" in (
        tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md"
    ).read_text()


def test_duplicate_title_invalidates_an_earlier_valid_checkpoint(tmp_path):
    _fresh_recurring_fixture(tmp_path)
    first = run_completion_live_proof(
        tmp_path, now=NOW,
        http_get=lambda url: (0, ""),
        systemd_probe=lambda unit, mode: True,
    )
    assert first["live_proof_pass_count"] == 2
    title_path = next(
        tmp_path / row["checkpoint_ref"] for row in first["results"]
        if row["item"] == "Automatic Founder snapshot refresh"
    )
    checklist = tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md"
    checklist.write_text(
        checklist.read_text() +
        "## Duplicate\n- [ ] Automatic Founder snapshot refresh\n"
    )
    updated = run_completion_live_proof(
        tmp_path, now=NOW,
        http_get=lambda url: (0, ""),
        systemd_probe=lambda unit, mode: True,
    )
    assert updated["pending_rule_match_count"] == 1
    assert not title_path.exists()
    assert str(title_path.relative_to(tmp_path)) in updated["checkpoints_invalidated"]


def _competitor_sweep_fixture(root: Path, *, timestamp=NOW) -> None:
    _write(
        root / "docs/MASTER_REMAINING_CHECKLIST.md",
        "# Demo\n## Automate recurring intelligence\n"
        "- [ ] Scheduled competitor sweeps\n",
    )
    for filename, schema, metric, count in (
        ("competitor_audience_latest.json",
         "empire.competitor_audience_runtime.v1", "competitor_count", 9),
        ("competitor_account_research_latest.json",
         "empire.competitor_account_research_batch.v1", "observation_count", 21),
        ("competitor_account_briefs_latest.json",
         "empire.account_intelligence_brief_batch.v1", "brief_count", 2),
    ):
        _write(
            root / "runtime/competitive_intelligence" / filename,
            {"schema_version": schema, "generated_at": timestamp.isoformat(),
             "mode": "OBSERVE", "execution_authority": "none", metric: count},
        )


def test_competitor_sweep_live_rule_requires_fresh_full_chain(tmp_path):
    _competitor_sweep_fixture(tmp_path)
    result = run_completion_live_proof(
        tmp_path, now=NOW, http_get=lambda url: (0, ""),
        systemd_probe=lambda unit, mode: unit == "empire-opportunity-brief.timer",
    )
    assert result["configured_rule_count"] == 7
    assert result["pending_rule_match_count"] == 1
    assert result["live_proof_pass_count"] == 1
    row, = result["results"]
    assert row["item"] == "Scheduled competitor sweeps"
    assert all(p["passed"] is True for p in row["probes"])
    packet = json.loads((tmp_path / row["checkpoint_ref"]).read_text())
    assert packet["checklist_lines"] == [3]
    assert packet["external_action_performed"] is False
    assert packet["execution_authority"] == "none"
    assert "- [ ] Scheduled competitor sweeps" in (
        tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md"
    ).read_text()


def test_competitor_sweep_rule_revokes_on_stale_source(tmp_path):
    from datetime import timedelta
    _competitor_sweep_fixture(tmp_path)
    good = run_completion_live_proof(
        tmp_path, now=NOW, http_get=lambda _: (0, ""),
        systemd_probe=lambda unit, mode: True,
    )
    assert good["live_proof_pass_count"] == 1
    changed = tmp_path / "runtime/competitive_intelligence/competitor_account_research_latest.json"
    data = json.loads(changed.read_text())
    data["generated_at"] = (NOW - timedelta(minutes=90)).isoformat()
    _write(changed, data)
    stale = run_completion_live_proof(
        tmp_path, now=NOW, http_get=lambda _: (0, ""),
        systemd_probe=lambda unit, mode: True,
    )
    assert stale["live_proof_pass_count"] == 0
    assert stale["live_proof_blocked_count"] == 1
    assert len(stale["checkpoints_invalidated"]) == 1
    assert not (tmp_path / good["checkpoints_written"][0]).exists()


def test_competitor_sweep_rule_rejects_missing_malformed_and_zero_evidence(tmp_path):
    _competitor_sweep_fixture(tmp_path)
    rel = "runtime/competitive_intelligence/competitor_account_briefs_latest.json"
    path = tmp_path / rel
    original = json.loads(path.read_text())
    for invalid in (0, True, "2", None, -1):
        current = dict(original, brief_count=invalid)
        _write(path, current)
        result = run_completion_live_proof(
            tmp_path, now=NOW, http_get=lambda _: (0, ""),
            systemd_probe=lambda unit, mode: True,
        )
        assert result["live_proof_pass_count"] == 0
        assert result["checkpoints_written"] == []
    path.unlink()
    missing = run_completion_live_proof(
        tmp_path, now=NOW, http_get=lambda _: (0, ""),
        systemd_probe=lambda unit, mode: True,
    )
    assert missing["live_proof_pass_count"] == 0


def test_competitor_sweep_rule_requires_enabled_and_active_timer(tmp_path):
    _competitor_sweep_fixture(tmp_path)
    for good_mode in ("active", "enabled"):
        result = run_completion_live_proof(
            tmp_path, now=NOW, http_get=lambda _: (0, ""),
            systemd_probe=lambda unit, mode: mode == good_mode,
        )
        assert result["live_proof_pass_count"] == 0
        assert result["live_proof_blocked_count"] == 1
