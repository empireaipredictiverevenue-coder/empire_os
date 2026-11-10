from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.chief_of_staff_continuity import SCHEMA, build_continuity_review, run_tick

NOW = datetime(2026, 11, 10, 20, 50, tzinfo=timezone.utc)
FIRST = "directive_" + "a" * 32
SECOND = "directive_" + "b" * 32
THIRD = "directive_" + "c" * 32


def source(root, rows=None, *, index_age=timedelta(hours=1), executive_age=timedelta(minutes=1)):
    ddir = root / "runtime/founder_directives"
    edir = root / "runtime/astra"
    ddir.mkdir(parents=True, exist_ok=True)
    edir.mkdir(parents=True, exist_ok=True)
    rows = rows if rows is not None else [
        {"id": FIRST, "title": "Restore first sale execution", "status": "implementation_failed",
         "priority": 95, "category": "revenue", "authority": "internal_plan"},
        {"id": SECOND, "title": "Prepare founder gated action", "status": "founder_gate",
         "priority": 90, "category": "revenue", "authority": "founder_gate"},
        {"id": THIRD, "title": "Already implemented", "status": "implemented",
         "priority": 50, "category": "search", "authority": "internal_plan"},
    ]
    index = {
        "schema_version": "empire.founder_directives.v1",
        "execution_mode": "OBSERVE",
        "automatic_production_execution": False,
        "observed_at": (NOW - index_age).isoformat(),
        "directive_count": len(rows),
        "latest": rows,
    }
    (ddir / "latest.json").write_text(json.dumps(index))
    generated = NOW - executive_age
    executive = {
        "schema_version": "empire.astra.executive.v2", "mode": "OBSERVE",
        "generated_at": generated.isoformat(),
        "executive_commercial_roles": {
            "schema_version": "empire.executive.commercial_observer.v1",
            "mode": "OBSERVE", "as_of": generated.isoformat(),
            "execution_authority": "none", "outbound_enabled": False,
            "production_changes": False,
            "observed_systemd": {"department_cycle": "SUCCEEDED", "astra_dispatcher": "SUCCEEDED"},
            "opportunity_proof": {"status": "FRESH"},
            "founder_mailbox_observer": {"status": "HEALTHY"},
            "existing_relationship_registry": {"status": "OBSERVE_REVIEW",
                                                "total_relationships": 0,
                                                "suppression_review_count": 0,
                                                "mailbox_current": False},
            "review": {"coo": {"tasks": []},
                       "chief_of_staff": {"top_three_next_actions": []}},
        },
    }
    (edir / "executive_latest.json").write_text(json.dumps(executive))
    return ddir / "latest.json", edir / "executive_latest.json"


def research_source(root, *, findings=0, degraded=15, age=timedelta(minutes=2),
                    corrupt=False, mismatch=False):
    directory = root / "runtime/opportunity_radar"
    directory.mkdir(parents=True, exist_ok=True)
    finished = NOW - age
    started = finished - timedelta(minutes=2)
    step_names = (
        "opportunity_radar", "opportunity_research", "opportunity_evidence_normalizer",
        "opportunity_factory_intake", "opportunity_quant_review",
        "opportunity_value_scoring", "opportunity_evidence_router",
        "opportunity_ai_planner",
    )
    loop = {
        "schema_version": "empire.predictive_cloud.opportunity_loop.v2",
        "mode": "OBSERVE", "execution_authority": "none",
        "automatic_external_execution_allowed": False,
        "ok": True, "finished_at": finished.isoformat(),
        "steps": [{"step": name, "ok": True} for name in step_names],
        "radar_candidate_count": 22, "research_observation_count": findings,
        "research_new_observation_count": findings,
        "research_degraded_query_count": degraded,
    }
    research = {
        "schema_version": "empire.opportunity_research_batch.v2",
        "mode": "OBSERVE", "execution_authority": "none",
        "outreach_enabled": False, "generated_at": started.isoformat(),
        "observation_count": findings + (1 if mismatch else 0),
        "new_observation_count": findings,
    }
    if corrupt:
        loop["execution_authority"] = "production"
    (directory / "loop_latest.json").write_text(json.dumps(loop))
    (directory / "research_latest.json").write_text(json.dumps(research))


@pytest.mark.parametrize("findings,degraded,expected", [
    (0, 15, "SEARCH_PROVIDER_DEGRADED_NO_RESULTS"),
    (0, 0, "RESEARCH_LOOP_COMPLETE_ZERO_RESULTS"),
    (3, 15, "RESEARCH_SOURCE_REVIEW_REQUIRED"),
])
def test_owned_opportunity_research_handoff_never_dispatches_browser(tmp_path, findings, degraded, expected):
    source(tmp_path)
    research_source(tmp_path, findings=findings, degraded=degraded)
    output = build_continuity_review(tmp_path, as_of=NOW)
    status = output["research_execution"]
    assert status["status"] == expected
    assert status["loop_completed"] is True
    assert status["candidate_count"] == 22
    assert status["new_observation_count"] == findings
    assert status["degraded_query_count"] == degraded
    assert status["browser_dispatched"] is False
    assert status["commercial_authority"] == "none"
    if findings == 0:
        assert status["browser_handoff"] == "HELD_NO_VALIDATED_PUBLIC_SOURCE"
    else:
        assert status["browser_handoff"] == "ORIGINAL_OWNER_VERIFY_SOURCE_URLS_FIRST"


@pytest.mark.parametrize("case,expected", [
    ("stale", "RESEARCH_RECEIPT_STALE_OR_INCONSISTENT"),
    ("tampered", "NO_VERIFIED_RESEARCH_RECEIPT"),
    ("mismatch", "RESEARCH_COUNTERS_UNVERIFIED"),
])
def test_research_handoff_rejects_stale_tampered_and_contradictory_receipts(tmp_path, case, expected):
    source(tmp_path)
    research_source(tmp_path, age=timedelta(hours=3) if case == "stale" else timedelta(minutes=2),
                    corrupt=case == "tampered", mismatch=case == "mismatch")
    output = build_continuity_review(tmp_path, as_of=NOW)
    assert output["research_execution"]["status"] == expected
    assert output["research_execution"]["browser_dispatched"] is False


def test_missing_research_has_no_browser_handoff(tmp_path):
    source(tmp_path)
    output = build_continuity_review(tmp_path, as_of=NOW)
    assert output["research_execution"]["status"] == "NO_VERIFIED_RESEARCH_RECEIPT"


def test_reuses_canonical_evidence_and_respects_approval_and_completion(tmp_path):
    source(tmp_path)
    report = build_continuity_review(tmp_path, as_of=NOW)
    assert report["schema_version"] == SCHEMA
    assert report["status"] == "REVIEW_ONLY"
    assert report["active_count_in_latest_window"] == 2
    assert [r["directive_id"] for r in report["top_three_follow_ups"]] == [FIRST, SECOND]
    assert report["top_three_follow_ups"][1]["next_action"] == "REVIEW_RECORDED_FOUNDER_GATE"
    assert all(r["owner"] == "EXISTING_OWNER_TO_VERIFY" for r in report["top_three_follow_ups"])
    assert all(r["dispatchable"] is False for r in report["top_three_follow_ups"])
    assert report["change_basis"] == "BASELINE_ONLY"
    assert report["changed_attention"] == []
    assert report["execution_authority"] == "none"
    assert report["notifications_sent"] is False
    assert report["revenue_verified_by_this_review"] is False


def test_proactive_change_is_deduplicated(tmp_path):
    index, _ = source(tmp_path)
    baseline = build_continuity_review(tmp_path, as_of=NOW)
    same = build_continuity_review(tmp_path, as_of=NOW, previous=baseline)
    assert same["change_basis"] == "VERIFIED_PRIOR_REPORT"
    assert same["changed_attention"] == []
    data = json.loads(index.read_text())
    data["latest"][0]["status"] = "verification_failed"
    index.write_text(json.dumps(data))
    changed = build_continuity_review(tmp_path, as_of=NOW, previous=baseline)
    assert [(r["directive_id"], r["previous_status"]) for r in changed["changed_attention"]] == [
        (FIRST, "implementation_failed")
    ]
    assert build_continuity_review(tmp_path, as_of=NOW, previous=changed)["changed_attention"] == []


@pytest.mark.parametrize("corruption", ["invalid_json", "wrong_mode", "execution_on", "ancient", "duplicate", "wrong_authority"])
def test_canonical_input_fails_closed(tmp_path, corruption):
    index, _ = source(tmp_path)
    data = json.loads(index.read_text())
    if corruption == "invalid_json":
        index.write_text("{")
    else:
        if corruption == "wrong_mode":
            data["execution_mode"] = "LIVE"
        elif corruption == "execution_on":
            data["automatic_production_execution"] = True
        elif corruption == "ancient":
            data["observed_at"] = (NOW - timedelta(days=366)).isoformat()
        elif corruption == "duplicate":
            data["latest"].append(dict(data["latest"][0]))
            data["directive_count"] += 1
        elif corruption == "wrong_authority":
            data["latest"][1]["authority"] = "internal_plan"
        index.write_text(json.dumps(data))
    result = build_continuity_review(tmp_path, as_of=NOW)
    assert result["status"] == "EVIDENCE_HOLD"
    assert result["top_three_follow_ups"] == []
    assert result["changed_attention"] == []


def test_old_persisted_directives_continue_without_claiming_freshness(tmp_path):
    source(tmp_path, index_age=timedelta(days=4))
    report = build_continuity_review(tmp_path, as_of=NOW)
    assert report["directive_evidence"] == "PERSISTED_INDEX_REVIEW"
    assert report["status"] == "REVIEW_WITH_PERSISTED_DIRECTIVES"
    assert report["active_count_in_latest_window"] == 2
    assert report["changed_attention"] == []
    tick = run_tick(tmp_path, as_of=NOW)
    assert tick["status"] == "REVIEW_WITH_PERSISTED_DIRECTIVES"
    assert (tmp_path / "runtime/chief_of_staff/continuity_latest.json").is_file()
    assert run_tick(tmp_path, as_of=NOW)["changed_attention"] == []


def test_astora_stale_holds_all_followup_and_deltas(tmp_path):
    source(tmp_path, executive_age=timedelta(minutes=45))
    report = build_continuity_review(tmp_path, as_of=NOW)
    assert report["status"] == "EVIDENCE_HOLD"
    assert report["top_three_follow_ups"] == []
    assert report["changed_attention"] == []


def test_corrupt_prior_does_not_create_alert_burst(tmp_path):
    source(tmp_path)
    prior = {"schema_version": SCHEMA, "mode": "LIVE", "observed_states": {}}
    report = build_continuity_review(tmp_path, as_of=NOW, previous=prior)
    assert report["status"] == "REVIEW_ONLY"
    assert report["change_basis"] == "PRIOR_UNTRUSTED"
    assert report["changed_attention"] == []


def test_persistent_autonomous_tick_survives_restart_without_repeat(tmp_path):
    index, _ = source(tmp_path)
    first = run_tick(tmp_path, as_of=NOW)
    checkpoint = tmp_path / "runtime/chief_of_staff/continuity_latest.json"
    assert checkpoint.is_file()
    assert checkpoint.stat().st_mode & 0o077 == 0
    assert first["change_basis"] == "BASELINE_ONLY"
    second = run_tick(tmp_path, as_of=NOW)
    assert second["change_basis"] == "VERIFIED_PRIOR_REPORT"
    assert second["changed_attention"] == []
    raw = json.loads(index.read_text())
    raw["latest"][0]["status"] = "verification_failed"
    index.write_text(json.dumps(raw))
    third = run_tick(tmp_path, as_of=NOW)
    assert len(third["changed_attention"]) == 1
    assert run_tick(tmp_path, as_of=NOW)["changed_attention"] == []
    assert json.loads(checkpoint.read_text())["schema_version"] == SCHEMA


def test_tick_holds_without_erasing_last_known_observation(tmp_path):
    index, _ = source(tmp_path)
    run_tick(tmp_path, as_of=NOW)
    checkpoint = tmp_path / "runtime/chief_of_staff/continuity_latest.json"
    last = checkpoint.read_bytes()
    index.write_text("corrupt")
    assert run_tick(tmp_path, as_of=NOW)["status"] == "EVIDENCE_HOLD"
    assert checkpoint.read_bytes() == last


def test_checkpoint_symlink_refused(tmp_path):
    source(tmp_path)
    checkpoint_dir = tmp_path / "runtime/chief_of_staff"
    checkpoint_dir.mkdir()
    (checkpoint_dir / "continuity_latest.json").symlink_to(
        tmp_path / "runtime/founder_directives/latest.json"
    )
    with pytest.raises(ValueError, match="symlink"):
        run_tick(tmp_path, as_of=NOW)


def test_naive_clock_rejected(tmp_path):
    with pytest.raises(ValueError, match="timezone"):
        build_continuity_review(tmp_path, as_of=NOW.replace(tzinfo=None))


def test_symlinked_snapshot_is_untrusted(tmp_path):
    _, exec_path = source(tmp_path)
    dpath = tmp_path / "runtime/founder_directives/latest.json"
    dpath.unlink()
    dpath.symlink_to(exec_path)
    assert build_continuity_review(tmp_path, as_of=NOW)["status"] == "EVIDENCE_HOLD"
