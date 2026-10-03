"""Empire-owned tabu search for validated QUBO packets.

Pure Python. Uses short-term move memory, aspiration against the global best,
multi-start diversification, and source-constraint validation. No provider,
network solver, or third-party runtime is used.
"""
from __future__ import annotations

import random
import time
from typing import Any, Mapping

from empire_os.solver_adapters.empire_annealing import (
    _energy,
    _parse_quadratic,
    _source_objective,
    _validate_constraints,
)


SCHEMA_VERSION = "empire.solver.empire_tabu.v1"


def solve_empire_tabu(
    qubo: Mapping[str, Any],
    *,
    iterations: int = 2000,
    tabu_tenure: int = 11,
    restart_interval: int = 250,
    seed: int = 1729,
    max_wall_clock_ms: float = 2000.0,
) -> dict[str, Any]:
    """Run bounded tabu search on one validated Empire QUBO."""
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
            "reason": "qubo_not_validated_for_empire_tabu",
            "execution_authority": "none",
        }
    if iterations <= 0 or tabu_tenure <= 0 or restart_interval <= 0:
        raise ValueError(
            "iterations, tabu_tenure and restart_interval must be positive"
        )
    if max_wall_clock_ms <= 0:
        raise ValueError("max_wall_clock_ms must be positive")

    linear = {
        str(variable): float(coefficient)
        for variable, coefficient in dict(qubo.get("linear") or {}).items()
    }
    quadratic, _ = _parse_quadratic(dict(qubo.get("quadratic") or {}))
    variables = sorted({
        *linear,
        *(left for left, _ in quadratic),
        *(right for _, right in quadratic),
    })
    if not variables:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_qubo_variables",
            "execution_authority": "none",
        }

    rng = random.Random(int(seed))
    state = {variable: 0 for variable in variables}
    energy = _energy(state, linear, quadratic)
    tabu_until: dict[str, int] = {}

    best_assignment: dict[str, int] | None = None
    best_energy: float | None = None
    best_source_value: float | None = None
    source_sense = str(
        dict(qubo.get("source_objective") or {}).get("sense") or ""
    ).upper()

    def consider(candidate: Mapping[str, int], candidate_energy: float) -> None:
        nonlocal best_assignment, best_energy, best_source_value
        feasible, _ = _validate_constraints(qubo, candidate)
        if not feasible:
            return
        source_value = _source_objective(qubo, candidate)
        better = (
            best_assignment is None
            or best_energy is None
            or candidate_energy < best_energy - 1e-12
            or (
                abs(candidate_energy - best_energy) <= 1e-12
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
            best_assignment = dict(candidate)
            best_energy = float(candidate_energy)
            best_source_value = float(source_value)

    consider(state, energy)
    started = time.perf_counter()
    deadline = started + max_wall_clock_ms / 1000.0
    iterations_completed = 0
    restart_count = 0
    aspiration_count = 0
    timed_out = False

    for iteration in range(iterations):
        if time.perf_counter() >= deadline:
            timed_out = True
            break

        if iteration and iteration % restart_interval == 0:
            state = {
                variable: rng.randint(0, 1)
                for variable in variables
            }
            energy = _energy(state, linear, quadratic)
            tabu_until.clear()
            restart_count += 1
            consider(state, energy)

        moves: list[tuple[float, str, dict[str, int]]] = []
        for variable in variables:
            candidate = dict(state)
            candidate[variable] = 1 - candidate[variable]
            candidate_energy = _energy(candidate, linear, quadratic)
            is_tabu = tabu_until.get(variable, -1) > iteration
            aspiration = (
                best_energy is None
                or candidate_energy < best_energy - 1e-12
            )
            if is_tabu and not aspiration:
                continue
            if is_tabu and aspiration:
                aspiration_count += 1
            moves.append((candidate_energy, variable, candidate))

        if not moves:
            tabu_until.clear()
            continue

        moves.sort(key=lambda row: (row[0], row[1]))
        energy, moved_variable, state = moves[0]
        tabu_until[moved_variable] = iteration + tabu_tenure
        consider(state, energy)
        iterations_completed += 1

    wall_clock_ms = (time.perf_counter() - started) * 1000.0
    if best_assignment is None or best_source_value is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_feasible_tabu_state_observed",
            "problem_fingerprint": qubo.get("problem_fingerprint"),
            "solver": "empire_tabu",
            "solver_family": "empire_quantum_inspired_tabu",
            "wall_clock_ms": round(wall_clock_ms, 6),
            "qpu_called": False,
            "external_solver_called": False,
            "execution_authority": "none",
        }

    feasible, violations = _validate_constraints(qubo, best_assignment)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "solve_status": (
            "TIME_LIMIT_FEASIBLE" if timed_out else "HEURISTIC_FEASIBLE"
        ),
        "problem_fingerprint": qubo.get("problem_fingerprint"),
        "solver": "empire_tabu",
        "solver_family": "empire_quantum_inspired_tabu",
        "provider": "empire_os",
        "hardware_class": "cpu",
        "assignment": best_assignment,
        "selected_variables": sorted(
            variable
            for variable, value in best_assignment.items()
            if value == 1
        ),
        "selected_count": sum(best_assignment.values()),
        "objective_value": round(best_source_value, 8),
        "qubo_energy": round(float(best_energy), 12),
        "constraints_satisfied": feasible,
        "constraint_violation_count": len(violations),
        "constraint_violations": violations,
        "iterations_requested": int(iterations),
        "iterations_completed": iterations_completed,
        "tabu_tenure": int(tabu_tenure),
        "restart_interval": int(restart_interval),
        "restart_count": restart_count,
        "aspiration_count": aspiration_count,
        "seed": int(seed),
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
