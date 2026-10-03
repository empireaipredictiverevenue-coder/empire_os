"""Provider-neutral optimization problem factory for EmpireOS.

Compiles domain optimization packets into one immutable, fingerprinted IR that
can be queued to classical, quantum-inspired, hybrid or QPU benchmark workers.

This module never executes a commercial action and never converts UNKNOWN to 0.
"""
from __future__ import annotations

from hashlib import sha256
import json
from math import ceil
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "empire.optimization.problem.v2"
DECOMPOSITION_SCHEMA_VERSION = "empire.optimization.decomposition.v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _finite_number(value: Any, name: str) -> float:
    if value is None:
        raise ValueError(f"{name} required")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be finite")
    return number


def _optional_nonnegative_number(value: Any, name: str) -> float | None:
    if value is None:
        return None
    number = _finite_number(value, name)
    if number < 0:
        raise ValueError(f"{name} must be nonnegative")
    return number


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_canonical(item) for item in value]
    return value


def _fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _canonical(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _evidence_refs(
    variables: Sequence[Mapping[str, Any]],
    extra: Sequence[Any],
) -> tuple[str, ...]:
    refs = {
        _text(ref)
        for ref in extra
        if _text(ref)
    }
    for row in variables:
        refs.update(
            _text(ref)
            for ref in (row.get("evidence_refs") or ())
            if _text(ref)
        )
    return tuple(sorted(refs))


def build_problem_ir(
    *,
    workload_key: str,
    workload_type: str,
    source_schema_version: str,
    variable_type: str,
    variables: Sequence[Mapping[str, Any]],
    objective: Mapping[str, Any],
    constraints: Sequence[Mapping[str, Any]],
    evidence_refs: Sequence[Any] = (),
    tenant_id: str | None = None,
    time_budget_ms: Any = None,
    cost_budget_minor_units: Any = None,
    representations: Sequence[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical optimization intermediate representation."""
    key = _text(workload_key)
    kind = _text(workload_type)
    source_schema = _text(source_schema_version)
    vtype = _text(variable_type).upper()
    if not key or not kind or not source_schema:
        raise ValueError("workload_key, workload_type and source_schema_version required")
    if vtype not in {"BINARY", "INTEGER", "CONTINUOUS", "MIXED"}:
        raise ValueError("unsupported variable_type")

    normalized_variables: list[dict[str, Any]] = []
    variable_names: set[str] = set()
    for raw in variables:
        if not isinstance(raw, Mapping):
            raise ValueError("variables must be mappings")
        row = dict(raw)
        variable = _text(row.get("variable"))
        if not variable:
            raise ValueError("variable name required")
        if variable in variable_names:
            raise ValueError(f"duplicate variable: {variable}")
        variable_names.add(variable)
        row["variable"] = variable
        normalized_variables.append(row)

    normalized_variables.sort(key=lambda row: str(row["variable"]))

    if not normalized_variables:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_variables",
            "workload_key": key,
            "workload_type": kind,
            "unknown_is_zero": False,
            "execution_authority": "none",
        }

    objective_packet = dict(objective or {})
    sense = _text(objective_packet.get("sense")).upper()
    if sense not in {"MAXIMIZE", "MINIMIZE"}:
        raise ValueError("objective sense must be MAXIMIZE or MINIMIZE")
    linear = dict(objective_packet.get("linear") or {})
    quadratic = dict(objective_packet.get("quadratic") or {})
    unknown_objective_variables = sorted(
        str(name)
        for name in linear
        if str(name) not in variable_names
    )
    if unknown_objective_variables:
        raise ValueError(
            "objective references unknown variables: "
            + ",".join(unknown_objective_variables)
        )
    for name, coefficient in linear.items():
        _finite_number(coefficient, f"objective coefficient {name}")
    for name, coefficient in quadratic.items():
        key = str(name)
        if "|" not in key:
            raise ValueError(
                f"quadratic key must be left|right: {key}"
            )
        left, right = key.split("|", 1)
        unknown = sorted({
            variable
            for variable in (left, right)
            if variable not in variable_names
        })
        if unknown:
            raise ValueError(
                "quadratic objective references unknown variables: "
                + ",".join(unknown)
            )
        _finite_number(coefficient, f"quadratic coefficient {name}")

    normalized_constraints: list[dict[str, Any]] = []
    for index, raw in enumerate(constraints):
        if not isinstance(raw, Mapping):
            raise ValueError("constraints must be mappings")
        packet = dict(raw)
        name = _text(packet.get("name")) or f"constraint::{index}"
        coefficients = dict(packet.get("coefficients") or {})
        unknown = sorted(
            str(variable)
            for variable in coefficients
            if str(variable) not in variable_names
        )
        if unknown:
            raise ValueError(
                f"constraint {name} references unknown variables: "
                + ",".join(unknown)
            )
        for variable, coefficient in coefficients.items():
            _finite_number(coefficient, f"constraint coefficient {variable}")
        constraint_sense = _text(packet.get("sense"))
        if constraint_sense not in {"<=", ">=", "==", "="}:
            raise ValueError(f"constraint {name} has unsupported sense")
        rhs = _finite_number(packet.get("rhs"), f"constraint rhs {name}")
        normalized_constraints.append({
            **packet,
            "name": name,
            "coefficients": coefficients,
            "sense": "==" if constraint_sense == "=" else constraint_sense,
            "rhs": rhs,
        })

    normalized_constraints.sort(key=lambda row: str(row["name"]))

    refs = _evidence_refs(normalized_variables, evidence_refs)
    if not refs:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "evidence_refs_required",
            "workload_key": key,
            "workload_type": kind,
            "unknown_is_zero": False,
            "execution_authority": "none",
        }

    time_budget = _optional_nonnegative_number(time_budget_ms, "time_budget_ms")
    cost_budget = _optional_nonnegative_number(
        cost_budget_minor_units,
        "cost_budget_minor_units",
    )
    reps = tuple(sorted({
        _text(value).upper()
        for value in representations
        if _text(value)
    }))

    semantic_payload = {
        "workload_key": key,
        "workload_type": kind,
        "tenant_id": _text(tenant_id) or None,
        "variable_type": vtype,
        "variables": normalized_variables,
        "objective": {
            **objective_packet,
            "sense": sense,
            "linear": linear,
            "quadratic": quadratic,
        },
        "constraints": normalized_constraints,
        "evidence_refs": refs,
        "time_budget_ms": time_budget,
        "cost_budget_minor_units": cost_budget,
        "representations": reps,
    }
    problem_fingerprint = _fingerprint(semantic_payload)

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "problem_fingerprint": problem_fingerprint,
        "workload_key": key,
        "workload_type": kind,
        "source_schema_version": source_schema,
        "tenant_id": _text(tenant_id) or None,
        "variable_type": vtype,
        "variable_count": len(normalized_variables),
        "constraint_count": len(normalized_constraints),
        "variables": normalized_variables,
        "objective": semantic_payload["objective"],
        "constraints": normalized_constraints,
        "evidence_refs": list(refs),
        "time_budget_ms": time_budget,
        "cost_budget_minor_units": cost_budget,
        "representations": list(reps),
        "metadata": dict(metadata or {}),
        "queueable": True,
        "prediction_only": True,
        "actual_revenue": False,
        "execution_authority": "none",
        "unknown_is_zero": False,
    }


def compute_problem_fingerprint(problem: Mapping[str, Any]) -> str:
    """Recompute the semantic fingerprint of an existing V2 IR packet."""
    variables = [
        dict(row)
        for row in (problem.get("variables") or ())
        if isinstance(row, Mapping)
    ]
    variables.sort(key=lambda row: _text(row.get("variable")))

    objective_packet = dict(problem.get("objective") or {})
    objective = {
        **objective_packet,
        "sense": _text(objective_packet.get("sense")).upper(),
        "linear": dict(objective_packet.get("linear") or {}),
        "quadratic": dict(objective_packet.get("quadratic") or {}),
    }

    constraints = []
    for index, raw in enumerate(problem.get("constraints") or ()):
        if not isinstance(raw, Mapping):
            continue
        packet = dict(raw)
        packet["name"] = (
            _text(packet.get("name")) or f"constraint::{index}"
        )
        packet["coefficients"] = dict(
            packet.get("coefficients") or {}
        )
        sense = _text(packet.get("sense"))
        packet["sense"] = "==" if sense == "=" else sense
        constraints.append(packet)
    constraints.sort(key=lambda row: str(row["name"]))

    refs = tuple(sorted({
        _text(ref)
        for ref in (problem.get("evidence_refs") or ())
        if _text(ref)
    }))
    reps = tuple(sorted({
        _text(value).upper()
        for value in (problem.get("representations") or ())
        if _text(value)
    }))

    payload = {
        "workload_key": _text(problem.get("workload_key")),
        "workload_type": _text(problem.get("workload_type")),
        "tenant_id": _text(problem.get("tenant_id")) or None,
        "variable_type": _text(problem.get("variable_type")).upper(),
        "variables": variables,
        "objective": objective,
        "constraints": constraints,
        "evidence_refs": refs,
        "time_budget_ms": problem.get("time_budget_ms"),
        "cost_budget_minor_units": problem.get(
            "cost_budget_minor_units"
        ),
        "representations": reps,
    }
    return _fingerprint(payload)


def validate_problem_integrity(
    problem: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed when a supposedly immutable optimization IR was mutated."""
    if _text(problem.get("status")).upper() != "AVAILABLE":
        return {
            "schema_version": "empire.optimization.problem-integrity.v1",
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "integrity_valid": False,
            "execution_authority": "none",
        }

    observed = _text(problem.get("problem_fingerprint"))
    blockers: list[str] = []
    if not observed:
        blockers.append("problem_fingerprint_missing")

    try:
        expected = compute_problem_fingerprint(problem)
    except (TypeError, ValueError) as exc:
        return {
            "schema_version": "empire.optimization.problem-integrity.v1",
            "status": "UNAVAILABLE",
            "reason": "problem_fingerprint_recompute_failed",
            "detail": str(exc),
            "integrity_valid": False,
            "execution_authority": "none",
        }

    if observed and observed != expected:
        blockers.append("problem_fingerprint_mismatch")

    variables = [
        row
        for row in (problem.get("variables") or ())
        if isinstance(row, Mapping)
    ]
    constraints = [
        row
        for row in (problem.get("constraints") or ())
        if isinstance(row, Mapping)
    ]
    if problem.get("variable_count") != len(variables):
        blockers.append("variable_count_mismatch")
    if problem.get("constraint_count") != len(constraints):
        blockers.append("constraint_count_mismatch")
    if problem.get("execution_authority") != "none":
        blockers.append("execution_authority_not_none")
    if problem.get("actual_revenue") is not False:
        blockers.append("actual_revenue_truth_boundary_invalid")
    if problem.get("prediction_only") is not True:
        blockers.append("prediction_only_boundary_invalid")
    if problem.get("unknown_is_zero") is not False:
        blockers.append("unknown_semantics_invalid")
    if problem.get("queueable") is not True:
        blockers.append("queueable_contract_invalid")

    if blockers:
        return {
            "schema_version": "empire.optimization.problem-integrity.v1",
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_integrity_failed",
            "integrity_valid": False,
            "observed_problem_fingerprint": observed or None,
            "expected_problem_fingerprint": expected,
            "blockers": sorted(set(blockers)),
            "execution_authority": "none",
        }

    return {
        "schema_version": "empire.optimization.problem-integrity.v1",
        "status": "AVAILABLE",
        "problem_fingerprint": expected,
        "integrity_valid": True,
        "execution_authority": "none",
    }


def compile_allocation_problem(
    problem: Mapping[str, Any],
    *,
    workload_key: str = "buyer_allocation",
    tenant_id: str | None = None,
    time_budget_ms: Any = None,
    cost_budget_minor_units: Any = None,
) -> dict[str, Any]:
    """Compile the existing governed buyer-allocation contract to V2 IR."""
    if _text(problem.get("status")).upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "source_problem_unavailable",
            "source_schema_version": problem.get("schema_version"),
            "execution_authority": "none",
        }

    variables = [
        dict(row)
        for row in (problem.get("variables") or ())
        if isinstance(row, Mapping)
    ]
    capacities = dict(problem.get("buyer_capacities") or {})
    unit_capacity = all(int(value) in (0, 1) for value in capacities.values())
    return build_problem_ir(
        workload_key=workload_key,
        workload_type="buyer_allocation",
        source_schema_version=_text(problem.get("schema_version"))
        or "empire.quantum_optimization.allocation.v1",
        variable_type="BINARY",
        variables=variables,
        objective=dict(problem.get("objective") or {}),
        constraints=[
            dict(row)
            for row in (problem.get("constraints") or ())
            if isinstance(row, Mapping)
        ],
        tenant_id=tenant_id,
        time_budget_ms=time_budget_ms,
        cost_budget_minor_units=cost_budget_minor_units,
        representations=("CQM", "QUBO") if unit_capacity else ("CQM",),
        metadata={
            "buyer_count": len(capacities),
            "unit_capacity_problem": unit_capacity,
            "source_execution_authority": problem.get("execution_authority"),
        },
    )


def compile_action_portfolio_problem(
    problem: Mapping[str, Any],
    *,
    workload_key: str = "predictive_action_portfolio",
    tenant_id: str | None = None,
    time_budget_ms: Any = None,
    cost_budget_minor_units: Any = None,
) -> dict[str, Any]:
    """Compile the existing Predictive Revenue NBA portfolio contract to V2 IR."""
    if _text(problem.get("status")).upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "source_problem_unavailable",
            "source_schema_version": problem.get("schema_version"),
            "execution_authority": "none",
        }

    variables = [
        dict(row)
        for row in (problem.get("variables") or ())
        if isinstance(row, Mapping)
    ]
    objective = {
        "sense": "MAXIMIZE",
        "linear": {
            _text(row.get("variable")): row.get("expected_incremental_value_cents")
            for row in variables
            if _text(row.get("variable"))
        },
        "quadratic": {},
        "objective_semantics": "maximize_expected_incremental_value_cents",
    }
    return build_problem_ir(
        workload_key=workload_key,
        workload_type="predictive_action_portfolio",
        source_schema_version=_text(problem.get("schema_version"))
        or "empire.action_portfolio_optimization.v1",
        variable_type="BINARY",
        variables=variables,
        objective=objective,
        constraints=[
            dict(row)
            for row in (problem.get("constraints") or ())
            if isinstance(row, Mapping)
        ],
        tenant_id=tenant_id,
        time_budget_ms=time_budget_ms,
        cost_budget_minor_units=cost_budget_minor_units,
        # The legacy action-portfolio QUBO requires independent constraint
        # encoding revalidation before V2 advertises it as a safe backend IR.
        representations=("CQM",),
        metadata={
            "budget_cents": problem.get("budget_cents"),
            "qubo_revalidation_required": True,
            "capacity_group_count": len(
                dict(problem.get("capacity_constraints") or {})
            ),
            "source_execution_authority": problem.get("execution_authority"),
        },
    )


def build_decomposition_plan(
    problem: Mapping[str, Any],
    *,
    max_variables_per_shard: int = 5000,
    partition_field: str = "partition_key",
) -> dict[str, Any]:
    """Plan horizontal decomposition without assuming constraints are local."""
    if max_variables_per_shard <= 0:
        raise ValueError("max_variables_per_shard must be positive")
    if _text(problem.get("status")).upper() != "AVAILABLE":
        return {
            "schema_version": DECOMPOSITION_SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "execution_authority": "none",
        }

    variables = [
        dict(row)
        for row in (problem.get("variables") or ())
        if isinstance(row, Mapping)
    ]
    count = len(variables)
    if count <= max_variables_per_shard:
        return {
            "schema_version": DECOMPOSITION_SCHEMA_VERSION,
            "status": "AVAILABLE",
            "problem_fingerprint": problem.get("problem_fingerprint"),
            "strategy": "single_worker",
            "variable_count": count,
            "planned_shard_count": 1,
            "independent_shard_execution_safe": True,
            "execution_authority": "none",
        }

    partition_by_variable: dict[str, str] = {}
    missing_partition: list[str] = []
    groups: dict[str, list[str]] = {}
    for row in variables:
        variable = _text(row.get("variable"))
        partition = _text(row.get(partition_field))
        if not partition:
            missing_partition.append(variable)
            continue
        partition_by_variable[variable] = partition
        groups.setdefault(partition, []).append(variable)

    cross_partition_constraints: list[str] = []
    global_constant_constraints: list[str] = []
    for index, raw in enumerate(problem.get("constraints") or ()):
        if not isinstance(raw, Mapping):
            continue
        coefficients = dict(raw.get("coefficients") or {})
        name = _text(raw.get("name")) or f"constraint::{index}"
        if not coefficients:
            global_constant_constraints.append(name)
            continue
        touched = {
            partition_by_variable[variable]
            for variable in coefficients
            if variable in partition_by_variable
        }
        if len(touched) > 1:
            cross_partition_constraints.append(name)

    cross_partition_quadratic_terms: list[str] = []
    unparsed_quadratic_terms: list[str] = []
    quadratic = dict(
        (problem.get("objective") or {}).get("quadratic") or {}
    )
    for raw_key in quadratic:
        key = str(raw_key)
        left, separator, right = key.partition("|")
        if not separator or not left or not right:
            unparsed_quadratic_terms.append(key)
            continue
        left_partition = partition_by_variable.get(left)
        right_partition = partition_by_variable.get(right)
        if (
            left_partition
            and right_partition
            and left_partition != right_partition
        ):
            cross_partition_quadratic_terms.append(key)

    group_too_large = sorted(
        key
        for key, members in groups.items()
        if len(members) > max_variables_per_shard
    )
    independent = not (
        missing_partition
        or cross_partition_constraints
        or global_constant_constraints
        or cross_partition_quadratic_terms
        or unparsed_quadratic_terms
        or group_too_large
    )
    if independent:
        return {
            "schema_version": DECOMPOSITION_SCHEMA_VERSION,
            "status": "AVAILABLE",
            "problem_fingerprint": problem.get("problem_fingerprint"),
            "strategy": "independent_shards",
            "variable_count": count,
            "planned_shard_count": len(groups),
            "partition_field": partition_field,
            "partitions": {
                key: sorted(members)
                for key, members in sorted(groups.items())
            },
            "independent_shard_execution_safe": True,
            "execution_authority": "none",
        }

    return {
        "schema_version": DECOMPOSITION_SCHEMA_VERSION,
        "status": "AVAILABLE",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "strategy": "coordinator_decomposition_required",
        "variable_count": count,
        "estimated_min_shards": ceil(count / max_variables_per_shard),
        "independent_shard_execution_safe": False,
        "blockers": {
            "variables_missing_partition_key": sorted(missing_partition),
            "cross_partition_constraints": sorted(cross_partition_constraints),
            "global_constant_constraints": sorted(global_constant_constraints),
            "cross_partition_quadratic_terms": sorted(
                cross_partition_quadratic_terms
            ),
            "unparsed_quadratic_terms": sorted(unparsed_quadratic_terms),
            "partitions_exceeding_shard_limit": group_too_large,
        },
        "global_constraint_reconciliation_required": True,
        "execution_authority": "none",
    }
