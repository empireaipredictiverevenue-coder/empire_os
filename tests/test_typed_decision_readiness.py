import pytest
from empire_os.typed_decision_readiness import (
    build_readiness_board,
    next_evidence_actions,
    review_task_readiness,
)


def task(task_key="reply_classification",n=150):
    return {
        "task_key":task_key,
        "real_labeled_case_count":n,
        "provider_output_count":n,
        "shadow_record_count":n,
        "independent_review_count":2,
        "calibration_observed":True,
        "fallback_tested":True,
        "drift_monitor_defined":True,
        "schema_failure_measured":True,
        "synthetic_cases_present":False,
        "minimum_real_labels":100,
        "minimum_provider_outputs":100,
        "minimum_shadow_records":100,
    }


def test_task_ready_does_not_enable_provider_or_production():
    r=review_task_readiness(task())
    assert r["promotion_review_ready"] is True
    assert r["provider_selected"] is False
    assert r["production_routing_enabled"] is False


def test_missing_real_evidence_blocks_promotion():
    r=review_task_readiness(task(n=10))
    assert r["promotion_review_ready"] is False
    assert "insufficient_real_labels" in r["blockers"]
    assert "insufficient_provider_outputs" in r["blockers"]
    assert "insufficient_shadow_records" in r["blockers"]


def test_synthetic_cases_block_even_when_counts_are_high():
    row=task()
    row["synthetic_cases_present"]=True
    r=review_task_readiness(row)
    assert r["promotion_review_ready"] is False
    assert "synthetic_cases_present" in r["blockers"]


def test_board_requires_all_core_tasks():
    board=build_readiness_board([task()])
    assert board["all_core_tasks_ready"] is False
    assert "keyword_intent" in board["missing_tasks"]


def test_next_actions_are_advisory_only():
    board=build_readiness_board([task(n=10)])
    actions=next_evidence_actions(board)
    assert actions["automatic_execution"] is False
    assert any(a["action"]=="collect_and_review_real_labels" for a in actions["actions"])


def test_duplicate_task_rejected():
    with pytest.raises(ValueError,match="duplicate"):
        build_readiness_board([task(),task()])
