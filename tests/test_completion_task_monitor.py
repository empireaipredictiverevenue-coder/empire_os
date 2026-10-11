"""Task monitor: per-item stages and safe transitions in existing department cycle."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.completion_task_monitor import (
    MonitorEvidenceError, OUTPUT, RECONCILIATION, SCHEMA,
    build_completion_task_monitor, refresh_completion_task_monitor,
)
from empire_os.founder_execution_ledger_api import create_founder_execution_ledger_router
from empire_os.master_execution_ledger import LedgerItem, parse_checklist

NOW = datetime(2026, 10, 11, 19, 0, tzinfo=timezone.utc)
SENTENCE = "Obtain actual buyer-approved PPC call buy-box"
SECOND = "Implement consent-bound intake receipts in sovereign EmpireDB"
THIRD = "Founder approves production live go-live"
SECTION = "Sales & Revenue"


def sources(
    *, moment=NOW,
    tasks=(SENTENCE, SECOND, THIRD),
    stages=("BUILDER_PROVIDER_BLOCKED", "CODE_COMPLETE_NOT_LIVE", "FOUNDER_GATE"),
):
    from hashlib import sha256

    checklist = [
        LedgerItem(
            source="docs/MASTER_REMAINING_CHECKLIST.md",
            line=index + 3, section=SECTION, section_level=2,
            item=item, status="PENDING",
        ) for index, item in enumerate(tasks)
    ]
    items = []
    for row, state in zip(checklist, stages):
        item_id = "check_" + sha256(
            f"{row.line}|{row.section}|{row.item}".encode()
        ).hexdigest()[:16]
        items.append({
            "item_id": item_id, "state": state,
            "department": "sales_revenue", "checklist_line": row.line,
            "execution_class": (
                "founder_gate" if state == "FOUNDER_GATE" else "builder_required"
            ),
            "attempt_memory_state": (
                "PROVIDER_CAPACITY_BLOCKED" if state == "BUILDER_PROVIDER_BLOCKED"
                else "CODE_VERIFIED_NOT_LIVE" if state == "CODE_COMPLETE_NOT_LIVE"
                else None
            ),
            "attempt_memory_commit": (
                "fb8fa656" if state == "CODE_COMPLETE_NOT_LIVE" else None
            ),
            "attempt_memory_blocker": (
                "hermes_zero_cost_model_unavailable"
                if state == "BUILDER_PROVIDER_BLOCKED" else None
            ),
            "verification_job_id": None,
            "verification_verdict": None,
        })
    from collections import Counter
    recon = {
        "schema_version": "empire.completion_reconciliation.v1",
        "status": "AVAILABLE", "mode": "OBSERVE",
        "execution_authority": "none",
        "external_execution_performed": False,
        "automatic_checklist_mutation_allowed": False,
        "production_mutation": False,
        "verified_done_count": 0,
        "generated_at": moment.isoformat(),
        "canonical_pending_count": len(items),
        "canonical_done_count": 0,
        "canonical_total_count": len(items),
        "reconciled_item_count": len(items),
        "state_counts": dict(Counter(stages)),
        "items": items,
    }
    return checklist, recon


def test_first_monitor_is_baseline_not_three_new_completed_tasks():
    rows, source = sources()
    out = build_completion_task_monitor(rows, source, now=NOW)
    assert out["status"] == "AVAILABLE"
    assert out["schema_version"] == SCHEMA
    assert out["tracked_pending_count"] == 3
    assert out["checklist"] == {
        "pending": 3, "checked_done": 0, "total": 3,
        "checked_done_is_not_independent_production_proof": True,
    }
    assert out["state_counts"] == {
        "BUILDER_PROVIDER_BLOCKED": 1,
        "CODE_COMPLETE_NOT_LIVE": 1,
        "FOUNDER_GATE": 1,
    }
    assert out["attention_count"] == 3
    assert out["new_state_transition_count"] == 0
    assert out["recent_transitions"] == []
    assert out["first_observation_only_not_historical_task_age"] is True
    assert all(row["monitored_cycles"] == 1 for row in out["items"])
    assert all(row["state_age_seconds"] == 0 for row in out["items"])
    assert all(row["commercial_outcome_verified"] is False for row in out["items"])
    assert out["external_execution_performed"] is False
    assert out["notifications_sent"] is False
    assert out["execution_authority"] == "none"


def test_repeat_same_stage_does_not_raise_duplicate_transition():
    rows, recon = sources()
    first = build_completion_task_monitor(rows, recon, now=NOW)
    later = NOW + timedelta(minutes=5)
    _, recon2 = sources(moment=later)
    second = build_completion_task_monitor(rows, recon2, now=later, previous=first)
    assert second["new_state_transition_count"] == 0
    assert second["recent_transitions"] == []
    assert all(row["monitored_cycles"] == 2 for row in second["items"])
    assert all(row["state_age_seconds"] == 300 for row in second["items"])
    assert second["first_observation_only_not_historical_task_age"] is False


def test_stage_change_event_is_recorded_once_and_kept_without_repeat():
    rows, source = sources()
    prior = build_completion_task_monitor(rows, source, now=NOW)
    two = NOW + timedelta(minutes=10)
    _, new_recon = sources(
        moment=two,
        stages=("NEEDS_LIVE_PROOF", "CODE_COMPLETE_NOT_LIVE", "FOUNDER_GATE"),
    )
    changed = build_completion_task_monitor(rows, new_recon, previous=prior, now=two)
    assert changed["new_state_transition_count"] == 1
    assert changed["new_state_transitions"][0]["from_state"] == "BUILDER_PROVIDER_BLOCKED"
    assert changed["new_state_transitions"][0]["to_state"] == "NEEDS_LIVE_PROOF"
    assert changed["items"][0]["state_age_seconds"] == 0
    assert changed["items"][0]["first_monitored_at"] == NOW.isoformat()
    assert changed["items"][1]["state_age_seconds"] == 600
    three = two + timedelta(minutes=10)
    _, recon3 = sources(
        moment=three,
        stages=("NEEDS_LIVE_PROOF", "CODE_COMPLETE_NOT_LIVE", "FOUNDER_GATE"),
    )
    stable = build_completion_task_monitor(rows, recon3, now=three, previous=changed)
    assert stable["new_state_transition_count"] == 0
    assert len(stable["recent_transitions"]) == 1


def test_monitor_marks_24h_no_stage_change_not_deadline_breach():
    rows, source = sources()
    baseline = build_completion_task_monitor(rows, source, now=NOW)
    future = NOW + timedelta(hours=25)
    _, refreshed = sources(moment=future)
    observed = build_completion_task_monitor(rows, refreshed, previous=baseline, now=future)
    assert "NO_OBSERVED_STAGE_CHANGE_24H" in observed["items"][1]["signals"]
    assert observed["items"][1]["state_age_seconds"] == 25 * 3600
    assert observed["new_state_transition_count"] == 0
    assert observed["execution_authority"] == "none"


def test_checked_done_is_only_checklist_truth_not_live_completion():
    rows, recon = sources()
    previous = build_completion_task_monitor(rows, recon, now=NOW)
    done = LedgerItem(**{**rows[0].__dict__, "status": "DONE"})
    remaining_rows = [done, *rows[1:]]
    moment = NOW + timedelta(minutes=8)
    _, narrowed = sources(moment=moment, tasks=(SECOND, THIRD),
                          stages=("CODE_COMPLETE_NOT_LIVE", "FOUNDER_GATE"))
    # Re-bind line numbers to actual unchanged canonical rows.
    narrowed["items"][0]["item_id"] = recon["items"][1]["item_id"]
    narrowed["items"][0]["checklist_line"] = rows[1].line
    narrowed["items"][1]["item_id"] = recon["items"][2]["item_id"]
    narrowed["items"][1]["checklist_line"] = rows[2].line
    narrowed["canonical_total_count"] = 3
    narrowed["canonical_done_count"] = 1
    result = build_completion_task_monitor(
        remaining_rows, narrowed, previous=previous, now=moment,
    )
    assert result["tracked_pending_count"] == 2
    assert result["checklist"]["checked_done"] == 1
    assert result["checklist"]["checked_done_is_not_independent_production_proof"]
    assert result["new_state_transitions"][0]["to_state"] == "CHECKLIST_MARKED_DONE"


def test_removed_task_without_checked_done_is_not_silent_completion():
    rows, source = sources()
    previous = build_completion_task_monitor(rows, source, now=NOW)
    moment = NOW + timedelta(minutes=3)
    _, narrowed = sources(moment=moment, tasks=(SECOND, THIRD),
                          stages=("CODE_COMPLETE_NOT_LIVE", "FOUNDER_GATE"))
    narrowed["items"][0]["item_id"] = source["items"][1]["item_id"]
    narrowed["items"][0]["checklist_line"] = rows[1].line
    narrowed["items"][1]["item_id"] = source["items"][2]["item_id"]
    narrowed["items"][1]["checklist_line"] = rows[2].line
    with pytest.raises(MonitorEvidenceError, match="disappeared_without_done"):
        build_completion_task_monitor(rows[1:], narrowed, previous=previous, now=moment)


@pytest.mark.parametrize(("field", "value"), [
    ("mode", "EXECUTE"),
    ("status", "FAILED"),
    ("execution_authority", "send_mail"),
    ("external_execution_performed", True),
    ("automatic_checklist_mutation_allowed", True),
    ("production_mutation", True),
    ("verified_done_count", True),
    ("generated_at", "2026-10-10T19:00:00+00:00"),
    ("generated_at", "2026-10-11T19:30:00+00:00"),
    ("canonical_pending_count", 0),
    ("reconciled_item_count", 0),
    ("canonical_total_count", 50),
])
def test_missing_stale_or_dangerous_sources_fail_closed(field, value):
    rows, recon = sources()
    recon[field] = value
    with pytest.raises(MonitorEvidenceError):
        build_completion_task_monitor(rows, recon, now=NOW)


def test_duplicate_or_forged_item_identity_cannot_be_monitored():
    rows, recon = sources()
    recon["items"][1]["item_id"] = recon["items"][0]["item_id"]
    with pytest.raises(MonitorEvidenceError, match="identity"):
        build_completion_task_monitor(rows, recon, now=NOW)


def test_stage_count_conflict_rejected_without_fabricated_progress():
    rows, recon = sources()
    recon["state_counts"]["FOUNDER_GATE"] = 2
    with pytest.raises(MonitorEvidenceError, match="state_counts"):
        build_completion_task_monitor(rows, recon, now=NOW)


def test_corrupt_previous_monitored_state_stops_history_reset():
    rows, recon = sources()
    prev = build_completion_task_monitor(rows, recon, now=NOW)
    prev["items"][0]["state_since"] = "2030-01-01T00:00:00+00:00"
    later = NOW + timedelta(minutes=1)
    _, next_recon = sources(moment=later)
    with pytest.raises(MonitorEvidenceError, match="clock_conflict"):
        build_completion_task_monitor(rows, next_recon, now=later, previous=prev)


def test_refresh_writes_atomic_latest_and_leaves_canonical_sources_untouched(tmp_path):
    root = tmp_path
    checklist = root / "docs/MASTER_REMAINING_CHECKLIST.md"
    checklist.parent.mkdir(parents=True)
    checklist.write_text("# Master\n## Sales & Revenue\n- [ ] " + SENTENCE + "\n"
                         "- [ ] " + SECOND + "\n- [ ] " + THIRD + "\n")
    rows, recon = sources()
    target = root / RECONCILIATION
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(recon))
    source_before = (checklist.read_bytes(), target.read_bytes())
    result = refresh_completion_task_monitor(root, now=NOW)
    out = root / OUTPUT
    assert result["status"] == "AVAILABLE"
    assert out.exists()
    assert json.loads(out.read_text())["tracked_pending_count"] == 3
    assert (checklist.read_bytes(), target.read_bytes()) == source_before
    next_time = NOW + timedelta(minutes=4)
    _, update = sources(moment=next_time)
    target.write_text(json.dumps(update))
    again = refresh_completion_task_monitor(root, now=next_time)
    assert again["new_state_transition_count"] == 0
    assert again["items"][0]["monitored_cycles"] == 2


def test_stale_source_preserves_latest_valid_snapshot(tmp_path):
    checklist = tmp_path / "docs/MASTER_REMAINING_CHECKLIST.md"
    checklist.parent.mkdir(parents=True)
    checklist.write_text("# Master\n## Sales & Revenue\n- [ ] " + SENTENCE + "\n"
                         "- [ ] " + SECOND + "\n- [ ] " + THIRD + "\n")
    _, source = sources()
    path = tmp_path / RECONCILIATION
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(source))
    refresh_completion_task_monitor(tmp_path, now=NOW)
    saved = (tmp_path / OUTPUT).read_bytes()
    with pytest.raises(MonitorEvidenceError, match="stale"):
        refresh_completion_task_monitor(tmp_path, now=NOW+timedelta(hours=2))
    assert (tmp_path / OUTPUT).read_bytes() == saved


def test_existing_founder_endpoint_filters_and_returns_attention_only_snapshot(tmp_path):
    from empire_os.completion_task_monitor import build_completion_task_monitor
    rows, source = sources(moment=datetime.now(timezone.utc))
    snapshot = build_completion_task_monitor(
        rows, source, now=datetime.now(timezone.utc),
    )
    monitor = tmp_path / "monitor.json"
    monitor.write_text(json.dumps(snapshot))
    checklist = tmp_path / "checklist.md"
    checklist.write_text("# Example\n- [ ] Test\n")
    app = FastAPI()
    app.include_router(create_founder_execution_ledger_router(
        checklist_path=checklist,
        completion_progress_path=tmp_path/"missing_progress",
        capability_registry_path=tmp_path/"missing_registry",
        task_monitor_path=monitor,
    ))
    client = TestClient(app)
    path = "/v1/founder-execution-ledger/task-monitor"
    response = client.get(path)
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["tracked_pending_count"] == 3
    assert payload["attention_count"] == 3
    assert payload["read_only"] is True
    assert payload["execution_authority"] == "none"
    filtered = client.get(path, params={"state": "FOUNDER_GATE", "limit": 1}).json()
    assert filtered["matched_item_count"] == 1
    assert filtered["returned_item_count"] == 1
    assert filtered["items"][0]["state"] == "FOUNDER_GATE"


def test_stale_api_snapshot_hides_old_counts_instead_of_open_now_claim(tmp_path):
    old_time = datetime.now(timezone.utc) - timedelta(days=2)
    rows, recon = sources(moment=old_time)
    snapshot = build_completion_task_monitor(rows, recon, now=old_time)
    file = tmp_path / "monitor.json"
    file.write_text(json.dumps(snapshot))
    app = FastAPI()
    app.include_router(create_founder_execution_ledger_router(
        checklist_path=tmp_path/"missing",
        completion_progress_path=tmp_path/"missing",
        capability_registry_path=tmp_path/"missing",
        task_monitor_path=file,
    ))
    response = TestClient(app).get("/v1/founder-execution-ledger/task-monitor")
    body = response.json()
    assert body["available"] is False
    assert body["reason"] == "task_monitor_snapshot_stale_or_untrusted"
    assert "items" not in body



def test_local_monitor_cli_reads_only_latest_and_surfaces_attention(tmp_path):
    from scripts.task_monitor_status import inspect
    clock = datetime.now(timezone.utc)
    rows, recon = sources(moment=clock)
    snapshot = build_completion_task_monitor(rows, recon, now=clock)
    path = tmp_path / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot))
    before = path.read_bytes()
    report = inspect(tmp_path, now=clock + timedelta(minutes=2))
    assert report["status"] == "AVAILABLE"
    assert report["checklist"]["pending"] == 3
    assert report["attention_count"] == 3
    assert len(report["top_attention"]) == 3
    assert report["monitoring_not_dispatch"] is True
    assert report["execution_authority"] == "none"
    assert path.read_bytes() == before
    stale = inspect(tmp_path, now=clock + timedelta(hours=2))
    assert stale["status"] == "STALE_OR_UNTRUSTED"
    assert "top_attention" not in stale


def test_history_transitions_are_bounded_and_real_state_changes_only():
    rows, recon = sources()
    source = build_completion_task_monitor(rows, recon, now=NOW)
    for i in range(1, 65):
        stamp = NOW + timedelta(minutes=i * 2)
        states = (
            ("NEEDS_LIVE_PROOF", "CODE_COMPLETE_NOT_LIVE", "FOUNDER_GATE")
            if i % 2 else
            ("BUILDER_PROVIDER_BLOCKED", "CODE_COMPLETE_NOT_LIVE", "FOUNDER_GATE")
        )
        _, payload = sources(moment=stamp, stages=states)
        source = build_completion_task_monitor(
            rows, payload, previous=source, now=stamp,
        )
    assert source["new_state_transition_count"] == 1
    assert len(source["recent_transitions"]) == 64
    assert source["items"][0]["monitored_cycles"] == 65
    assert source["items"][1]["state_age_seconds"] == 128 * 60
