from empire_os.media_workflow_evolution import (
    WorkflowExecutionEvidence,
    compile_media_skill_candidate,
    workflow_promotion_review,
)


def _execution(index: int) -> WorkflowExecutionEvidence:
    return WorkflowExecutionEvidence(
        execution_id=f"run-{index}",
        workflow_name="research_topic",
        workflow_version="v1",
        input_shape_hash="shape-1",
        step_signature=(
            "collect_evidence",
            "build_research_pack",
            "verify_claims",
        ),
        outcome_state="SUCCESS",
        quality_score=0.9,
        accuracy_passed=True,
        evidence_refs=(f"run:evidence:{index}",),
    )


def test_repeated_successful_workflow_becomes_skill_candidate_only():
    result = compile_media_skill_candidate(
        (_execution(1), _execution(2), _execution(3))
    )

    assert result["state"] == "SKILL_CANDIDATE"
    assert result["consistent_procedure"] is True
    assert result["passing_execution_count"] == 3
    assert "shadow_validation" in result["required_promotion_path"]
    assert result["production_self_modification_authorized"] is False
    assert result["automatic_registration_authorized"] is False
    assert result["execution_authority"] == "none"


def test_inconsistent_or_weak_workflow_stays_on_hold():
    weak = WorkflowExecutionEvidence(
        execution_id="weak",
        workflow_name="research_topic",
        workflow_version="v2",
        input_shape_hash="shape-2",
        step_signature=("collect_evidence",),
        outcome_state="FAILED",
        quality_score=0.4,
        accuracy_passed=False,
        failure_modes=("unsupported_claim",),
        evidence_refs=("run:weak",),
    )

    result = compile_media_skill_candidate(
        (_execution(1), _execution(2), weak)
    )

    assert result["state"] == "HOLD_FOR_MORE_EVIDENCE"
    assert result["automatic_registration_authorized"] is False


def test_workflow_promotion_never_auto_promotes():
    result = workflow_promotion_review(
        candidate_ref="media-skill:research-topic:v2",
        tests_passed=True,
        replay_passed=True,
        shadow_passed=True,
        quality_improved=True,
        accuracy_regressed=False,
        cost_regressed_materially=False,
        failure_rate_regressed=False,
    )

    assert result["state"] == "PROMOTION_CANDIDATE"
    assert result["controlled_experiment_required"] is True
    assert result["automatic_production_promotion"] is False
    assert result["production_self_modification_authorized"] is False
    assert result["execution_authority"] == "none"
