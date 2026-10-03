from empire_os.intelligence_optimization_fabric import (
    build_optimization_fabric_plan,
)
from empire_os.optimization_job_protocol import (
    build_compute_jobs,
    reconcile_compute_results,
)
from empire_os.optimization_problem_factory import build_problem_ir
from empire_os.solver_adapters.exact_binary import solve_exact_binary


def _partitioned_problem(*, cross_partition=False):
    constraints = [
        {
            "name": "north_once",
            "coefficients": {"x::a": 1, "x::b": 1},
            "sense": "<=",
            "rhs": 1,
        },
        {
            "name": "south_once",
            "coefficients": {"x::c": 1, "x::d": 1},
            "sense": "<=",
            "rhs": 1,
        },
    ]
    if cross_partition:
        constraints.append({
            "name": "global_once",
            "coefficients": {"x::a": 1, "x::c": 1},
            "sense": "<=",
            "rhs": 1,
        })
    return build_problem_ir(
        workload_key="partitioned_fixture",
        workload_type="future_workload",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=[
            {"variable": "x::a", "partition_key": "north", "evidence_refs": ["ev:a"]},
            {"variable": "x::b", "partition_key": "north", "evidence_refs": ["ev:b"]},
            {"variable": "x::c", "partition_key": "south", "evidence_refs": ["ev:c"]},
            {"variable": "x::d", "partition_key": "south", "evidence_refs": ["ev:d"]},
        ],
        objective={
            "sense": "MAXIMIZE",
            "linear": {"x::a": 10, "x::b": 4, "x::c": 8, "x::d": 2},
            "quadratic": {},
        },
        constraints=constraints,
        time_budget_ms=2000,
        cost_budget_minor_units=100,
        representations=("CQM",),
    )


def test_independent_shards_materialize_deterministic_bounded_jobs():
    problem = _partitioned_problem()
    plan = build_optimization_fabric_plan(problem, max_variables_per_shard=2)

    first = build_compute_jobs(plan)
    second = build_compute_jobs(plan)

    assert first["status"] == "AVAILABLE"
    assert first["strategy"] == "independent_shards"
    assert first["job_count"] == 2
    assert [row["job_id"] for row in first["jobs"]] == [
        row["job_id"] for row in second["jobs"]
    ]
    assert {row["shard_key"] for row in first["jobs"]} == {"north", "south"}
    assert all(row["time_budget_ms"] == 1000 for row in first["jobs"])
    assert all(row["cost_budget_minor_units"] == 50 for row in first["jobs"])
    assert all(
        row["parent_problem_fingerprint"] == problem["problem_fingerprint"]
        for row in first["jobs"]
    )
    assert all(row["execution_authority"] == "none" for row in first["jobs"])


def test_independent_shard_results_reconcile_against_parent_problem():
    problem = _partitioned_problem()
    plan = build_optimization_fabric_plan(problem, max_variables_per_shard=2)
    batch = build_compute_jobs(plan)
    results = []
    for job in batch["jobs"]:
        solved = solve_exact_binary(job["problem"])
        results.append({
            "job_id": job["job_id"],
            "problem_fingerprint": job["problem_fingerprint"],
            "result": solved,
        })

    merged = reconcile_compute_results(plan, batch, results)

    assert merged["status"] == "AVAILABLE"
    assert merged["constraints_satisfied"] is True
    assert merged["selected_variables"] == ["x::a", "x::c"]
    assert merged["objective_value"] == 18.0
    assert merged["job_count"] == 2
    assert merged["execution_authority"] == "none"


def test_cross_partition_constraint_never_materializes_independent_jobs():
    problem = _partitioned_problem(cross_partition=True)
    plan = build_optimization_fabric_plan(problem, max_variables_per_shard=2)
    batch = build_compute_jobs(plan)

    assert plan["decomposition"]["strategy"] == "coordinator_decomposition_required"
    assert batch["status"] == "UNAVAILABLE"
    assert batch["reason"] == "global_coordinator_required"


def test_reconciliation_rejects_wrong_problem_fingerprint():
    problem = _partitioned_problem()
    plan = build_optimization_fabric_plan(problem, max_variables_per_shard=2)
    batch = build_compute_jobs(plan)
    results = []
    for index, job in enumerate(batch["jobs"]):
        solved = solve_exact_binary(job["problem"])
        results.append({
            "job_id": job["job_id"],
            "problem_fingerprint": "wrong" if index == 0 else job["problem_fingerprint"],
            "result": solved,
        })

    merged = reconcile_compute_results(plan, batch, results)

    assert merged["status"] == "UNAVAILABLE"
    assert merged["reason"] == "result_problem_fingerprint_mismatch"
