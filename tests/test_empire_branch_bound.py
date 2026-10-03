from empire_os.optimization_problem_factory import build_problem_ir
from empire_os.solver_adapters.empire_branch_bound import (
    solve_empire_branch_bound,
)
from empire_os.solver_adapters.exact_binary import solve_exact_binary


def _problem():
    return build_problem_ir(
        workload_key="empire_bb_fixture",
        workload_type="generic_binary_portfolio",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=[
            {"variable": "x::a", "evidence_refs": ["ev:a"]},
            {"variable": "x::b", "evidence_refs": ["ev:b"]},
            {"variable": "x::c", "evidence_refs": ["ev:c"]},
            {"variable": "x::d", "evidence_refs": ["ev:d"]},
        ],
        objective={
            "sense": "MAXIMIZE",
            "linear": {
                "x::a": 9,
                "x::b": 7,
                "x::c": -3,
                "x::d": 5,
            },
            "quadratic": {},
        },
        constraints=[
            {
                "name": "capacity",
                "coefficients": {
                    "x::a": 1,
                    "x::b": 1,
                    "x::d": 1,
                },
                "sense": "<=",
                "rhs": 2,
            },
            {
                "name": "coverage",
                "coefficients": {
                    "x::b": 1,
                    "x::c": 1,
                },
                "sense": ">=",
                "rhs": 1,
            },
        ],
        time_budget_ms=1000,
        representations=("CQM",),
    )


def test_empire_branch_bound_matches_exact_reference():
    problem = _problem()
    exact = solve_exact_binary(problem)
    result = solve_empire_branch_bound(problem)

    assert exact["status"] == "AVAILABLE"
    assert result["status"] == "AVAILABLE"
    assert result["solve_status"] == "OPTIMAL"
    assert result["objective_value"] == exact["objective_value"]
    assert result["selected_variables"] == exact["selected_variables"]
    assert result["constraints_satisfied"] is True
    assert result["optimal_for_normalized_problem"] is True
    assert result["external_solver_called"] is False
    assert result["execution_authority"] == "none"


def test_empire_branch_bound_handles_equality_and_minimize():
    problem = build_problem_ir(
        workload_key="empire_bb_min",
        workload_type="generic_binary_portfolio",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=[
            {"variable": "x::1", "evidence_refs": ["ev:1"]},
            {"variable": "x::2", "evidence_refs": ["ev:2"]},
            {"variable": "x::3", "evidence_refs": ["ev:3"]},
        ],
        objective={
            "sense": "MINIMIZE",
            "linear": {"x::1": 5, "x::2": 2, "x::3": 7},
            "quadratic": {},
        },
        constraints=[
            {
                "name": "choose_two",
                "coefficients": {"x::1": 1, "x::2": 1, "x::3": 1},
                "sense": "==",
                "rhs": 2,
            }
        ],
        time_budget_ms=1000,
    )
    exact = solve_exact_binary(problem)
    result = solve_empire_branch_bound(problem)

    assert result["status"] == "AVAILABLE"
    assert result["objective_value"] == exact["objective_value"] == 7.0
    assert result["selected_variables"] == ["x::1", "x::2"]


def test_empire_branch_bound_requires_bounded_time():
    problem = _problem()
    problem["time_budget_ms"] = None
    # Rebuild to keep the fingerprint honest.
    problem = build_problem_ir(
        workload_key="no_time",
        workload_type="generic_binary_portfolio",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=[
            {"variable": "x::1", "evidence_refs": ["ev:1"]}
        ],
        objective={
            "sense": "MAXIMIZE",
            "linear": {"x::1": 1},
            "quadratic": {},
        },
        constraints=[],
    )

    result = solve_empire_branch_bound(problem)

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "time_budget_required"


def test_empire_branch_bound_rejects_tampered_ir():
    problem = _problem()
    problem["objective"]["linear"]["x::a"] = 999

    result = solve_empire_branch_bound(problem)

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "optimization_problem_integrity_failed"
