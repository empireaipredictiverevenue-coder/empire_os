from empire_os.quantum_optimization import (
    benchmark_solution,
    build_allocation_optimization_problem,
    build_cqm_export,
    build_qubo_export,
    solve_allocation_classical_exact,
)


def _options():
    return [
        {
            "prospect_id": "p1",
            "buyer_id": "b1",
            "expected_value_cents": 10000,
            "evidence_refs": ["erv:p1:b1"],
        },
        {
            "prospect_id": "p1",
            "buyer_id": "b2",
            "expected_value_cents": 9000,
            "evidence_refs": ["erv:p1:b2"],
        },
        {
            "prospect_id": "p2",
            "buyer_id": "b1",
            "expected_value_cents": 8000,
            "evidence_refs": ["erv:p2:b1"],
        },
        {
            "prospect_id": "p2",
            "buyer_id": "b2",
            "expected_value_cents": 7000,
            "evidence_refs": ["erv:p2:b2"],
        },
    ]


def test_problem_preserves_unknown_economics():
    problem = build_allocation_optimization_problem(
        options=[
            {
                "prospect_id": "p1",
                "buyer_id": "b1",
                "expected_value_cents": None,
                "evidence_refs": ["match:p1:b1"],
            },
            {
                "prospect_id": "p2",
                "buyer_id": "b1",
                "expected_value_cents": 8000,
                "evidence_refs": ["erv:p2:b1"],
            },
        ],
        buyer_capacities={"b1": 1},
    )
    assert problem["status"] == "AVAILABLE"
    assert len(problem["variables"]) == 1
    assert len(problem["blocked_options"]) == 1
    assert problem["blocked_options"][0]["reason"] == (
        "unknown_allocation_economics_preserved"
    )
    assert problem["unknown_is_zero"] is False


def test_problem_fails_closed_when_capacity_unknown():
    problem = build_allocation_optimization_problem(
        options=_options(),
        buyer_capacities={"b1": 1},
    )
    assert problem["status"] == "UNAVAILABLE"
    assert problem["reason"] == "buyer_capacity_unknown"
    assert problem["unknown_buyers"] == ["b2"]


def test_classical_reference_finds_capacity_constrained_optimum():
    problem = build_allocation_optimization_problem(
        options=_options(),
        buyer_capacities={"b1": 1, "b2": 1},
    )
    result = solve_allocation_classical_exact(problem)
    assert result["status"] == "AVAILABLE"
    assert result["optimal_for_normalized_problem"] is True
    assert result["objective_value_cents"] == 17000
    assignments = {
        (row["prospect_id"], row["buyer_id"])
        for row in result["selected_assignments"]
    }
    assert assignments in (
        {("p1", "b1"), ("p2", "b2")},
        {("p1", "b2"), ("p2", "b1")},
    )
    assert result["allocation_execution"] is False


def test_cqm_export_keeps_hard_constraints():
    problem = build_allocation_optimization_problem(
        options=_options(),
        buyer_capacities={"b1": 2, "b2": 1},
    )
    cqm = build_cqm_export(problem)
    assert cqm["status"] == "AVAILABLE"
    assert cqm["model_type"] == "CONSTRAINED_QUADRATIC_MODEL"
    assert any(
        row["name"] == "buyer_capacity::b1"
        and row["rhs"] == 2
        for row in cqm["constraints"]
    )
    assert cqm["external_solver_called"] is False


def test_qubo_is_ready_for_unit_capacity_only():
    problem = build_allocation_optimization_problem(
        options=_options(),
        buyer_capacities={"b1": 1, "b2": 1},
    )
    qubo = build_qubo_export(problem)
    assert qubo["status"] == "AVAILABLE"
    assert qubo["qaoa_ready"] is True
    assert qubo["model_type"] == "QUBO"
    assert qubo["quadratic"]
    assert qubo["external_solver_called"] is False


def test_qubo_fails_closed_for_general_capacity():
    problem = build_allocation_optimization_problem(
        options=_options(),
        buyer_capacities={"b1": 2, "b2": 1},
    )
    qubo = build_qubo_export(problem)
    assert qubo["status"] == "UNAVAILABLE"
    assert qubo["reason"] == "general_capacity_requires_slack_encoding"
    assert qubo["qaoa_ready"] is False
    assert qubo["buyers_requiring_slack_encoding"] == ["b1"]


def test_benchmark_does_not_claim_quantum_advantage():
    result = benchmark_solution(
        classical={"objective_value_cents": 17000},
        candidate={"objective_value_cents": 16500},
    )
    assert result["status"] == "AVAILABLE"
    assert result["optimality_gap_cents"] == 500
    assert result["matches_or_beats_reference"] is False
    assert result["quantum_advantage_claimed"] is False
    assert result["benchmark_required_before_production_use"] is True
