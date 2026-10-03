"""Empire-owned bounded QAOA statevector simulator for safe QUBOs.

V1 implements p=1 QAOA using the Python standard library only. It is a
classical simulator for quantum-style optimization research, never a QPU claim.
"""
from __future__ import annotations

from cmath import exp as cexp
from math import cos, pi, sin, sqrt
import time
from typing import Any, Mapping

from empire_os.solver_adapters.qubo_math import (
    energy as _energy,
    parse_quadratic as _parse_quadratic,
    source_objective as _source_objective,
    validate_constraints as _validate_constraints,
)


SCHEMA_VERSION = "empire.solver.empire_qaoa_simulator.v1"
DEFAULT_MAX_QUBITS = 10


def _assignment(index: int, variables: list[str]) -> dict[str, int]:
    return {
        variable: (index >> qubit) & 1
        for qubit, variable in enumerate(variables)
    }


def _apply_mixer(
    state: list[complex],
    *,
    beta: float,
    qubit_count: int,
) -> None:
    c = cos(beta)
    s = -1j * sin(beta)
    size = len(state)
    for qubit in range(qubit_count):
        mask = 1 << qubit
        for base in range(size):
            if base & mask:
                continue
            other = base | mask
            a0 = state[base]
            a1 = state[other]
            state[base] = c * a0 + s * a1
            state[other] = s * a0 + c * a1


def _simulate(
    *,
    normalized_costs: list[float],
    gamma: float,
    beta: float,
    qubit_count: int,
) -> tuple[list[complex], float]:
    size = 1 << qubit_count
    initial = 1.0 / sqrt(size)
    state = [
        complex(initial, 0.0) * cexp(-1j * gamma * cost)
        for cost in normalized_costs
    ]
    _apply_mixer(state, beta=beta, qubit_count=qubit_count)
    expectation = sum(
        (amplitude.real * amplitude.real + amplitude.imag * amplitude.imag)
        * cost
        for amplitude, cost in zip(state, normalized_costs, strict=True)
    )
    return state, float(expectation)


def solve_empire_qaoa_simulator(
    qubo: Mapping[str, Any],
    *,
    max_qubits: int = DEFAULT_MAX_QUBITS,
    gamma_steps: int = 11,
    beta_steps: int = 9,
    max_wall_clock_ms: float = 2000.0,
) -> dict[str, Any]:
    """Search p=1 QAOA angles and return the most probable feasible bitstring."""
    if str(qubo.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "qubo_unavailable",
            "execution_authority": "none",
        }
    if qubo.get("qaoa_ready") is not True:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "qubo_not_validated_for_qaoa",
            "execution_authority": "none",
        }
    if max_qubits <= 0:
        raise ValueError("max_qubits must be positive")
    if gamma_steps < 2 or beta_steps < 2:
        raise ValueError("gamma_steps and beta_steps must be >= 2")
    if max_wall_clock_ms <= 0:
        raise ValueError("max_wall_clock_ms must be positive")

    linear = {
        str(variable): float(coefficient)
        for variable, coefficient in dict(qubo.get("linear") or {}).items()
    }
    quadratic, _ = _parse_quadratic(
        dict(qubo.get("quadratic") or {})
    )
    variables = sorted({
        *linear,
        *(left for left, _ in quadratic),
        *(right for _, right in quadratic),
    })
    qubit_count = len(variables)
    if qubit_count == 0:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_qubo_variables",
            "execution_authority": "none",
        }
    if qubit_count > max_qubits:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "statevector_qubit_limit_exceeded",
            "qubit_count": qubit_count,
            "max_qubits": max_qubits,
            "execution_authority": "none",
        }

    size = 1 << qubit_count
    assignments = [_assignment(index, variables) for index in range(size)]
    costs = [
        _energy(row, linear, quadratic)
        for row in assignments
    ]
    energy_scale = max([abs(value) for value in costs] + [1.0])
    normalized_costs = [value / energy_scale for value in costs]

    started = time.perf_counter()
    deadline = started + (max_wall_clock_ms / 1000.0)
    best_state: list[complex] | None = None
    best_expectation: float | None = None
    best_gamma: float | None = None
    best_beta: float | None = None
    evaluations = 0
    timed_out = False

    for gi in range(gamma_steps):
        gamma = (2.0 * pi * gi) / (gamma_steps - 1)
        for bi in range(beta_steps):
            if time.perf_counter() >= deadline:
                timed_out = True
                break
            beta = (0.5 * pi * bi) / (beta_steps - 1)
            state, expectation = _simulate(
                normalized_costs=normalized_costs,
                gamma=gamma,
                beta=beta,
                qubit_count=qubit_count,
            )
            evaluations += 1
            if (
                best_expectation is None
                or expectation < best_expectation
            ):
                best_expectation = expectation
                best_state = state
                best_gamma = gamma
                best_beta = beta
        if timed_out:
            break

    if best_state is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "qaoa_angle_search_timed_out_before_evaluation",
            "execution_authority": "none",
        }

    ranked: list[tuple[float, float, int, dict[str, int]]] = []
    for index, amplitude in enumerate(best_state):
        probability = (
            amplitude.real * amplitude.real
            + amplitude.imag * amplitude.imag
        )
        assignment = assignments[index]
        feasible, _ = _validate_constraints(qubo, assignment)
        if not feasible:
            continue
        ranked.append(
            (
                -probability,
                costs[index],
                index,
                assignment,
            )
        )
    if not ranked:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "qaoa_distribution_has_no_feasible_state",
            "problem_fingerprint": qubo.get("problem_fingerprint"),
            "qubit_count": qubit_count,
            "execution_authority": "none",
        }

    ranked.sort(key=lambda row: (row[0], row[1], row[2]))
    negative_probability, qubo_energy, basis_index, selected = ranked[0]
    probability = -negative_probability
    source_value = _source_objective(qubo, selected)
    feasible, violations = _validate_constraints(qubo, selected)
    wall_clock_ms = (time.perf_counter() - started) * 1000.0
    statevector_norm = sum(
        amplitude.real * amplitude.real
        + amplitude.imag * amplitude.imag
        for amplitude in best_state
    )
    expected_qubo_energy = float(best_expectation) * energy_scale

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "solve_status": (
            "TIME_LIMIT_FEASIBLE" if timed_out else "SIMULATED_P1_FEASIBLE"
        ),
        "problem_fingerprint": qubo.get("problem_fingerprint"),
        "solver": "empire_qaoa_simulator",
        "solver_family": "empire_quantum_qaoa_statevector_simulator",
        "provider": "empire_os",
        "hardware_class": "cpu_statevector_simulator",
        "assignment": selected,
        "selected_variables": sorted(
            variable
            for variable, value in selected.items()
            if value == 1
        ),
        "selected_count": sum(selected.values()),
        "objective_value": round(float(source_value), 8),
        "qubo_energy": round(float(qubo_energy), 12),
        "constraints_satisfied": feasible,
        "constraint_violation_count": len(violations),
        "constraint_violations": violations,
        "qubit_count": qubit_count,
        "statevector_size": size,
        "statevector_dimension": size,
        "statevector_norm": round(statevector_norm, 12),
        "qaoa_depth": 1,
        "best_gamma": round(float(best_gamma), 12),
        "best_beta": round(float(best_beta), 12),
        "normalized_expected_energy": round(
            float(best_expectation), 12
        ),
        "expected_qubo_energy": round(
            expected_qubo_energy, 12
        ),
        "selected_state_probability": round(probability, 12),
        "angle_evaluations": evaluations,
        "gamma_steps": gamma_steps,
        "beta_steps": beta_steps,
        "timed_out": timed_out,
        "wall_clock_ms": round(wall_clock_ms, 6),
        "statevector_exact_simulation": True,
        "quantum_simulator": True,
        "quantum_hardware_used": False,
        "real_qpu": False,
        "qpu_called": False,
        "external_solver_called": False,
        "third_party_runtime_dependency": False,
        "benchmark_only": True,
        "prediction_only": True,
        "actual_revenue": False,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }
