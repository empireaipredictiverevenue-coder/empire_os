from empire_os.action_portfolio_optimization import (
    build_portfolio_optimization_problem,
)
from empire_os.optimization_problem_factory import (
    compile_action_portfolio_problem,
    compile_allocation_problem,
)
from empire_os.optimization_qubo import build_safe_qubo
from empire_os.quantum_optimization import (
    build_allocation_optimization_problem,
)


def test_safe_qubo_compiles_unit_capacity_allocation_ir():
    source = build_allocation_optimization_problem(
        options=[
            {
                "prospect_id": "p1",
                "buyer_id": "b1",
                "expected_value_cents": 1000,
                "evidence_refs": ["ev:1"],
            },
            {
                "prospect_id": "p1",
                "buyer_id": "b2",
                "expected_value_cents": 800,
                "evidence_refs": ["ev:2"],
            },
        ],
        buyer_capacities={"b1": 1, "b2": 1},
    )
    problem = compile_allocation_problem(source)
    qubo = build_safe_qubo(problem)

    assert qubo["status"] == "AVAILABLE"
    assert qubo["problem_fingerprint"] == problem["problem_fingerprint"]
    assert qubo["qaoa_ready"] is True
    assert qubo["local_bqm_ready"] is True
    assert qubo["constraint_penalty"] > 0
    assert qubo["execution_authority"] == "none"


def test_safe_qubo_rejects_general_capacity_constraint():
    source = build_allocation_optimization_problem(
        options=[
            {
                "prospect_id": "p1",
                "buyer_id": "b1",
                "expected_value_cents": 1000,
                "evidence_refs": ["ev:1"],
            },
            {
                "prospect_id": "p2",
                "buyer_id": "b1",
                "expected_value_cents": 900,
                "evidence_refs": ["ev:2"],
            },
        ],
        buyer_capacities={"b1": 2},
    )
    problem = compile_allocation_problem(source)
    qubo = build_safe_qubo(problem)

    assert qubo["status"] == "UNAVAILABLE"
    assert qubo["reason"] == "general_constraint_requires_cqm_or_slack_encoding"


def test_safe_qubo_rejects_budget_constraint_in_action_portfolio():
    source = build_portfolio_optimization_problem(
        actions=[
            {
                "action_key": "a1",
                "expected_incremental_value_cents": 5000,
                "action_cost_cents": 500,
                "evidence_refs": ["ev:a1"],
            }
        ],
        budget_cents=1000,
    )
    problem = compile_action_portfolio_problem(source)
    qubo = build_safe_qubo(problem)

    assert qubo["status"] == "UNAVAILABLE"
    assert qubo["reason"] in {
        "general_constraint_requires_cqm_or_slack_encoding",
        "non_unit_constraint_coefficient_requires_cqm",
    }
