from empire_os.agi_orchestrator import build_agi_orchestration_packet


def _base_kwargs():
    return {
        "task_id": "agi-task-1",
        "goal": "Maximize verified revenue safely",
        "world_state_ref": "world:latest",
        "evidence_refs": ["evidence:1"],
    }


def test_agi_orchestrator_preserves_unknown_specialists():
    result = build_agi_orchestration_packet(**_base_kwargs())
    assert result["human_level_agi_claimed"] is False
    assert result["asi_claimed"] is False
    assert result["unknown_is_zero"] is False
    assert result["execution_ready"] is False
    assert result["recommended_cognitive_workstream"]["workstream"] == (
        "close_evidence_gaps"
    )


def test_agi_orchestrator_prefers_blocker_resolution():
    result = build_agi_orchestration_packet(
        **_base_kwargs(),
        predictive_revenue={
            "status": "AVAILABLE",
            "predicted_revenue_cents": 100000,
            "actual_revenue": False,
        },
        predictive_cloud={
            "status": "AVAILABLE",
            "cloud_operating_score": 80,
            "constraints": {"state": "BLOCKED"},
            "actual_revenue": False,
        },
        future_trend={
            "status": "AVAILABLE",
            "future_opportunity_status": "AVAILABLE",
            "direction": "up",
            "trend_confidence": 0.8,
            "trend_opportunity_alignment": 0.7,
            "causal_claim": False,
        },
        quantum_optimization={
            "status": "AVAILABLE",
            "qaoa_ready": False,
            "external_solver_called": False,
        },
        economic_memory={
            "status": "OBSERVED",
            "verified_outcomes_only_for_outcome_conditioned_memory": True,
            "outcome_conditioned_memory_count": 4,
            "model_weight_mutation_authorized": False,
        },
    )
    assert result["recommended_cognitive_workstream"]["workstream"] == (
        "resolve_governance_or_capacity_constraints"
    )
    assert result["external_action_performed"] is False


def test_agi_orchestrator_routes_quantum_benchmark_when_ready():
    result = build_agi_orchestration_packet(
        **_base_kwargs(),
        predictive_revenue={
            "status": "AVAILABLE",
            "predicted_revenue_cents": 100000,
            "actual_revenue": False,
        },
        predictive_cloud={
            "status": "AVAILABLE",
            "cloud_operating_score": 85,
            "constraints": {"state": "CLEAR"},
            "actual_revenue": False,
        },
        future_trend={
            "status": "AVAILABLE",
            "future_opportunity_status": "AVAILABLE",
            "direction": "up",
            "trend_confidence": 0.8,
            "trend_opportunity_alignment": 0.7,
            "causal_claim": False,
        },
        quantum_optimization={
            "status": "AVAILABLE",
            "qaoa_ready": True,
            "model_type": "QUBO",
            "external_solver_called": False,
            "quantum_advantage_claimed": False,
        },
        economic_memory={
            "status": "OBSERVED",
            "verified_outcomes_only_for_outcome_conditioned_memory": True,
            "outcome_conditioned_memory_count": 4,
            "model_weight_mutation_authorized": False,
        },
    )
    workstreams = [
        row["workstream"]
        for row in result["candidate_workstreams"]
    ]
    assert "benchmark_quantum_candidate" in workstreams
    assert result["verification_requirements"][
        "classical_reference_required_for_quantum_claim"
    ] is True
    assert result["execution_authority"] == "none"


def test_agi_orchestrator_builds_memory_query():
    result = build_agi_orchestration_packet(
        **_base_kwargs(),
        entity_refs=["buyer:1"],
        topic_keys=["predictive_revenue", "quantum"],
    )
    query = result["memory_query"]
    assert query["task_type"] == "planning"
    assert query["entity_refs"] == ["buyer:1"]
    assert query["retrieval_only"] is True
