from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.business_optimization_automation import (
    enqueue_optimization_request,
    run_business_optimization_cycle,
)


NOW = datetime(2026, 10, 2, 22, 30, tzinfo=timezone.utc)


def _request(request_id="req-1", value=100):
    return {
        "request_id": request_id,
        "workload_type": "marketing_budgets",
        "tenant_id": "tenant-a",
        "options": [
            {
                "option_key": "search",
                "entity_key": "search",
                "objective_value": value,
                "resource_usage": {"marketing_budget": 50},
                "evidence_refs": ["evidence:search"],
            },
            {
                "option_key": "content",
                "entity_key": "content",
                "objective_value": 80,
                "resource_usage": {"marketing_budget": 50},
                "evidence_refs": ["evidence:content"],
            },
        ],
        "resource_limits": {"marketing_budget": {"max": 50}},
        "time_budget_ms": 1000,
    }


def _write(root: Path, name: str, payload) -> Path:
    path = root / "runtime/business_optimization/inbox" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_cycle_claims_processes_and_archives_request(tmp_path):
    _write(tmp_path, "one.json", _request())

    cycle = run_business_optimization_cycle(tmp_path, now=NOW)

    assert cycle["status"] == "AVAILABLE"
    assert cycle["claimed_request_count"] == 1
    assert cycle["processed_request_count"] == 1
    assert cycle["queued_request_count_remaining"] == 0
    assert cycle["processing_request_count_remaining"] == 0
    assert cycle["queue_semantics"]["atomic_claim"] is True
    assert cycle["queue_semantics"]["processed_events_archived"] is True
    assert cycle["automatic_business_action_allowed"] is False
    assert cycle["third_party_service_called"] is False
    assert not list(
        (tmp_path / "runtime/business_optimization/inbox").glob("*.json")
    )
    archived = list(
        (
            tmp_path
            / "runtime/business_optimization/archive/2026/10/02"
        ).glob("*.json")
    )
    assert len(archived) == 1


def test_duplicate_event_is_idempotent_but_does_not_starve_new_work(tmp_path):
    _write(tmp_path, "one.json", _request("same"))
    first = run_business_optimization_cycle(tmp_path, max_requests=1, now=NOW)
    assert first["recomputed_request_count"] == 1

    _write(tmp_path, "duplicate.json", _request("same"))
    _write(tmp_path, "new.json", _request("new", value=120))

    second = run_business_optimization_cycle(
        tmp_path,
        max_requests=1,
        now=NOW,
    )
    assert second["unchanged_request_count"] == 1
    assert second["queued_request_count_remaining"] == 1

    third = run_business_optimization_cycle(
        tmp_path,
        max_requests=1,
        now=NOW,
    )
    assert third["recomputed_request_count"] == 1
    assert third["queued_request_count_remaining"] == 0


def test_cycle_recovers_processing_file_after_interrupted_prior_cycle(tmp_path):
    processing = (
        tmp_path / "runtime/business_optimization/processing"
    )
    processing.mkdir(parents=True, exist_ok=True)
    (processing / "stuck.json").write_text(
        json.dumps(_request("recovered")),
        encoding="utf-8",
    )

    cycle = run_business_optimization_cycle(tmp_path, now=NOW)

    assert cycle["recovered_processing_count"] == 1
    assert cycle["processed_request_count"] == 1
    assert cycle["processing_request_count_remaining"] == 0


def test_invalid_json_is_quarantined_and_does_not_poison_cycle(tmp_path):
    _write(tmp_path, "bad.json", "{not-json")

    cycle = run_business_optimization_cycle(tmp_path, now=NOW)

    assert cycle["status"] == "AVAILABLE"
    assert cycle["invalid_request_file_count"] == 1
    assert cycle["processed_request_count"] == 0
    invalid = list(
        (
            tmp_path
            / "runtime/business_optimization/invalid/2026/10/02"
        ).glob("*.json")
    )
    assert len(invalid) == 1


def test_cycle_is_bounded_and_leaves_excess_events_for_next_heartbeat(tmp_path):
    for index in range(3):
        _write(
            tmp_path,
            f"{index}.json",
            _request(f"req-{index}", value=100 + index),
        )

    cycle = run_business_optimization_cycle(
        tmp_path,
        max_requests=2,
        now=NOW,
    )

    assert cycle["claimed_request_count"] == 2
    assert cycle["processed_request_count"] == 2
    assert cycle["queued_request_count_remaining"] == 1

def test_internal_evidence_event_can_enqueue_without_granting_action_authority(
    tmp_path,
):
    queued = enqueue_optimization_request(
        tmp_path,
        _request("event-driven"),
        event_ref="predictive_cloud:forecast:42",
        observed_at="2026-10-02T22:30:00+00:00",
    )

    assert queued["status"] == "QUEUED"
    assert queued["enqueued"] is True
    assert queued["automatic_business_action_allowed"] is False
    assert queued["third_party_service_called"] is False
    assert queued["execution_authority"] == "none"
    assert (tmp_path / queued["queue_ref"]).exists()

    cycle = run_business_optimization_cycle(tmp_path, now=NOW)

    assert cycle["processed_request_count"] == 1
    assert cycle["queued_request_count_remaining"] == 0
    assert cycle["automatic_business_action_allowed"] is False


def test_repeated_benchmarks_refresh_solver_memory_without_routing_change(tmp_path):
    for index, value in enumerate((100, 110, 120)):
        queued = enqueue_optimization_request(
            tmp_path,
            _request(f"learn-{index}", value=value),
            event_ref=f"evidence:learn:{index}",
            observed_at=f"2026-10-02T22:3{index}:00+00:00",
        )
        assert queued["status"] == "QUEUED"
        cycle = run_business_optimization_cycle(tmp_path, now=NOW)
        assert cycle["processed_request_count"] == 1

    memory_path = (
        tmp_path
        / "runtime/business_optimization/solver_performance_memory_latest.json"
    )
    recommendation_path = (
        tmp_path
        / "runtime/business_optimization/solver_recommendation_latest.json"
    )
    memory = json.loads(memory_path.read_text())
    recommendation = json.loads(recommendation_path.read_text())

    assert memory["status"] == "AVAILABLE"
    assert memory["profile_count"] >= 1
    assert memory["automatic_production_routing_changed"] is False
    assert memory["quantum_advantage_claimed"] is False
    assert recommendation["automatic_production_routing_changed"] is False
    assert recommendation["production_promotion_ready"] is False
    assert recommendation["execution_authority"] == "none"
