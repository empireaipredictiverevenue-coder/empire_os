"""Quantum-ready constrained optimization primitives for EmpireOS.

The first production-relevant quantum use case is governed buyer allocation:
choose prospect->buyer assignments that maximize evidence-backed expected value
subject to one-allocation-per-prospect and verified buyer-capacity constraints.

This module always provides a classical reference path first. It also emits a
provider-neutral constrained quadratic model (CQM-style) and, where the
constraint structure is safely representable without invented slack/penalty
assumptions, a QUBO suitable for QAOA/annealing experiments.

No quantum provider is called here. No allocation is executed. Unknown
economics remain unknown rather than being replaced by match scores.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Any, Mapping, Sequence


MAX_EXACT_VARIABLES = 24
SCHEMA_VERSION = "empire.quantum_optimization.allocation.v1"


@dataclass(frozen=True)
class AllocationOption:
    prospect_id: str
    buyer_id: str
    expected_value_cents: float
    evidence_refs: tuple[str, ...]
    variable: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _nonnegative_number(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if number < 0:
        raise ValueError(f"{name} must be nonnegative")
    return number


def _capacity(value: Any, buyer_id: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"capacity for buyer {buyer_id} must be an integer"
        ) from exc
    if number < 0:
        raise ValueError(
            f"capacity for buyer {buyer_id} must be nonnegative"
        )
    return number


def _variable(prospect_id: str, buyer_id: str) -> str:
    return f"x::{prospect_id}::{buyer_id}"


def normalize_allocation_options(
    options: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Normalize only options with explicit expected-value evidence."""
    normalized: list[AllocationOption] = []
    blocked: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for raw in options:
        if not isinstance(raw, Mapping):
            continue
        prospect_id = _text(raw.get("prospect_id"))
        buyer_id = _text(raw.get("buyer_id"))
        missing: list[str] = []
        if not prospect_id:
            missing.append("prospect_id")
        if not buyer_id:
            missing.append("buyer_id")
        if raw.get("expected_value_cents") is None:
            missing.append("expected_value_cents")
        refs = tuple(
            dict.fromkeys(
                _text(ref)
                for ref in (raw.get("evidence_refs") or ())
                if _text(ref)
            )
        )
        if not refs:
            missing.append("evidence_refs")
        if missing:
            blocked.append({
                "prospect_id": prospect_id or None,
                "buyer_id": buyer_id or None,
                "missing_fields": missing,
                "reason": "unknown_allocation_economics_preserved",
            })
            continue

        key = (prospect_id, buyer_id)
        if key in seen:
            blocked.append({
                "prospect_id": prospect_id,
                "buyer_id": buyer_id,
                "missing_fields": [],
                "reason": "duplicate_assignment_option",
            })
            continue
        seen.add(key)

        normalized.append(
            AllocationOption(
                prospect_id=prospect_id,
                buyer_id=buyer_id,
                expected_value_cents=_nonnegative_number(
                    raw["expected_value_cents"],
                    "expected_value_cents",
                ),
                evidence_refs=refs,
                variable=_variable(prospect_id, buyer_id),
            )
        )

    return {
        "available": normalized,
        "blocked": blocked,
    }


def build_allocation_optimization_problem(
    *,
    options: Sequence[Mapping[str, Any]],
    buyer_capacities: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a provider-neutral binary constrained optimization problem."""
    normalized = normalize_allocation_options(options)
    rows: list[AllocationOption] = normalized["available"]
    blocked = normalized["blocked"]

    capacities = {
        _text(buyer_id): _capacity(value, _text(buyer_id))
        for buyer_id, value in dict(buyer_capacities or {}).items()
        if _text(buyer_id)
    }

    unknown_capacity_buyers = sorted({
        row.buyer_id
        for row in rows
        if row.buyer_id not in capacities
    })
    if unknown_capacity_buyers:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "buyer_capacity_unknown",
            "unknown_buyers": unknown_capacity_buyers,
            "blocked_options": blocked,
            "unknown_is_zero": False,
            "execution_authority": "none",
        }

    active = [
        row for row in rows
        if capacities[row.buyer_id] > 0
    ]

    by_prospect: dict[str, list[AllocationOption]] = {}
    by_buyer: dict[str, list[AllocationOption]] = {}
    for row in active:
        by_prospect.setdefault(row.prospect_id, []).append(row)
        by_buyer.setdefault(row.buyer_id, []).append(row)

    constraints: list[dict[str, Any]] = []
    for prospect_id, prospect_rows in sorted(by_prospect.items()):
        constraints.append({
            "name": f"prospect_once::{prospect_id}",
            "coefficients": {
                row.variable: 1
                for row in prospect_rows
            },
            "sense": "<=",
            "rhs": 1,
            "constraint_type": "hard",
        })
    for buyer_id, buyer_rows in sorted(by_buyer.items()):
        constraints.append({
            "name": f"buyer_capacity::{buyer_id}",
            "coefficients": {
                row.variable: 1
                for row in buyer_rows
            },
            "sense": "<=",
            "rhs": capacities[buyer_id],
            "constraint_type": "hard",
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE" if active else "UNAVAILABLE",
        "reason": None if active else "no_evidenced_allocatable_options",
        "variable_type": "BINARY",
        "variables": [row.as_dict() for row in active],
        "objective": {
            "sense": "MAXIMIZE",
            "linear": {
                row.variable: row.expected_value_cents
                for row in active
            },
            "quadratic": {},
            "objective_semantics": "maximize_expected_value_cents",
        },
        "constraints": constraints,
        "buyer_capacities": capacities,
        "blocked_options": blocked,
        "unknown_is_zero": False,
        "prediction_only": True,
        "actual_revenue": False,
        "allocation_execution": False,
        "execution_authority": "none",
    }


def solve_allocation_classical_exact(
    problem: Mapping[str, Any],
    *,
    max_variables: int = MAX_EXACT_VARIABLES,
) -> dict[str, Any]:
    """Exact reference solver for small allocation instances.

    This exists to benchmark any future quantum/hybrid backend. Quantum output
    must beat or match this reference on solution quality for small instances
    before it can claim value.
    """
    if str(problem.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": "empire.quantum_optimization.classical.v1",
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "execution_authority": "none",
        }

    variables = [
        row
        for row in (problem.get("variables") or [])
        if isinstance(row, Mapping)
    ]
    if len(variables) > max_variables:
        return {
            "schema_version": "empire.quantum_optimization.classical.v1",
            "status": "UNAVAILABLE",
            "reason": "exact_reference_variable_limit_exceeded",
            "variable_count": len(variables),
            "max_variables": max_variables,
            "execution_authority": "none",
        }

    capacities = {
        str(key): int(value)
        for key, value in dict(
            problem.get("buyer_capacities") or {}
        ).items()
    }
    prospect_ids = sorted({
        str(row["prospect_id"])
        for row in variables
    })
    options_by_prospect: dict[str, list[Mapping[str, Any]]] = {
        prospect_id: []
        for prospect_id in prospect_ids
    }
    for row in variables:
        options_by_prospect[str(row["prospect_id"])].append(row)

    best_value = 0.0
    best_rows: list[Mapping[str, Any]] = []
    explored = 0

    def search(
        index: int,
        used: dict[str, int],
        chosen: list[Mapping[str, Any]],
        value: float,
    ) -> None:
        nonlocal best_value, best_rows, explored
        if index >= len(prospect_ids):
            explored += 1
            signature = tuple(
                sorted(str(row["variable"]) for row in chosen)
            )
            best_signature = tuple(
                sorted(str(row["variable"]) for row in best_rows)
            )
            if (
                value > best_value
                or (
                    value == best_value
                    and signature < best_signature
                )
            ):
                best_value = value
                best_rows = list(chosen)
            return

        prospect_id = prospect_ids[index]
        search(index + 1, used, chosen, value)

        for row in options_by_prospect[prospect_id]:
            buyer_id = str(row["buyer_id"])
            current = used.get(buyer_id, 0)
            if current >= capacities.get(buyer_id, 0):
                continue
            used[buyer_id] = current + 1
            chosen.append(row)
            search(
                index + 1,
                used,
                chosen,
                value + float(row["expected_value_cents"]),
            )
            chosen.pop()
            if current:
                used[buyer_id] = current
            else:
                used.pop(buyer_id, None)

    search(0, {}, [], 0.0)

    return {
        "schema_version": "empire.quantum_optimization.classical.v1",
        "status": "AVAILABLE",
        "solver": "classical_exact_reference",
        "optimal_for_normalized_problem": True,
        "selected_assignments": [
            {
                "prospect_id": row["prospect_id"],
                "buyer_id": row["buyer_id"],
                "variable": row["variable"],
                "expected_value_cents": row[
                    "expected_value_cents"
                ],
                "evidence_refs": list(row.get("evidence_refs") or []),
            }
            for row in best_rows
        ],
        "selected_count": len(best_rows),
        "objective_value_cents": round(best_value, 4),
        "leaf_states_explored": explored,
        "prediction_only": True,
        "actual_revenue": False,
        "allocation_execution": False,
        "execution_authority": "none",
    }


def build_cqm_export(problem: Mapping[str, Any]) -> dict[str, Any]:
    """Export the normalized problem in a CQM-compatible contract."""
    if str(problem.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": "empire.quantum_optimization.cqm.v1",
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "execution_authority": "none",
        }
    return {
        "schema_version": "empire.quantum_optimization.cqm.v1",
        "status": "AVAILABLE",
        "model_type": "CONSTRAINED_QUADRATIC_MODEL",
        "variable_type": "BINARY",
        "objective": dict(problem.get("objective") or {}),
        "constraints": list(problem.get("constraints") or []),
        "backend_candidates": [
            "dwave_hybrid_cqm",
            "classical_mip_or_cp_sat",
        ],
        "external_solver_called": False,
        "execution_authority": "none",
    }


def build_qubo_export(
    problem: Mapping[str, Any],
    *,
    penalty_multiplier: float = 2.0,
) -> dict[str, Any]:
    """Create a safe direct QUBO only for unit-capacity allocation.

    General buyer capacities require slack-variable/penalty calibration. Until
    that is explicitly modeled, QAOA readiness remains unavailable rather than
    inventing a penalty formulation.
    """
    if str(problem.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": "empire.quantum_optimization.qubo.v1",
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "execution_authority": "none",
        }

    capacities = dict(problem.get("buyer_capacities") or {})
    non_unit = sorted(
        str(buyer_id)
        for buyer_id, capacity in capacities.items()
        if int(capacity) not in (0, 1)
    )
    if non_unit:
        return {
            "schema_version": "empire.quantum_optimization.qubo.v1",
            "status": "UNAVAILABLE",
            "reason": "general_capacity_requires_slack_encoding",
            "buyers_requiring_slack_encoding": non_unit,
            "qaoa_ready": False,
            "unknown_is_zero": False,
            "execution_authority": "none",
        }

    variables = [
        row
        for row in (problem.get("variables") or [])
        if isinstance(row, Mapping)
    ]
    if not variables:
        return {
            "schema_version": "empire.quantum_optimization.qubo.v1",
            "status": "UNAVAILABLE",
            "reason": "no_variables",
            "qaoa_ready": False,
            "execution_authority": "none",
        }

    values = [
        float(row["expected_value_cents"])
        for row in variables
    ]
    scale = max(max(values), 1.0)
    penalty = max(float(penalty_multiplier), 1.0)

    linear = {
        str(row["variable"]): -(
            float(row["expected_value_cents"]) / scale
        )
        for row in variables
    }
    quadratic: dict[str, float] = {}

    def add_pair(left: str, right: str, weight: float) -> None:
        a, b = sorted((left, right))
        key = f"{a}|{b}"
        quadratic[key] = quadratic.get(key, 0.0) + weight

    by_prospect: dict[str, list[str]] = {}
    by_buyer: dict[str, list[str]] = {}
    for row in variables:
        variable = str(row["variable"])
        by_prospect.setdefault(
            str(row["prospect_id"]), []
        ).append(variable)
        by_buyer.setdefault(
            str(row["buyer_id"]), []
        ).append(variable)

    for group in [*by_prospect.values(), *by_buyer.values()]:
        for left, right in combinations(sorted(group), 2):
            add_pair(left, right, penalty)

    return {
        "schema_version": "empire.quantum_optimization.qubo.v1",
        "status": "AVAILABLE",
        "model_type": "QUBO",
        "objective_sense": "MINIMIZE",
        "linear": {
            key: round(value, 12)
            for key, value in linear.items()
        },
        "quadratic": {
            key: round(value, 12)
            for key, value in sorted(quadratic.items())
        },
        "normalization_scale_cents": scale,
        "constraint_penalty": penalty,
        "qaoa_ready": True,
        "backend_candidates": [
            "qaoa_simulator",
            "ibm_quantum_qaoa",
            "dwave_bqm_or_hybrid",
        ],
        "external_solver_called": False,
        "prediction_only": True,
        "actual_revenue": False,
        "allocation_execution": False,
        "execution_authority": "none",
    }


def benchmark_solution(
    *,
    classical: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare a quantum/hybrid candidate with the exact reference."""
    if (
        classical.get("objective_value_cents") is None
        or candidate.get("objective_value_cents") is None
    ):
        return {
            "schema_version": "empire.quantum_optimization.benchmark.v1",
            "status": "UNAVAILABLE",
            "reason": "objective_value_missing",
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    reference = float(classical["objective_value_cents"])
    observed = float(candidate["objective_value_cents"])
    gap = reference - observed
    ratio = (
        observed / reference
        if reference > 0
        else 1.0 if observed == 0 else None
    )

    return {
        "schema_version": "empire.quantum_optimization.benchmark.v1",
        "status": "AVAILABLE",
        "classical_reference_cents": reference,
        "candidate_objective_cents": observed,
        "optimality_gap_cents": round(gap, 4),
        "candidate_to_reference_ratio": (
            round(ratio, 8)
            if ratio is not None
            else None
        ),
        "matches_or_beats_reference": observed >= reference,
        "quantum_advantage_claimed": False,
        "benchmark_required_before_production_use": True,
        "execution_authority": "none",
    }
