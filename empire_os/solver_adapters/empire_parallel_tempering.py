"""Empire-owned parallel tempering solver for validated QUBO packets.

Pure Python. Multiple replicas explore the QUBO energy landscape at different
temperatures and exchange states using the Metropolis replica-exchange rule.
No provider SDK, network service or QPU is used.
"""
from __future__ import annotations

from math import exp
import random
import time
from typing import Any, Mapping

from empire_os.solver_adapters.qubo_math import (
    energy as _energy,
    parse_quadratic as _parse_quadratic,
    source_objective as _source_objective,
    validate_constraints as _validate_constraints,
)


SCHEMA_VERSION = "empire.solver.empire_parallel_tempering.v1"


def solve_empire_parallel_tempering(
    qubo: Mapping[str, Any],
    *,
    replica_count: int = 8,
    rounds: int = 120,
    sweeps_per_round: int = 2,
    seed: int = 1729,
    max_wall_clock_ms: float = 2000.0,
) -> dict[str, Any]:
    """Run bounded replica-exchange Monte Carlo on one safe QUBO."""
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
            "reason": "qubo_not_validated_for_empire_parallel_tempering",
            "execution_authority": "none",
        }
    if replica_count < 2:
        raise ValueError("replica_count must be >= 2")
    if rounds <= 0 or sweeps_per_round <= 0:
        raise ValueError("rounds and sweeps_per_round must be positive")
    if max_wall_clock_ms <= 0:
        raise ValueError("max_wall_clock_ms must be positive")

    linear = {
        str(variable): float(coefficient)
        for variable, coefficient in dict(qubo.get("linear") or {}).items()
    }
    quadratic, adjacency = _parse_quadratic(
        dict(qubo.get("quadratic") or {})
    )
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

    magnitude = max(
        [abs(value) for value in linear.values()]
        + [abs(value) for value in quadratic.values()]
        + [1.0]
    )
    low = max(1e-6, 0.01 * magnitude)
    high = max(low * 2.0, 5.0 * magnitude)
    ratio = (high / low) ** (1.0 / (replica_count - 1))
    temperatures = [low * (ratio ** index) for index in range(replica_count)]

    rng = random.Random(int(seed))
    states: list[dict[str, int]] = []
    energies: list[float] = []
    for replica in range(replica_count):
        if replica == 0:
            state = {variable: 0 for variable in variables}
        else:
            state = {
                variable: rng.randint(0, 1)
                for variable in variables
            }
        states.append(state)
        energies.append(_energy(state, linear, quadratic))

    started = time.perf_counter()
    deadline = started + (max_wall_clock_ms / 1000.0)
    local_proposals = 0
    local_accepts = 0
    swap_proposals = 0
    swap_accepts = 0
    rounds_completed = 0
    timed_out = False

    best_assignment: dict[str, int] | None = None
    best_energy: float | None = None
    best_source_value: float | None = None
    source_sense = str(
        dict(qubo.get("source_objective") or {}).get("sense") or ""
    ).upper()

    def consider(state: Mapping[str, int], energy: float) -> None:
        nonlocal best_assignment, best_energy, best_source_value
        feasible, _ = _validate_constraints(qubo, state)
        if not feasible:
            return
        source_value = _source_objective(qubo, state)
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
            best_assignment = dict(state)
            best_energy = float(energy)
            best_source_value = float(source_value)

    for state, energy in zip(states, energies, strict=True):
        consider(state, energy)

    for round_index in range(rounds):
        if time.perf_counter() >= deadline:
            timed_out = True
            break

        for replica, temperature in enumerate(temperatures):
            state = states[replica]
            energy = energies[replica]
            for _ in range(sweeps_per_round):
                order = list(variables)
                rng.shuffle(order)
                for variable in order:
                    if time.perf_counter() >= deadline:
                        timed_out = True
                        break
                    local_proposals += 1
                    current = state[variable]
                    # Compute exact delta without external numeric libraries.
                    state[variable] = 1 - current
                    candidate_energy = _energy(state, linear, quadratic)
                    delta = candidate_energy - energy
                    accept = (
                        delta <= 0
                        or rng.random() < exp(
                            -delta / max(temperature, 1e-12)
                        )
                    )
                    if accept:
                        energy = candidate_energy
                        local_accepts += 1
                    else:
                        state[variable] = current
                if timed_out:
                    break
            energies[replica] = energy
            consider(state, energy)
            if timed_out:
                break
        if timed_out:
            break

        # Alternate even/odd swap boundaries to improve mixing.
        start = round_index % 2
        for left in range(start, replica_count - 1, 2):
            right = left + 1
            swap_proposals += 1
            e_left = energies[left]
            e_right = energies[right]
            beta_left = 1.0 / max(temperatures[left], 1e-12)
            beta_right = 1.0 / max(temperatures[right], 1e-12)
            exponent = (beta_left - beta_right) * (e_left - e_right)
            accept_swap = (
                exponent >= 0
                or rng.random() < exp(max(-700.0, exponent))
            )
            if accept_swap:
                states[left], states[right] = states[right], states[left]
                energies[left], energies[right] = e_right, e_left
                swap_accepts += 1

        rounds_completed += 1

    wall_clock_ms = (time.perf_counter() - started) * 1000.0
    if best_assignment is None or best_source_value is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_feasible_replica_observed",
            "problem_fingerprint": qubo.get("problem_fingerprint"),
            "solver": "empire_parallel_tempering",
            "solver_family": "empire_quantum_inspired_parallel_tempering",
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
        "solver": "empire_parallel_tempering",
        "solver_family": "empire_quantum_inspired_parallel_tempering",
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
        "replica_count": replica_count,
        "temperatures": [round(value, 12) for value in temperatures],
        "rounds_requested": rounds,
        "rounds_completed": rounds_completed,
        "sweeps_per_round": sweeps_per_round,
        "seed": int(seed),
        "local_move_acceptance_rate": (
            round(local_accepts / local_proposals, 8)
            if local_proposals else 0.0
        ),
        "replica_swap_acceptance_rate": (
            round(swap_accepts / swap_proposals, 8)
            if swap_proposals else 0.0
        ),
        "timed_out": timed_out,
        "wall_clock_ms": round(wall_clock_ms, 6),
        "compute_cost_minor_units": None,
        "compute_cost_known": False,
        "stochastic_solver": True,
        "replica_exchange": True,
        "swap_attempts": swap_proposals,
        "accepted_swaps": swap_accepts,
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
