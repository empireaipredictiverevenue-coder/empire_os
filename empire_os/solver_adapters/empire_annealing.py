"""Empire-owned simulated annealing engine for validated QUBO packets.

Pure Python. No D-Wave, Qiskit, cloud provider or external solver dependency.
The engine is stochastic but reproducible under a fixed seed and always
revalidates source constraints before accepting a candidate.
"""
from __future__ import annotations

from math import exp
import random
import time
from typing import Any, Mapping


SCHEMA_VERSION = "empire.solver.empire_annealing.v1"


from empire_os.solver_adapters.qubo_math import (
    energy as _energy,
    flip_delta as _flip_delta,
    number as _number,
    parse_quadratic as _parse_quadratic,
    source_objective as _source_objective,
    source_sense as _source_sense,
    text as _text,
    validate_constraints as _validate_constraints,
    variable_order as _variable_order,
)


def solve_empire_annealing(
    qubo: Mapping[str, Any],
    *,
    num_reads: int = 64,
    sweeps_per_read: int = 800,
    seed: int = 1729,
    max_wall_clock_ms: float = 2000.0,
) -> dict[str, Any]:
    """Run Empire-owned bounded simulated annealing against a validated QUBO."""
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
            "reason": "qubo_not_validated_for_empire_annealing",
            "execution_authority": "none",
        }
    if num_reads <= 0 or sweeps_per_read <= 0:
        raise ValueError("num_reads and sweeps_per_read must be positive")
    if max_wall_clock_ms <= 0:
        raise ValueError("max_wall_clock_ms must be positive")

    try:
        linear = {
            str(variable): _number(
                coefficient,
                f"linear:{variable}",
            )
            for variable, coefficient in dict(
                qubo.get("linear") or {}
            ).items()
        }
        quadratic, adjacency = _parse_quadratic(
            dict(qubo.get("quadratic") or {})
        )
    except ValueError as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "invalid_qubo",
            "detail": str(exc),
            "execution_authority": "none",
        }

    variables = _variable_order(linear, quadratic)
    if not variables:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_qubo_variables",
            "execution_authority": "none",
        }

    scale = max(
        [abs(value) for value in linear.values()]
        + [abs(value) for value in quadratic.values()]
        + [1.0]
    )
    start_temperature = max(1e-6, 2.0 * scale)
    end_temperature = max(1e-9, 0.001 * scale)
    cooling_ratio = (
        (end_temperature / start_temperature)
        ** (1.0 / max(1, sweeps_per_read - 1))
    )

    rng = random.Random(int(seed))
    started = time.perf_counter()
    deadline = started + (max_wall_clock_ms / 1000.0)

    best_assignment: dict[str, int] | None = None
    best_energy: float | None = None
    best_source_value: float | None = None
    best_violations: list[dict[str, Any]] = []
    reads_completed = 0
    accepted_moves = 0
    proposed_moves = 0
    timed_out = False

    source_sense = _source_sense(qubo)

    for read_index in range(num_reads):
        if time.perf_counter() >= deadline:
            timed_out = True
            break

        if read_index == 0:
            assignment = {variable: 0 for variable in variables}
        else:
            assignment = {
                variable: rng.randint(0, 1)
                for variable in variables
            }

        energy = _energy(assignment, linear, quadratic)
        temperature = start_temperature

        for _ in range(sweeps_per_read):
            if time.perf_counter() >= deadline:
                timed_out = True
                break
            order = list(variables)
            rng.shuffle(order)
            for variable in order:
                proposed_moves += 1
                delta = _flip_delta(
                    variable,
                    assignment,
                    linear,
                    adjacency,
                )
                accept = (
                    delta <= 0
                    or rng.random() < exp(-delta / max(temperature, 1e-12))
                )
                if accept:
                    assignment[variable] = 1 - assignment[variable]
                    energy += delta
                    accepted_moves += 1
            temperature *= cooling_ratio

        feasible, violations = _validate_constraints(
            qubo,
            assignment,
        )
        if feasible:
            source_value = _source_objective(qubo, assignment)
            better = (
                best_assignment is None
                or best_energy is None
                or energy < best_energy - 1e-12
                or (
                    abs(energy - best_energy) <= 1e-12
                    and best_source_value is not None
                    and (
                        (
                            source_sense == "MAXIMIZE"
                            and source_value > best_source_value
                        )
                        or (
                            source_sense == "MINIMIZE"
                            and source_value < best_source_value
                        )
                    )
                )
            )
            if better:
                best_assignment = dict(assignment)
                best_energy = energy
                best_source_value = source_value
                best_violations = violations

        reads_completed += 1
        if timed_out:
            break

    wall_clock_ms = (time.perf_counter() - started) * 1000.0

    if best_assignment is None or best_source_value is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_feasible_sample_observed",
            "problem_fingerprint": qubo.get("problem_fingerprint"),
            "solver": "empire_annealing",
            "solver_family": "empire_quantum_inspired_annealing",
            "reads_completed": reads_completed,
            "timed_out": timed_out,
            "wall_clock_ms": round(wall_clock_ms, 6),
            "qpu_called": False,
            "external_solver_called": False,
            "execution_authority": "none",
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "solve_status": (
            "TIME_LIMIT_FEASIBLE"
            if timed_out
            else "HEURISTIC_FEASIBLE"
        ),
        "problem_fingerprint": qubo.get("problem_fingerprint"),
        "solver": "empire_annealing",
        "solver_family": "empire_quantum_inspired_annealing",
        "provider": "empire_os",
        "hardware_class": "cpu",
        "assignment": best_assignment,
        "selected_variables": sorted(
            variable
            for variable, value in best_assignment.items()
            if value == 1
        ),
        "selected_count": sum(best_assignment.values()),
        "objective_value": round(float(best_source_value), 8),
        "qubo_energy": round(float(best_energy), 12),
        "constraints_satisfied": not best_violations,
        "constraint_violation_count": len(best_violations),
        "constraint_violations": best_violations,
        "num_reads_requested": int(num_reads),
        "reads_completed": reads_completed,
        "sweeps_per_read": int(sweeps_per_read),
        "seed": int(seed),
        "accepted_moves": accepted_moves,
        "proposed_moves": proposed_moves,
        "acceptance_rate": (
            round(accepted_moves / proposed_moves, 8)
            if proposed_moves
            else 0.0
        ),
        "timed_out": timed_out,
        "wall_clock_ms": round(wall_clock_ms, 6),
        "compute_cost_minor_units": None,
        "compute_cost_known": False,
        "stochastic_solver": True,
        "external": False,
        "external_solver_called": False,
        "qpu_called": False,
        "third_party_runtime_dependency": False,
        "prediction_only": True,
        "actual_revenue": False,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }
