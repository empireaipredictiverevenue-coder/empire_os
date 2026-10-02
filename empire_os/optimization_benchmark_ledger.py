"""Evidence-grade benchmark records for Empire optimization solvers.

This module compares runs against the same fingerprinted problem and records
objective quality, feasibility, latency, cost and repeatability evidence.

It never promotes a solver and never claims quantum advantage from benchmark
evidence alone.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from statistics import fmean
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "empire.optimization.benchmark-ledger.v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be finite")
    return number


def _optional_nonnegative(value: Any, name: str) -> float | None:
    if value is None:
        return None
    number = _number(value, name)
    if number < 0:
        raise ValueError(f"{name} must be nonnegative")
    return number


def _observed_at(value: Any) -> str:
    text = _text(value)
    if not text:
        raise ValueError("observed_at required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    return parsed.isoformat()


def _run_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def build_solver_run_evidence(
    *,
    problem: Mapping[str, Any],
    solver: str,
    solver_family: str,
    hardware_class: str,
    objective_value: Any,
    constraints_satisfied: bool,
    wall_clock_ms: Any,
    compute_cost_minor_units: Any = None,
    provider: str | None = None,
    observed_at: str,
    run_ref: str,
    external: bool = False,
) -> dict[str, Any]:
    """Normalize one observed solver run without inventing missing cost."""
    fingerprint = _text(problem.get("problem_fingerprint"))
    if not fingerprint:
        raise ValueError("problem_fingerprint required")
    if str(problem.get("status") or "").upper() != "AVAILABLE":
        raise ValueError("problem must be AVAILABLE")
    solver_name = _text(solver)
    family = _text(solver_family)
    hardware = _text(hardware_class)
    reference = _text(run_ref)
    if not solver_name or not family or not hardware or not reference:
        raise ValueError(
            "solver, solver_family, hardware_class and run_ref required"
        )
    if not isinstance(constraints_satisfied, bool):
        raise ValueError("constraints_satisfied must be boolean")

    objective = _number(objective_value, "objective_value")
    wall_clock = _optional_nonnegative(wall_clock_ms, "wall_clock_ms")
    if wall_clock is None:
        raise ValueError("wall_clock_ms required")
    compute_cost = _optional_nonnegative(
        compute_cost_minor_units,
        "compute_cost_minor_units",
    )
    timestamp = _observed_at(observed_at)

    identity = {
        "problem_fingerprint": fingerprint,
        "solver": solver_name,
        "solver_family": family,
        "hardware_class": hardware,
        "provider": _text(provider) or None,
        "objective_value": objective,
        "constraints_satisfied": constraints_satisfied,
        "wall_clock_ms": wall_clock,
        "compute_cost_minor_units": compute_cost,
        "observed_at": timestamp,
        "run_ref": reference,
        "external": bool(external),
    }

    return {
        "schema_version": "empire.optimization.solver-run.v1",
        "status": "AVAILABLE",
        "run_id": _run_id(identity),
        **identity,
        "compute_cost_known": compute_cost is not None,
        "prediction_only": True,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }


def compare_solver_runs(
    *,
    problem: Mapping[str, Any],
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two observed runs bound to the exact same problem fingerprint."""
    fingerprint = _text(problem.get("problem_fingerprint"))
    if not fingerprint:
        raise ValueError("problem_fingerprint required")
    if _text(baseline.get("problem_fingerprint")) != fingerprint:
        raise ValueError("baseline problem fingerprint mismatch")
    if _text(candidate.get("problem_fingerprint")) != fingerprint:
        raise ValueError("candidate problem fingerprint mismatch")

    objective = dict(problem.get("objective") or {})
    sense = _text(objective.get("sense")).upper()
    if sense not in {"MAXIMIZE", "MINIMIZE"}:
        raise ValueError("problem objective sense required")

    baseline_value = _number(baseline.get("objective_value"), "baseline objective")
    candidate_value = _number(
        candidate.get("objective_value"),
        "candidate objective",
    )
    baseline_feasible = baseline.get("constraints_satisfied") is True
    candidate_feasible = candidate.get("constraints_satisfied") is True

    if sense == "MAXIMIZE":
        quality_delta = candidate_value - baseline_value
        matches_or_beats = candidate_value >= baseline_value
    else:
        quality_delta = baseline_value - candidate_value
        matches_or_beats = candidate_value <= baseline_value

    candidate_wall = _number(candidate.get("wall_clock_ms"), "candidate wall_clock_ms")
    baseline_wall = _number(baseline.get("wall_clock_ms"), "baseline wall_clock_ms")
    speedup_ratio = (
        baseline_wall / candidate_wall
        if candidate_wall > 0
        else None
    )

    baseline_cost = baseline.get("compute_cost_minor_units")
    candidate_cost = candidate.get("compute_cost_minor_units")
    cost_delta = (
        _number(candidate_cost, "candidate cost")
        - _number(baseline_cost, "baseline cost")
        if baseline_cost is not None and candidate_cost is not None
        else None
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "problem_fingerprint": fingerprint,
        "objective_sense": sense,
        "baseline_run_id": baseline.get("run_id"),
        "candidate_run_id": candidate.get("run_id"),
        "baseline_solver": baseline.get("solver"),
        "candidate_solver": candidate.get("solver"),
        "baseline_feasible": baseline_feasible,
        "candidate_feasible": candidate_feasible,
        "baseline_objective_value": baseline_value,
        "candidate_objective_value": candidate_value,
        "objective_quality_delta": round(quality_delta, 8),
        "matches_or_beats_reference": (
            baseline_feasible
            and candidate_feasible
            and matches_or_beats
        ),
        "baseline_wall_clock_ms": baseline_wall,
        "candidate_wall_clock_ms": candidate_wall,
        "speedup_ratio": (
            round(speedup_ratio, 8)
            if speedup_ratio is not None
            else None
        ),
        "compute_cost_delta_minor_units": (
            round(cost_delta, 8)
            if cost_delta is not None
            else None
        ),
        "compute_cost_comparable": cost_delta is not None,
        "benchmark_evidence_only": True,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "human_review_required": True,
        "execution_authority": "none",
    }


def summarize_repeatability(
    runs: Sequence[Mapping[str, Any]],
    *,
    minimum_runs: int = 3,
) -> dict[str, Any]:
    """Summarize repeated runs only when they share problem + solver identity."""
    if minimum_runs < 2:
        raise ValueError("minimum_runs must be >= 2")
    usable = [
        row
        for row in runs
        if isinstance(row, Mapping)
        and str(row.get("status") or "").upper() == "AVAILABLE"
    ]
    if len(usable) < minimum_runs:
        return {
            "schema_version": "empire.optimization.repeatability.v1",
            "status": "UNAVAILABLE",
            "reason": "insufficient_repeated_runs",
            "observed_run_count": len(usable),
            "minimum_runs": minimum_runs,
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    fingerprints = {
        _text(row.get("problem_fingerprint"))
        for row in usable
    }
    solvers = {_text(row.get("solver")) for row in usable}
    if len(fingerprints) != 1 or len(solvers) != 1 or "" in fingerprints | solvers:
        return {
            "schema_version": "empire.optimization.repeatability.v1",
            "status": "UNAVAILABLE",
            "reason": "mixed_problem_or_solver_identity",
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    objectives = [_number(row.get("objective_value"), "objective_value") for row in usable]
    walls = [_number(row.get("wall_clock_ms"), "wall_clock_ms") for row in usable]
    feasible_count = sum(row.get("constraints_satisfied") is True for row in usable)

    costs = [
        _number(row.get("compute_cost_minor_units"), "compute_cost_minor_units")
        for row in usable
        if row.get("compute_cost_minor_units") is not None
    ]

    return {
        "schema_version": "empire.optimization.repeatability.v1",
        "status": "AVAILABLE",
        "problem_fingerprint": next(iter(fingerprints)),
        "solver": next(iter(solvers)),
        "run_count": len(usable),
        "feasible_run_count": feasible_count,
        "all_runs_feasible": feasible_count == len(usable),
        "objective_min": min(objectives),
        "objective_max": max(objectives),
        "objective_mean": round(fmean(objectives), 8),
        "wall_clock_ms_min": min(walls),
        "wall_clock_ms_max": max(walls),
        "wall_clock_ms_mean": round(fmean(walls), 8),
        "compute_cost_observation_count": len(costs),
        "compute_cost_mean_minor_units": (
            round(fmean(costs), 8)
            if costs
            else None
        ),
        "repeatability_evidence_available": True,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }
