import json
from pathlib import Path

from empire_os.phase_3f_closeout import build_phase_3f_closeout


def write_json(root: Path, relative: str, value) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def seed_ready_closeout(root: Path) -> None:
    write_json(
        root,
        "runtime/astra/executive_latest.json",
        {"plan_id": "astra_plan_current"},
    )
    write_json(
        root,
        "runtime/astra/executive_evaluation_latest.json",
        {
            "plan_id": "astra_plan_current",
            "evaluation_state": "BLOCKED",
            "status_counts": {"DONE": 4, "BLOCKED": 4},
            "undispatched_step_ids": [],
        },
    )
    write_json(
        root,
        "runtime/predictive_intelligence/latest.json",
        {
            "prediction_only": True,
            "llm_probability_used": False,
            "search_scores_used": False,
            "source_outcome_count": 0,
            "probability_ready_product_count": 0,
            "timing_ready_product_count": 0,
        },
    )
    write_json(
        root,
        "runtime/economic_memory/latest.json",
        {
            "verified_outcomes_only_for_outcome_conditioned_memory": True,
            "department_done_is_verified_outcome": False,
            "model_weight_mutation_authorized": False,
            "outcome_conditioned_memory_count": 0,
        },
    )
    write_json(
        root,
        "runtime/opportunity_factory/value_latest.json",
        {
            "candidate_count": 24,
            "value_available_count": 0,
            "prediction_only": True,
            "actual_revenue": False,
        },
    )

    blocked = root / "runtime/departments/work/blocked"
    for index, action in enumerate((
        "resolve_quant_input:probability_success",
        "resolve_quant_input:confidence",
        "resolve_quant_input:uncertainty",
        "resolve_quant_input:time_to_revenue_days",
    )):
        write_json(
            root,
            f"runtime/departments/work/blocked/current-{index}.json",
            {
                "id": f"work-{index}",
                "plan_id": "astra_plan_current",
                "step_id": f"step-{index}",
                "target_component": "predictive_intelligence",
                "action": action,
                "error": "insufficient_verified_outcome_cohort",
            },
        )

    # Historical blockers must not contaminate current closeout.
    write_json(
        root,
        "runtime/departments/work/blocked/old.json",
        {
            "id": "old",
            "plan_id": "astra_plan_old",
            "step_id": "old-step",
            "target_component": "identity_enrichment",
            "action": "verify_decision_maker",
            "error": "specialist_adapter_required",
        },
    )


def test_evidence_gated_current_plan_can_advance(tmp_path):
    seed_ready_closeout(tmp_path)

    result = build_phase_3f_closeout(tmp_path)

    assert result["closeout_state"] == "ENGINEERING_READY_EVIDENCE_GATED"
    assert result["engineering_ready"] is True
    assert result["phase_can_advance"] is True
    assert result["production_proof_complete"] is False
    assert result["current_plan_blocker_count"] == 4
    assert result["current_plan_blocker_counts"] == {
        "insufficient_verified_outcome_cohort": 4
    }
    assert result["evidence_only_blockers"] is True
    assert result["truth_contracts_pass"] is True
    assert result["actual_revenue"] is False
    assert result["execution_authority"] == "none"


def test_non_evidence_blocker_prevents_closeout(tmp_path):
    seed_ready_closeout(tmp_path)
    write_json(
        tmp_path,
        "runtime/departments/work/blocked/current-extra.json",
        {
            "id": "extra",
            "plan_id": "astra_plan_current",
            "step_id": "extra-step",
            "target_component": "identity_enrichment",
            "action": "verify_decision_maker",
            "error": "specialist_adapter_required",
        },
    )
    evaluation = json.loads(
        (
            tmp_path
            / "runtime/astra/executive_evaluation_latest.json"
        ).read_text()
    )
    evaluation["status_counts"] = {"DONE": 4, "BLOCKED": 5}
    write_json(
        tmp_path,
        "runtime/astra/executive_evaluation_latest.json",
        evaluation,
    )

    result = build_phase_3f_closeout(tmp_path)

    assert result["engineering_ready"] is False
    assert result["phase_can_advance"] is False
    assert result["closeout_state"] == "ENGINEERING_INCOMPLETE"
    assert result["evidence_only_blockers"] is False


def test_ready_or_failed_work_prevents_closeout(tmp_path):
    seed_ready_closeout(tmp_path)
    evaluation = json.loads(
        (
            tmp_path
            / "runtime/astra/executive_evaluation_latest.json"
        ).read_text()
    )
    evaluation["status_counts"] = {
        "DONE": 4,
        "BLOCKED": 4,
        "READY": 1,
        "FAILED": 1,
    }
    write_json(
        tmp_path,
        "runtime/astra/executive_evaluation_latest.json",
        evaluation,
    )

    result = build_phase_3f_closeout(tmp_path)

    assert result["engineering_ready"] is False
    assert result["active_internal_work_count"] == 1
    assert result["failed_internal_work_count"] == 1


def test_truth_contract_violation_prevents_closeout(tmp_path):
    seed_ready_closeout(tmp_path)
    predictive = json.loads(
        (
            tmp_path
            / "runtime/predictive_intelligence/latest.json"
        ).read_text()
    )
    predictive["llm_probability_used"] = True
    write_json(
        tmp_path,
        "runtime/predictive_intelligence/latest.json",
        predictive,
    )

    result = build_phase_3f_closeout(tmp_path)

    assert result["truth_contracts_pass"] is False
    assert result["engineering_ready"] is False
