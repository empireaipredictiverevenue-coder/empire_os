"""Local D-Wave-compatible quantum-inspired solver adapters.

No Leap credentials or QPU are used here. V1 runs the open-source
dwave-samplers SimulatedAnnealingSampler against a pre-validated QUBO.
"""
from __future__ import annotations

import time
from typing import Any, Mapping


SCHEMA_VERSION = "empire.solver_adapter.dwave_local.v1"


def _load_runtime():
    try:
        import dimod
        from dwave.samplers import SimulatedAnnealingSampler
    except ImportError:
        return None, None
    return dimod, SimulatedAnnealingSampler


def _source_objective_value(
    qubo: Mapping[str, Any],
    assignment: Mapping[str, int],
) -> float:
    objective = dict(qubo.get("source_objective") or {})
    linear = dict(objective.get("linear") or {})
    value = sum(
        float(coefficient) * int(assignment.get(str(variable), 0))
        for variable, coefficient in linear.items()
    )
    return value


def _validate_constraints(
    qubo: Mapping[str, Any],
    assignment: Mapping[str, int],
) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    for raw in qubo.get("source_constraints") or ():
        if not isinstance(raw, Mapping):
            continue
        coefficients = dict(raw.get("coefficients") or {})
        lhs = sum(
            float(coefficient) * int(assignment.get(str(variable), 0))
            for variable, coefficient in coefficients.items()
        )
        rhs = float(raw.get("rhs"))
        sense = str(raw.get("sense") or "")
        ok = sense == "<=" and lhs <= rhs + 1e-9
        if not ok:
            violations.append({
                "constraint": raw.get("name"),
                "lhs": lhs,
                "sense": sense,
                "rhs": rhs,
            })
    return {
        "constraints_satisfied": not violations,
        "constraint_violation_count": len(violations),
        "constraint_violations": violations,
    }


def solve_simulated_annealing(
    qubo: Mapping[str, Any],
    *,
    num_reads: int = 100,
    num_sweeps: int = 1000,
    seed: int = 1729,
) -> dict[str, Any]:
    """Run a reproducible local simulated-annealing QUBO benchmark."""
    if str(qubo.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "qubo_unavailable",
            "execution_authority": "none",
        }
    if qubo.get("local_bqm_ready") is not True:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "qubo_not_validated_for_local_bqm",
            "execution_authority": "none",
        }
    if num_reads <= 0 or num_sweeps <= 0:
        raise ValueError("num_reads and num_sweeps must be positive")

    dimod, sampler_type = _load_runtime()
    if dimod is None or sampler_type is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "dwave_local_runtime_not_installed",
            "external_solver_called": False,
            "execution_authority": "none",
        }

    linear = {
        str(variable): float(coefficient)
        for variable, coefficient in dict(qubo.get("linear") or {}).items()
    }
    quadratic: dict[tuple[str, str], float] = {}
    for key, coefficient in dict(qubo.get("quadratic") or {}).items():
        left, separator, right = str(key).partition("|")
        if not separator or not left or not right:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "UNAVAILABLE",
                "reason": "invalid_qubo_quadratic_key",
                "execution_authority": "none",
            }
        quadratic[(left, right)] = float(coefficient)

    bqm = dimod.BinaryQuadraticModel(
        linear,
        quadratic,
        0.0,
        dimod.BINARY,
    )
    sampler = sampler_type()
    started = time.perf_counter()
    sampleset = sampler.sample(
        bqm,
        num_reads=int(num_reads),
        num_sweeps=int(num_sweeps),
        seed=int(seed),
    )
    wall_clock_ms = (time.perf_counter() - started) * 1000.0
    first = sampleset.first
    assignment = {
        str(variable): int(value)
        for variable, value in dict(first.sample).items()
    }
    validation = _validate_constraints(qubo, assignment)
    source_value = _source_objective_value(qubo, assignment)

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "problem_fingerprint": qubo.get("problem_fingerprint"),
        "solver": "dwave_local_simulated_annealing",
        "solver_family": "quantum_inspired_simulated_annealing",
        "provider": "dwave_open_source_local",
        "hardware_class": "cpu",
        "assignment": assignment,
        "selected_variables": sorted(
            variable
            for variable, value in assignment.items()
            if value == 1
        ),
        "objective_value": round(source_value, 8),
        "qubo_energy": round(float(first.energy), 12),
        **validation,
        "wall_clock_ms": round(wall_clock_ms, 6),
        "num_reads": int(num_reads),
        "num_sweeps": int(num_sweeps),
        "seed": int(seed),
        "stochastic_solver": True,
        "compute_cost_minor_units": None,
        "compute_cost_known": False,
        "external": False,
        "external_solver_called": False,
        "qpu_called": False,
        "prediction_only": True,
        "actual_revenue": False,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }
