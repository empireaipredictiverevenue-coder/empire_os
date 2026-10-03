from empire_os.solver_performance_memory import (
    build_solver_performance_memory,
    recommend_benchmark_solver,
    workload_signature,
)


def _arena(*, cp_ms, anneal_ms, anneal_matches=True):
    fingerprint = f"problem:{cp_ms}:{anneal_ms}"
    return {
        "status": "AVAILABLE",
        "problem_fingerprint": fingerprint,
        "workload_type": "buyer_allocation",
        "variable_count": 40,
        "constraint_count": 10,
        "representations": ["CQM", "QUBO"],
        "baseline_solver": "classical_exact_binary_ir",
        "external_qpu_called": False,
        "runs": {
            "classical_exact_binary_ir": {
                "solver": "classical_exact_binary_ir",
                "constraints_satisfied": True,
                "wall_clock_ms": 100.0,
                "compute_cost_minor_units": None,
                "quantum_advantage_claimed": False,
            },
            "ortools_cp_sat": {
                "solver": "ortools_cp_sat",
                "constraints_satisfied": True,
                "wall_clock_ms": cp_ms,
                "compute_cost_minor_units": None,
                "quantum_advantage_claimed": False,
            },
            "dwave_local_simulated_annealing": {
                "solver": "dwave_local_simulated_annealing",
                "constraints_satisfied": True,
                "wall_clock_ms": anneal_ms,
                "compute_cost_minor_units": None,
                "quantum_advantage_claimed": False,
            },
        },
        "comparisons": {
            "ortools_cp_sat": {
                "matches_or_beats_reference": True,
            },
            "dwave_local_simulated_annealing": {
                "matches_or_beats_reference": anneal_matches,
            },
        },
    }


def test_workload_signature_buckets_scale_and_representations():
    signature = workload_signature(_arena(cp_ms=20, anneal_ms=10))

    assert signature == (
        "buyer_allocation|v:000025-000100|"
        "c:000001-000024|r:CQM,QUBO"
    )


def test_memory_requires_repeated_feasible_reference_matching_evidence():
    memory = build_solver_performance_memory([
        _arena(cp_ms=20, anneal_ms=10, anneal_matches=True),
        _arena(cp_ms=22, anneal_ms=11, anneal_matches=False),
        _arena(cp_ms=18, anneal_ms=9, anneal_matches=True),
    ])

    profile = next(iter(memory["profiles"].values()))
    assert profile["solver_profiles"]["ortools_cp_sat"][
        "recommendation_eligible"
    ] is True
    assert profile["solver_profiles"]["dwave_local_simulated_annealing"][
        "recommendation_eligible"
    ] is False
    assert profile["recommended_benchmark_solver"] == "ortools_cp_sat"
    assert profile["automatic_production_routing_changed"] is False


def test_memory_can_recommend_quantum_inspired_only_after_clean_repetition():
    arenas = [
        _arena(cp_ms=20, anneal_ms=10, anneal_matches=True),
        _arena(cp_ms=22, anneal_ms=11, anneal_matches=True),
        _arena(cp_ms=18, anneal_ms=9, anneal_matches=True),
    ]
    memory = build_solver_performance_memory(arenas)
    recommendation = recommend_benchmark_solver(
        memory=memory,
        arena_shape=arenas[0],
    )

    assert recommendation["status"] == "AVAILABLE"
    assert recommendation["recommended_benchmark_solver"] == (
        "dwave_local_simulated_annealing"
    )
    assert recommendation["recommendation_only"] is True
    assert recommendation["production_promotion_ready"] is False
    assert recommendation["quantum_advantage_claimed"] is False


def test_memory_does_not_recommend_from_one_observation():
    arena = _arena(cp_ms=20, anneal_ms=10, anneal_matches=True)
    memory = build_solver_performance_memory([arena])

    recommendation = recommend_benchmark_solver(
        memory=memory,
        arena_shape=arena,
    )

    assert recommendation["status"] == "UNAVAILABLE"
    assert recommendation["reason"] == (
        "insufficient_repeated_solver_evidence"
    )
