"""Blocked source-mining queue work gets real bounded scientific desk triage."""
from copy import deepcopy
from pathlib import Path
import json
import pytest

from empire_os.department_work_queue import DepartmentWorkQueue
from empire_os.department_worker import run_one_department_work
from empire_os.public_source_sweep import (
    review_public_source_sweep, enqueue_deep_source_reviews,
)
from empire_os.revenue_stream_mining import (
    build_revenue_stream_mining, enqueue_existing_department_mining,
)
from empire_os.source_mining_specialist_adapter import (
    complete_source_mining_desk_review, SpecialistEvidenceHold,
)
from test_revenue_stream_mining import fixture_sources


def test_real_mining_department_queue_performs_bounded_desk_triage(tmp_path):
    fixture_sources(tmp_path)
    report = build_revenue_stream_mining(tmp_path)
    queued = enqueue_existing_department_mining(
        tmp_path, report, allow_noncanonical_test=True,
    )
    assert queued["jobs_new"] == 4
    outputs = [run_one_department_work(tmp_path) for _ in range(4)]
    assert all(item["state"] == "DONE" for item in outputs), outputs
    assert all(item["internal_desk_triage_completed"] is True for item in outputs)
    assert all(item["independent_source_research_completed"] is False for item in outputs)
    assert all(item["paid_model_invoked"] is False for item in outputs)
    assert all(item["outbound_sent"] is False for item in outputs)
    done = list((tmp_path/"runtime/departments/work/done").glob("*.json"))
    assert len(done) == 4
    for p in done:
        x = json.loads(p.read_text())
        result = x["result"]
        assert result["status"] == "INTERNAL_SOURCE_DESK_TRIAGE_COMPLETED"
        assert result["qualified_buyer_proven"] is False
        assert result["prediction_calibrated"] is False
        assert result["revenue_verified"] is False
        assert result["independent_source_research_completed"] is False
        assert len(result["scientific_controls_required"]) == 7
        for forbidden in (
            "buyer-secret@example.com", "private.person@example.com",
            "secret-content",
        ):
            assert forbidden not in json.dumps(x)
    assert DepartmentWorkQueue(tmp_path).counts()["blocked"] == 0


def test_stale_source_job_is_held_not_misreported_as_complete(tmp_path):
    fixture_sources(tmp_path)
    report = build_revenue_stream_mining(tmp_path)
    queued = enqueue_existing_department_mining(
        tmp_path, report, allow_noncanonical_test=True,
    )
    assert queued["jobs_new"] == 4
    # Mutate a queued source packet rather than pretending current evidence
    # still equals the original source research request.
    queue = DepartmentWorkQueue(tmp_path)
    target = tmp_path/"runtime/departments/work/ready"
    for path in target.glob("*.json"):
        data = json.loads(path.read_text())
        if data["intelligence_request"].get("stream_mining_review", {}).get("lane") == "commercial_opportunity":
            data["intelligence_request"]["stream_mining_review"]["evidence_fingerprint"] = "f"*64
            path.write_text(json.dumps(data))
    outputs = [run_one_department_work(tmp_path) for _ in range(4)]
    assert sum(o["state"] == "BLOCKED" for o in outputs) == 1
    assert sum(o["state"] == "DONE" for o in outputs) == 3
    blocked = list((tmp_path/"runtime/departments/work/blocked").glob("*.json"))
    assert len(blocked) == 1
    stored = json.loads(blocked[0].read_text())
    assert stored["error"] == "source_mining_snapshot_or_contract_hold"
    assert stored["result"]["paid_model_invoked"] is False


def test_two_existing_official_sweep_reviews_use_same_worker(tmp_path):
    reports = review_public_source_sweep()
    queued = enqueue_deep_source_reviews(
        str(tmp_path), reports, allow_noncanonical_test=True,
    )
    assert queued["new_review_tasks"] == 2
    outputs = [run_one_department_work(tmp_path) for _ in range(2)]
    assert [o["state"] for o in outputs] == ["DONE", "DONE"]
    for p in (tmp_path/"runtime/departments/work/done").glob("*.json"):
        item = json.loads(p.read_text())
        result = item["result"]
        assert result["status"] == "INTERNAL_SOURCE_READINESS_TRIAGE_COMPLETED"
        assert result["independent_live_source_verification_completed"] is False
        assert result["commercial_buyer_or_revenue_proven"] is False
        assert result["source_polling_activated"] is False
        assert result["external_execution_performed"] is False
        assert len(result["source_inventory"]) == 2


@pytest.mark.parametrize("tamper", [
    ("authority", "external"),
    ("department_keys", ["finance"]),
    ("tenant_id", "private-tenant"),
])
def test_source_compatibility_adapter_refuses_unsafe_authority(tmp_path,tamper):
    fixture_sources(tmp_path)
    review = build_revenue_stream_mining(tmp_path)
    enqueue_existing_department_mining(tmp_path, review, allow_noncanonical_test=True)
    path = next((tmp_path/"runtime/departments/work/ready").glob("*.json"))
    item = json.loads(path.read_text())
    item[tamper[0]] = tamper[1]
    from empire_os.department_work_queue import DepartmentWorkItem
    with pytest.raises(SpecialistEvidenceHold):
        complete_source_mining_desk_review(tmp_path, DepartmentWorkItem(**item))


def test_source_growth_requeues_new_evidence_without_erasing_old_blocked_history(tmp_path):
    from hashlib import sha256
    from datetime import datetime, timezone
    from empire_os.revenue_stream_mining import SOURCES
    fixture_sources(tmp_path)
    first = build_revenue_stream_mining(tmp_path)
    original = enqueue_existing_department_mining(
        tmp_path, first, allow_noncanonical_test=True,
    )
    old_id = next(
        item["work_id"] for item in original["jobs"]
        if item["stream"] == "acquisition"
    )
    source_file = tmp_path/SOURCES["acquisition"][0]
    rows = json.loads(source_file.read_text())
    signal_id = sha256(b"new-real-source-receipt-in-test").hexdigest()
    timestamp = datetime.now(timezone.utc).isoformat()
    rows[signal_id] = {
        "signal_id": signal_id,
        "source": "permits_nyc",
        "seen_count": 1,
        "created_at": timestamp,
        "last_seen_at": timestamp,
        "execution_authority": "none",
    }
    source_file.write_text(json.dumps(rows))
    # Four previously queued desk tasks: one stale acquisition should HOLD,
    # three unaffected streams still produce an internal desk-review result.
    previous_runs = [run_one_department_work(tmp_path) for _ in range(4)]
    assert sum(x["state"] == "BLOCKED" for x in previous_runs) == 1
    assert (tmp_path/"runtime/departments/work/blocked"/(old_id+".json")).exists()
    refresh = build_revenue_stream_mining(tmp_path)
    assert refresh["sources"]["acquisition"]["aggregate"]["counts"]["signal_inventory"] == 3
    replay = enqueue_existing_department_mining(
        tmp_path, refresh, allow_noncanonical_test=True,
    )
    assert replay["jobs_new"] == 1
    assert replay["jobs_duplicate"] == 3
    new_id = next(
        item["work_id"] for item in replay["jobs"]
        if item["stream"] == "acquisition"
    )
    assert new_id != old_id
    latest = run_one_department_work(tmp_path)
    assert latest["state"] == "DONE"
    assert latest["work_id"] == new_id
    assert latest["independent_source_research_completed"] is False
    queue = DepartmentWorkQueue(tmp_path)
    assert queue.counts()["blocked"] == 1
    assert queue.counts()["done"] == 4
    assert run_one_department_work(tmp_path)["state"] == "IDLE"
