import pytest

pytest.importorskip("ortools")

from empire_os.optimization_problem_factory import build_problem_ir
from empire_os.optimization_shards import solve_partitioned_cp_sat


def _problem(*, cross_partition=False):
    variables = [
        {
            "variable": "x::n1",
            "partition_key": "north",
            "evidence_refs": ["ev:n1"],
        },
        {
            "variable": "x::n2",
            "partition_key": "north",
            "evidence_refs": ["ev:n2"],
        },
        {
            "variable": "x::s1",
            "partition_key": "south",
            "evidence_refs": ["ev:s1"],
        },
        {
            "variable": "x::s2",
            "partition_key": "south",
            "evidence_refs": ["ev:s2"],
        },
    ]
    constraints = [
        {
            "name": "north_capacity",
            "coefficients": {"x::n1": 1, "x::n2": 1},
            "sense": "<=",
            "rhs": 1,
        },
        {
            "name": "south_capacity",
            "coefficients": {"x::s1": 1, "x::s2": 1},
            "sense": "<=",
            "rhs": 1,
        },
    ]
    if cross_partition:
        constraints.append({
            "name": "global_capacity",
            "coefficients": {"x::n1": 1, "x::s1": 1},
            "sense": "<=",
            "rhs": 1,
        })
    return build_problem_ir(
        workload_key="shard_fixture",
        workload_type="generic_binary_portfolio",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=variables,
        objective={
            "sense": "MAXIMIZE",
            "linear": {
                "x::n1": 5,
                "x::n2": 3,
                "x::s1": 4,
                "x::s2": 2,
            },
            "quadratic": {},
        },
        constraints=constraints,
        time_budget_ms=1500,
        representations=("CQM",),
    )


def test_independent_partitions_solve_in_parallel_and_reconcile():
    result = solve_partitioned_cp_sat(
        _problem(),
        max_variables_per_shard=2,
        max_parallel_workers=2,
    )

    assert result["status"] == "AVAILABLE"
    assert result["strategy"] == "independent_shards"
    assert result["shard_count"] == 2
    assert result["selected_variables"] == ["x::n1", "x::s1"]
    assert result["objective_value"] == 9.0
    assert result["constraints_satisfied"] is True
    assert result["compute_cost_known"] is False
    assert result["execution_authority"] == "none"


def test_cross_partition_constraint_requires_global_coordinator():
    result = solve_partitioned_cp_sat(
        _problem(cross_partition=True),
        max_variables_per_shard=2,
        max_parallel_workers=2,
    )

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "global_coordinator_required"
    assert result["decomposition"]["strategy"] == (
        "coordinator_decomposition_required"
    )
    assert "global_capacity" in (
        result["decomposition"]["blockers"][
            "cross_partition_constraints"
        ]
    )
    assert result["global_constraint_reconciliation_required"] is True


def test_small_problem_uses_single_worker_path():
    problem = _problem()

    result = solve_partitioned_cp_sat(
        problem,
        max_variables_per_shard=10,
    )

    assert result["status"] == "AVAILABLE"
    assert result["strategy"] == "single_worker"
    assert result["shard_count"] == 1
    assert result["objective_value"] == 9.0
