"""Queue-safe compute job protocol for Empire Optimization Fabric V2.

Jobs are immutable, deterministic and tenant-scoped. Independent sharding is
allowed only when the decomposition planner proves there are no cross-shard
constraints or quadratic interactions. No job grants business execution
authority.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence

from empire_os.optimization_problem_factory import build_problem_ir


SCHEMA_VERSION = "empire.optimization.compute-job.v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _job_id(parent_fingerprint: str, shard_key: str, solver: str) -> str:
    raw = f"{parent_fingerprint}|{shard_key}|{solver}".encode("utf-8")
    return "optjob_" + sha256(raw).hexdigest()[:24]


def _subproblem(
    problem: Mapping[str, Any],
    *,
    shard_key: str,
    variable_names: Sequence[str],
    shard_count: int,
) -> dict[str, Any]:
    allowed = set(variable_names)
    variables = [
        dict(row)
        for row in (problem.get("variables") or ())
        if isinstance(row, Mapping)
        and _text(row.get("variable")) in allowed
    ]
    objective = dict(problem.get("objective") or {})
    linear = {
        str(variable): coefficient
        for variable, coefficient in dict(objective.get("linear") or {}).items()
        if str(variable) in allowed
    }
    quadratic = {}
    for key, coefficient in dict(objective.get("quadratic") or {}).items():
        raw = str(key)
        left, separator, right = raw.partition("|")
        if separator and left in allowed and right in allowed:
            quadratic[raw] = coefficient

    constraints: list[dict[str, Any]] = []
    for raw in problem.get("constraints") or ():
        if not isinstance(raw, Mapping):
            continue
        packet = dict(raw)
        coefficients = dict(packet.get("coefficients") or {})
        touched = set(map(str, coefficients)) & allowed
        if not touched:
            continue
        if set(map(str, coefficients)) - allowed:
            raise ValueError(
                "decomposition contract violated by cross-shard constraint"
            )
        constraints.append(packet)

    time_budget = problem.get("time_budget_ms")
    cost_budget = problem.get("cost_budget_minor_units")
    shard_time_budget = (
        float(time_budget) / shard_count
        if time_budget is not None
        else None
    )
    shard_cost_budget = (
        float(cost_budget) / shard_count
        if cost_budget is not None
        else None
    )

    return build_problem_ir(
        workload_key=f"{problem.get('workload_key')}::shard::{shard_key}",
        workload_type=str(problem.get("workload_type") or ""),
        source_schema_version=str(problem.get("source_schema_version") or ""),
        variable_type=str(problem.get("variable_type") or ""),
        variables=variables,
        objective={
            **objective,
            "linear": linear,
            "quadratic": quadratic,
        },
        constraints=constraints,
        evidence_refs=problem.get("evidence_refs") or (),
        tenant_id=problem.get("tenant_id"),
        time_budget_ms=shard_time_budget,
        cost_budget_minor_units=shard_cost_budget,
        representations=problem.get("representations") or (),
        metadata={
            **dict(problem.get("metadata") or {}),
            "parent_problem_fingerprint": problem.get("problem_fingerprint"),
            "shard_key": shard_key,
            "shard_count": shard_count,
        },
    )


def build_compute_jobs(
    fabric_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Materialize deterministic compute jobs from a safe fabric plan."""
    if str(fabric_plan.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "fabric_plan_unavailable",
            "execution_authority": "none",
        }
    if fabric_plan.get("solver_execution_ready") is not True:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "solver_execution_not_ready",
            "execution_authority": "none",
        }

    problem = fabric_plan.get("problem")
    decomposition = fabric_plan.get("decomposition")
    if not isinstance(problem, Mapping) or not isinstance(
        decomposition,
        Mapping,
    ):
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "problem_or_decomposition_missing",
            "execution_authority": "none",
        }

    parent_fingerprint = _text(problem.get("problem_fingerprint"))
    solver = _text(fabric_plan.get("primary_solver"))
    strategy = _text(decomposition.get("strategy"))
    if strategy == "coordinator_decomposition_required":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "global_coordinator_required",
            "problem_fingerprint": parent_fingerprint,
            "decomposition": dict(decomposition),
            "execution_authority": "none",
        }

    shards: list[tuple[str, dict[str, Any]]] = []
    if strategy == "single_worker":
        shards.append(("root", dict(problem)))
    elif (
        strategy == "independent_shards"
        and decomposition.get("independent_shard_execution_safe") is True
    ):
        partitions = dict(decomposition.get("partitions") or {})
        shard_count = len(partitions)
        if shard_count <= 0:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "UNAVAILABLE",
                "reason": "no_partitions",
                "execution_authority": "none",
            }
        for shard_key, variable_names in sorted(partitions.items()):
            shard = _subproblem(
                problem,
                shard_key=str(shard_key),
                variable_names=list(variable_names or ()),
                shard_count=shard_count,
            )
            if str(shard.get("status") or "").upper() != "AVAILABLE":
                return {
                    "schema_version": SCHEMA_VERSION,
                    "status": "UNAVAILABLE",
                    "reason": "shard_materialization_failed",
                    "shard_key": shard_key,
                    "shard": shard,
                    "execution_authority": "none",
                }
            shards.append((str(shard_key), shard))
    else:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "unsupported_or_unsafe_decomposition_strategy",
            "execution_authority": "none",
        }

    jobs = []
    for shard_key, shard in shards:
        jobs.append({
            "schema_version": SCHEMA_VERSION,
            "job_id": _job_id(parent_fingerprint, shard_key, solver),
            "parent_problem_fingerprint": parent_fingerprint,
            "problem_fingerprint": shard.get("problem_fingerprint"),
            "shard_key": shard_key,
            "tenant_id": shard.get("tenant_id"),
            "solver": solver,
            "queue_class": fabric_plan.get("solver_route", {}).get(
                "queue_class",
                fabric_plan.get("queue_class"),
            ),
            "time_budget_ms": shard.get("time_budget_ms"),
            "cost_budget_minor_units": shard.get(
                "cost_budget_minor_units"
            ),
            "problem": shard,
            "recommendation_only": True,
            "external_action_allowed": False,
            "production_promotion_allowed": False,
            "execution_authority": "none",
        })

    return {
        "schema_version": "empire.optimization.compute-batch.v1",
        "status": "AVAILABLE",
        "parent_problem_fingerprint": parent_fingerprint,
        "strategy": strategy,
        "job_count": len(jobs),
        "jobs": jobs,
        "aggregate_cost_budget_minor_units": problem.get(
            "cost_budget_minor_units"
        ),
        "aggregate_time_budget_ms": problem.get("time_budget_ms"),
        "parallel_execution_safe": (
            strategy == "independent_shards"
            or strategy == "single_worker"
        ),
        "external_action_allowed": False,
        "production_promotion_allowed": False,
        "execution_authority": "none",
    }


def _objective_value(
    problem: Mapping[str, Any],
    assignment: Mapping[str, int],
) -> float:
    objective = dict(problem.get("objective") or {})
    value = sum(
        float(coefficient) * int(assignment.get(str(variable), 0))
        for variable, coefficient in dict(
            objective.get("linear") or {}
        ).items()
    )
    for key, coefficient in dict(
        objective.get("quadratic") or {}
    ).items():
        left, separator, right = str(key).partition("|")
        if not separator:
            raise ValueError("unparsed quadratic objective term")
        value += (
            float(coefficient)
            * int(assignment.get(left, 0))
            * int(assignment.get(right, 0))
        )
    return value


def _validate_parent_constraints(
    problem: Mapping[str, Any],
    assignment: Mapping[str, int],
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for raw in problem.get("constraints") or ():
        if not isinstance(raw, Mapping):
            continue
        lhs = sum(
            float(coefficient)
            * int(assignment.get(str(variable), 0))
            for variable, coefficient in dict(
                raw.get("coefficients") or {}
            ).items()
        )
        rhs = float(raw.get("rhs"))
        sense = _text(raw.get("sense"))
        ok = (
            lhs <= rhs + 1e-9
            if sense == "<="
            else lhs >= rhs - 1e-9
            if sense == ">="
            else abs(lhs - rhs) <= 1e-9
            if sense in {"==", "="}
            else False
        )
        if not ok:
            violations.append({
                "constraint": raw.get("name"),
                "lhs": lhs,
                "sense": sense,
                "rhs": rhs,
            })
    return violations


def reconcile_compute_results(
    fabric_plan: Mapping[str, Any],
    batch: Mapping[str, Any],
    results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Reconcile independently solved shards back against the parent problem."""
    if (
        str(fabric_plan.get("status") or "").upper() != "AVAILABLE"
        or str(batch.get("status") or "").upper() != "AVAILABLE"
    ):
        return {
            "schema_version": "empire.optimization.reconciliation.v1",
            "status": "UNAVAILABLE",
            "reason": "fabric_or_batch_unavailable",
            "execution_authority": "none",
        }
    problem = fabric_plan.get("problem")
    if not isinstance(problem, Mapping):
        return {
            "schema_version": "empire.optimization.reconciliation.v1",
            "status": "UNAVAILABLE",
            "reason": "parent_problem_missing",
            "execution_authority": "none",
        }

    jobs = {
        str(job.get("job_id")): job
        for job in (batch.get("jobs") or ())
        if isinstance(job, Mapping)
    }
    result_by_job = {
        str(row.get("job_id")): row
        for row in results
        if isinstance(row, Mapping)
    }
    if set(jobs) != set(result_by_job):
        return {
            "schema_version": "empire.optimization.reconciliation.v1",
            "status": "UNAVAILABLE",
            "reason": "job_result_set_mismatch",
            "missing_job_ids": sorted(set(jobs) - set(result_by_job)),
            "unexpected_job_ids": sorted(set(result_by_job) - set(jobs)),
            "execution_authority": "none",
        }

    assignment: dict[str, int] = {}
    for job_id, job in jobs.items():
        envelope = result_by_job[job_id]
        if envelope.get("problem_fingerprint") != job.get(
            "problem_fingerprint"
        ):
            return {
                "schema_version": "empire.optimization.reconciliation.v1",
                "status": "UNAVAILABLE",
                "reason": "result_problem_fingerprint_mismatch",
                "job_id": job_id,
                "execution_authority": "none",
            }
        result = envelope.get("result")
        if not isinstance(result, Mapping):
            return {
                "schema_version": "empire.optimization.reconciliation.v1",
                "status": "UNAVAILABLE",
                "reason": "result_payload_missing",
                "job_id": job_id,
                "execution_authority": "none",
            }
        if (
            str(result.get("status") or "").upper() != "AVAILABLE"
            or result.get("constraints_satisfied") is not True
        ):
            return {
                "schema_version": "empire.optimization.reconciliation.v1",
                "status": "UNAVAILABLE",
                "reason": "shard_result_not_feasible",
                "job_id": job_id,
                "execution_authority": "none",
            }
        for variable, raw_value in dict(
            result.get("assignment") or {}
        ).items():
            variable = str(variable)
            if variable in assignment:
                return {
                    "schema_version": "empire.optimization.reconciliation.v1",
                    "status": "UNAVAILABLE",
                    "reason": "duplicate_variable_across_shards",
                    "variable": variable,
                    "execution_authority": "none",
                }
            assignment[variable] = int(raw_value)

    expected_variables = {
        _text(row.get("variable"))
        for row in (problem.get("variables") or ())
        if isinstance(row, Mapping)
    }
    if set(assignment) != expected_variables:
        return {
            "schema_version": "empire.optimization.reconciliation.v1",
            "status": "UNAVAILABLE",
            "reason": "reconciled_assignment_incomplete",
            "execution_authority": "none",
        }

    violations = _validate_parent_constraints(problem, assignment)
    objective = _objective_value(problem, assignment)
    return {
        "schema_version": "empire.optimization.reconciliation.v1",
        "status": "AVAILABLE" if not violations else "UNAVAILABLE",
        "reason": None if not violations else "parent_constraint_violation",
        "parent_problem_fingerprint": problem.get("problem_fingerprint"),
        "assignment": assignment,
        "selected_variables": sorted(
            variable
            for variable, value in assignment.items()
            if value == 1
        ),
        "objective_value": round(objective, 8),
        "constraints_satisfied": not violations,
        "constraint_violations": violations,
        "job_count": len(jobs),
        "recommendation_only": True,
        "external_action_performed": False,
        "production_promotion_ready": False,
        "execution_authority": "none",
    }
