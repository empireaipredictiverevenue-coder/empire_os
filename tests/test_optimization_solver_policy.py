from empire_os.optimization_solver_policy import (
    build_solver_policy_profile,
    recommend_solver_for_plan,
)


def _arena(
    *,
    branch_ms,
    temper_ms,
    branch_match=True,
    temper_match=True,
    include_market=False,
):
    runs = {
        "classical_exact_binary_ir": {
            "solver": "classical_exact_binary_ir",
            "constraints_satisfied": True,
            "objective_value": 1000,
            "wall_clock_ms": 100,
            "compute_cost_minor_units": None,
            "external": False,
            "quantum_advantage_claimed": False,
        },
        "empire_branch_bound": {
            "solver": "empire_branch_bound",
            "constraints_satisfied": True,
            "objective_value": 1000 if branch_match else 900,
            "wall_clock_ms": branch_ms,
            "compute_cost_minor_units": None,
            "external": False,
            "quantum_advantage_claimed": False,
        },
        "empire_parallel_tempering": {
            "solver": "empire_parallel_tempering",
            "constraints_satisfied": True,
            "objective_value": 1000 if temper_match else 900,
            "wall_clock_ms": temper_ms,
            "compute_cost_minor_units": None,
            "external": False,
            "quantum_advantage_claimed": False,
        },
    }
    comparisons = {
        "empire_branch_bound": {
            "matches_or_beats_reference": branch_match,
        },
        "empire_parallel_tempering": {
            "matches_or_beats_reference": temper_match,
        },
    }
    if include_market:
        runs["ortools_cp_sat"] = {
            "solver": "ortools_cp_sat",
            "constraints_satisfied": True,
            "objective_value": 1000,
            "wall_clock_ms": 0.1,
            "compute_cost_minor_units": None,
            "external": False,
            "quantum_advantage_claimed": False,
        }
        comparisons["ortools_cp_sat"] = {
            "matches_or_beats_reference": True,
        }

    return {
        "status": "AVAILABLE",
        "workload_type": "buyer_allocation",
        "variable_count": 40,
        "constraint_count": 10,
        "representations": ["CQM", "QUBO"],
        "baseline_solver": "classical_exact_binary_ir",
        "external_qpu_called": False,
        "runs": runs,
        "comparisons": comparisons,
    }


def test_solver_policy_requires_repeated_benchmark_evidence():
    result = build_solver_policy_profile([
        _arena(branch_ms=2, temper_ms=8)
    ])

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "insufficient_benchmark_arenas"


def test_solver_policy_uses_empire_owned_fastest_quality_lane():
    arenas = [
        _arena(branch_ms=2, temper_ms=8),
        _arena(branch_ms=3, temper_ms=9),
        _arena(branch_ms=2.5, temper_ms=7),
    ]

    result = build_solver_policy_profile(arenas)

    assert result["status"] == "AVAILABLE"
    assert result["recommended_nonbaseline_solver"] == "empire_branch_bound"
    assert result["memory_schema_version"] == (
        "empire.solver_performance_memory.v1"
    )
    assert result["solver_profiles"]["empire_branch_bound"][
        "reference_match_rate"
    ] == 1.0
    assert result["market_reference_solvers_can_influence_policy"] is False
    assert result["automatic_production_routing_changed"] is False
    assert result["quantum_advantage_claimed"] is False


def test_solver_policy_rejects_speed_if_quality_regresses():
    arenas = [
        _arena(branch_ms=2, temper_ms=1, temper_match=True),
        _arena(branch_ms=2, temper_ms=1, temper_match=False),
        _arena(branch_ms=2, temper_ms=1, temper_match=True),
    ]

    result = build_solver_policy_profile(arenas)

    assert result["recommended_nonbaseline_solver"] == "empire_branch_bound"
    assert result["solver_profiles"]["empire_parallel_tempering"][
        "recommendation_eligible"
    ] is False


def test_solver_policy_excludes_market_reference_solver_even_when_fastest():
    arenas = [
        _arena(branch_ms=2, temper_ms=8, include_market=True),
        _arena(branch_ms=3, temper_ms=9, include_market=True),
        _arena(branch_ms=2.5, temper_ms=7, include_market=True),
    ]

    result = build_solver_policy_profile(arenas)

    assert result["recommended_nonbaseline_solver"] == "empire_branch_bound"
    assert "ortools_cp_sat" not in result["solver_profiles"]
    assert "ortools_cp_sat" in result["excluded_market_reference_solvers"]
    assert result["market_reference_solvers_can_influence_policy"] is False


def test_solver_policy_external_candidates_fail_closed():
    result = build_solver_policy_profile(
        [
            _arena(branch_ms=2, temper_ms=8),
            _arena(branch_ms=3, temper_ms=9),
            _arena(branch_ms=2.5, temper_ms=7),
        ],
        allow_external_candidates=True,
    )

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "external_solver_policy_not_supported"


def test_solver_policy_advice_requires_current_lane_to_be_runnable():
    policy = build_solver_policy_profile([
        _arena(branch_ms=2, temper_ms=8),
        _arena(branch_ms=3, temper_ms=9),
        _arena(branch_ms=2.5, temper_ms=7),
    ])
    plan = {
        "status": "AVAILABLE",
        "workload_type": "buyer_allocation",
        "variable_count": 40,
        "constraint_count": 10,
        "representations": ["CQM", "QUBO"],
        "solver_route": {
            "primary_solver": "classical_greedy_reference",
            "benchmark_lanes": [
                {
                    "solver": "empire_branch_bound",
                    "runnable": False,
                    "blockers": ["benchmark_lane_not_ready"],
                }
            ],
        },
    }

    result = recommend_solver_for_plan(plan, policy)

    assert result["status"] == "HELD"
    assert result["recommended_solver"] == "empire_branch_bound"
    assert result["reason"] == "recommended_solver_not_currently_runnable"
    assert result["automatic_production_routing_changed"] is False


def test_solver_policy_rejects_injected_non_empire_recommendation():
    policy = build_solver_policy_profile([
        _arena(branch_ms=2, temper_ms=8),
        _arena(branch_ms=3, temper_ms=9),
        _arena(branch_ms=2.5, temper_ms=7),
    ])
    policy["recommended_nonbaseline_solver"] = "ortools_cp_sat"
    plan = {
        "status": "AVAILABLE",
        "workload_type": "buyer_allocation",
        "variable_count": 40,
        "constraint_count": 10,
        "representations": ["CQM", "QUBO"],
        "solver_route": {
            "primary_solver": "classical_greedy_reference",
            "benchmark_lanes": [],
        },
    }

    result = recommend_solver_for_plan(plan, policy)

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "non_empire_solver_recommendation_rejected"


def test_solver_policy_refuses_different_workload_shape():
    policy = build_solver_policy_profile([
        _arena(branch_ms=2, temper_ms=8),
        _arena(branch_ms=3, temper_ms=9),
        _arena(branch_ms=2.5, temper_ms=7),
    ])
    plan = {
        "status": "AVAILABLE",
        "workload_type": "buyer_allocation",
        "variable_count": 400,
        "constraint_count": 10,
        "representations": ["CQM", "QUBO"],
        "solver_route": {"benchmark_lanes": []},
    }

    result = recommend_solver_for_plan(plan, policy)

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "workload_shape_mismatch"
