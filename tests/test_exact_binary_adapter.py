from empire_os.optimization_problem_factory import build_problem_ir
from empire_os.solver_adapters.exact_binary import solve_exact_binary


def _problem():
    return build_problem_ir(
        workload_key="exact_fixture",
        workload_type="future_workload",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=[
            {"variable": "x::a", "evidence_refs": ["ev:a"]},
            {"variable": "x::b", "evidence_refs": ["ev:b"]},
        ],
        objective={
            "sense": "MAXIMIZE",
            "linear": {"x::a": 10, "x::b": 7},
            "quadratic": {},
        },
        constraints=[
            {
                "name": "choose_one",
                "coefficients": {"x::a": 1, "x::b": 1},
                "sense": "<=",
                "rhs": 1,
            }
        ],
        representations=("CQM",),
    )


def test_exact_binary_solves_generic_ir_with_observed_latency():
    result = solve_exact_binary(_problem())

    assert result["status"] == "AVAILABLE"
    assert result["selected_variables"] == ["x::a"]
    assert result["objective_value"] == 10.0
    assert result["constraints_satisfied"] is True
    assert result["optimal_for_normalized_problem"] is True
    assert result["explored_states"] == 4
    assert result["wall_clock_ms"] >= 0
    assert result["compute_cost_minor_units"] is None
    assert result["execution_authority"] == "none"


def test_exact_binary_respects_variable_limit():
    variables = [
        {"variable": f"x::{index}", "evidence_refs": [f"ev:{index}"]}
        for index in range(3)
    ]
    problem = build_problem_ir(
        workload_key="limit_fixture",
        workload_type="fixture",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=variables,
        objective={
            "sense": "MAXIMIZE",
            "linear": {
                row["variable"]: 1
                for row in variables
            },
            "quadratic": {},
        },
        constraints=[],
    )

    result = solve_exact_binary(problem, max_variables=2)

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "exact_reference_variable_limit_exceeded"


def test_exact_binary_reports_infeasible_problem():
    problem = build_problem_ir(
        workload_key="infeasible",
        workload_type="fixture",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=[
            {"variable": "x::a", "evidence_refs": ["ev:a"]}
        ],
        objective={
            "sense": "MAXIMIZE",
            "linear": {"x::a": 1},
            "quadratic": {},
        },
        constraints=[
            {
                "name": "must_zero",
                "coefficients": {"x::a": 1},
                "sense": "==",
                "rhs": 0,
            },
            {
                "name": "must_one",
                "coefficients": {"x::a": 1},
                "sense": "==",
                "rhs": 1,
            },
        ],
    )

    result = solve_exact_binary(problem)

    assert result["status"] == "INFEASIBLE"
    assert result["feasible_states"] == 0
