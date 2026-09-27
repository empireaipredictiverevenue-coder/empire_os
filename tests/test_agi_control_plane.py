import pytest

from empire_os.agi_control_plane import (
    LAYERS,
    assess_agi_layer_readiness,
    build_cognitive_packet,
    review_learning_candidate,
)


def test_cognitive_packet_is_auditable_not_chain_of_thought():
    packet = build_cognitive_packet(
        task_id="task-1",
        goal="Choose the highest-value reversible next step.",
        evidence_refs=["evidence:market:1", "evidence:buyer:1"],
        world_state_ref="world:2026-09-20T00:00:00Z",
        memory_refs=[
            {"memory_type": "semantic", "ref": "memory:buyer-rules:v1"},
            {
                "memory_type": "outcome_conditioned",
                "ref": "outcome:1",
                "verified_outcome": True,
            },
        ],
        options=[
            {
                "option_id": "o1",
                "summary": "Prepare territory evidence pack.",
                "expected_value_cents": 50000,
                "expected_cost_cents": 5000,
                "risk_score": 0.1,
                "reversible": True,
                "required_authority": "none",
                "evidence_refs": ["evidence:market:1"],
            }
        ],
        selected_option_id="o1",
        verifier={
            "status": "passed",
            "evidence_supported": True,
            "policy_consistent": True,
            "freshness_verified": True,
            "independent": True,
        },
        policy={
            "status": "passed",
            "allowed": True,
            "approval_required": False,
        },
    )
    assert packet["authority_mode"] == "OBSERVE"
    assert packet["execution_ready"] is False
    assert packet["execution_performed"] is False
    assert packet["private_chain_of_thought_persisted"] is False
    assert packet["candidate_options"][0]["expected_gross_value_cents"] == 45000


def test_observe_mode_rejects_side_effect_request():
    with pytest.raises(ValueError, match="OBSERVE"):
        build_cognitive_packet(
            task_id="t",
            goal="g",
            evidence_refs=["e:1"],
            world_state_ref="world:1",
            authority_mode="OBSERVE",
            side_effect_class="external_communication",
        )


def test_outcome_conditioned_memory_requires_verified_outcome():
    with pytest.raises(ValueError, match="verified_outcome"):
        build_cognitive_packet(
            task_id="t",
            goal="g",
            evidence_refs=["e:1"],
            world_state_ref="world:1",
            memory_refs=[
                {
                    "memory_type": "outcome_conditioned",
                    "ref": "memory:fake",
                    "verified_outcome": False,
                }
            ],
        )


def test_guarded_execution_readiness_requires_verifier_and_policy():
    packet = build_cognitive_packet(
        task_id="task-2",
        goal="Execute one approved reversible action.",
        evidence_refs=["e:1"],
        world_state_ref="world:1",
        options=[{
            "option_id": "o1",
            "summary": "Approved external action",
            "reversible": True,
            "required_authority": "approved_external_send",
            "evidence_refs": ["e:1"],
        }],
        selected_option_id="o1",
        verifier={
            "status": "passed",
            "evidence_supported": True,
            "policy_consistent": True,
            "freshness_verified": True,
            "independent": True,
        },
        policy={
            "status": "passed",
            "allowed": True,
            "approval_required": True,
            "approval_present": True,
        },
        authority_mode="GUARDED_EXECUTE",
        side_effect_class="external_communication",
    )
    assert packet["execution_ready"] is True
    assert packet["execution_performed"] is False


def test_readiness_counts_explicit_layers_only():
    result = assess_agi_layer_readiness({})
    assert result["total_layer_count"] == len(LAYERS)
    assert result["ready_layer_count"] == 0
    assert result["consequential_autonomy_ready"] is False

    evidence = {
        "canonical_evidence": True,
        "source_provenance": True,
        "freshness": True,
    }
    grounded = assess_agi_layer_readiness(evidence)
    assert grounded["ready_layer_count"] == 1
    assert grounded["layers"][0]["layer"] == "grounding"
    assert grounded["layers"][0]["status"] == "READY"


def test_learning_candidate_requires_real_outcome_and_eval():
    blocked = review_learning_candidate({
        "synthetic_only": True,
        "evaluation_passed": True,
        "shadow_passed": True,
        "policy_review_passed": True,
    })
    assert blocked["promotion_ready_for_human_review"] is False
    assert "verified_outcome_required" in blocked["blockers"]
    assert "synthetic_only_cannot_promote" in blocked["blockers"]
    assert blocked["model_weight_mutation"] is False

    ready = review_learning_candidate({
        "verified_outcome": True,
        "outcome_ref": "outcome:1",
        "baseline_ref": "baseline:1",
        "candidate_ref": "candidate:1",
        "evaluation_passed": True,
        "shadow_passed": True,
        "policy_review_passed": True,
        "synthetic_only": False,
    })
    assert ready["promotion_ready_for_human_review"] is True
    assert ready["promotion_state"] == "EVALUATED"
    assert ready["permission_expansion"] is False
