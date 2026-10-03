"""Evidence-only solver performance memory for Empire Optimization Fabric.

Aggregates observed Benchmark Arena packets by workload shape. It can recommend
which solver deserves the next benchmark attempt, but it cannot alter production
routing, promote a solver, or claim quantum advantage.
"""
from __future__ import annotations

from statistics import fmean
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "empire.solver_performance_memory.v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bucket(value: int) -> str:
    if value <= 24:
        return "000001-000024"
    if value <= 100:
        return "000025-000100"
    if value <= 1000:
        return "000101-001000"
    if value <= 5000:
        return "001001-005000"
    if value <= 25000:
        return "005001-025000"
    return "025001-plus"


def workload_signature(packet: Mapping[str, Any]) -> str:
    workload_type = _text(packet.get("workload_type"))
    if not workload_type:
        raise ValueError("workload_type required")
    try:
        variables = int(packet.get("variable_count"))
        constraints = int(packet.get("constraint_count"))
    except (TypeError, ValueError) as exc:
        raise ValueError("variable_count and constraint_count required") from exc
    if variables < 0 or constraints < 0:
        raise ValueError("counts must be nonnegative")
    reps = sorted({
        _text(value).upper()
        for value in (packet.get("representations") or ())
        if _text(value)
    })
    return "|".join([
        workload_type,
        f"v:{_bucket(variables)}",
        f"c:{_bucket(constraints)}",
        f"r:{','.join(reps) if reps else 'NONE'}",
    ])


def build_solver_performance_memory(
    arena_packets: Sequence[Mapping[str, Any]],
    *,
    minimum_observations: int = 3,
) -> dict[str, Any]:
    """Aggregate repeated real benchmark observations by workload signature."""
    if minimum_observations < 2:
        raise ValueError("minimum_observations must be >= 2")

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    rejected = 0
    for packet in arena_packets:
        if not isinstance(packet, Mapping):
            rejected += 1
            continue
        if _text(packet.get("status")).upper() != "AVAILABLE":
            rejected += 1
            continue
        if packet.get("external_qpu_called") is True:
            # External results need provider/cost governance before they can
            # participate in this local evidence-only memory.
            rejected += 1
            continue
        try:
            signature = workload_signature(packet)
        except ValueError:
            rejected += 1
            continue
        grouped.setdefault(signature, []).append(packet)

    profiles: dict[str, dict[str, Any]] = {}
    for signature, packets in sorted(grouped.items()):
        by_solver: dict[str, list[dict[str, Any]]] = {}
        for packet in packets:
            baseline_solver = _text(packet.get("baseline_solver"))
            comparisons = dict(packet.get("comparisons") or {})
            runs = dict(packet.get("runs") or {})
            for run_key, raw in runs.items():
                if not isinstance(raw, Mapping):
                    continue
                solver = _text(raw.get("solver")) or str(run_key)
                comparison = comparisons.get(str(run_key))
                comparison = (
                    comparison if isinstance(comparison, Mapping) else {}
                )
                matches_reference = (
                    True
                    if solver == baseline_solver
                    else comparison.get("matches_or_beats_reference") is True
                )
                by_solver.setdefault(solver, []).append({
                    "feasible": raw.get("constraints_satisfied") is True,
                    "wall_clock_ms": raw.get("wall_clock_ms"),
                    "compute_cost_minor_units": raw.get(
                        "compute_cost_minor_units"
                    ),
                    "matches_reference": matches_reference,
                    "quantum_advantage_claimed": raw.get(
                        "quantum_advantage_claimed"
                    ) is True,
                })

        solver_profiles: dict[str, dict[str, Any]] = {}
        eligible: list[dict[str, Any]] = []
        for solver, rows in sorted(by_solver.items()):
            usable = [
                row
                for row in rows
                if row.get("wall_clock_ms") is not None
            ]
            observation_count = len(rows)
            feasible_count = sum(row["feasible"] for row in rows)
            reference_match_count = sum(
                row["matches_reference"] for row in rows
            )
            costs = [
                float(row["compute_cost_minor_units"])
                for row in rows
                if row.get("compute_cost_minor_units") is not None
            ]
            walls = [float(row["wall_clock_ms"]) for row in usable]
            has_bad_claim = any(
                row["quantum_advantage_claimed"] for row in rows
            )
            recommendation_eligible = (
                observation_count >= minimum_observations
                and observation_count == feasible_count
                and observation_count == reference_match_count
                and len(walls) == observation_count
                and not has_bad_claim
            )
            profile = {
                "solver": solver,
                "observation_count": observation_count,
                "feasible_count": feasible_count,
                "reference_match_count": reference_match_count,
                "feasibility_rate": round(
                    feasible_count / observation_count,
                    8,
                ) if observation_count else None,
                "reference_match_rate": round(
                    reference_match_count / observation_count,
                    8,
                ) if observation_count else None,
                "mean_wall_clock_ms": (
                    round(fmean(walls), 8)
                    if walls else None
                ),
                "compute_cost_observation_count": len(costs),
                "mean_compute_cost_minor_units": (
                    round(fmean(costs), 8)
                    if costs else None
                ),
                "recommendation_eligible": recommendation_eligible,
                "production_promotion_ready": False,
                "quantum_advantage_claimed": False,
            }
            solver_profiles[solver] = profile
            if recommendation_eligible:
                eligible.append(profile)

        eligible.sort(key=lambda row: (
            float(row["mean_wall_clock_ms"]),
            0 if row["mean_compute_cost_minor_units"] is not None else 1,
            float(row["mean_compute_cost_minor_units"] or 0.0),
            str(row["solver"]),
        ))
        recommended = eligible[0]["solver"] if eligible else None
        profiles[signature] = {
            "signature": signature,
            "arena_observation_count": len(packets),
            "solver_profiles": solver_profiles,
            "recommended_benchmark_solver": recommended,
            "recommendation_available": recommended is not None,
            "automatic_production_routing_changed": False,
            "production_promotion_ready": False,
            "human_review_required": True,
            "execution_authority": "none",
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE" if profiles else "UNAVAILABLE",
        "minimum_observations": minimum_observations,
        "profile_count": len(profiles),
        "profiles": profiles,
        "rejected_packet_count": rejected,
        "evidence_only": True,
        "automatic_production_routing_changed": False,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }


def recommend_benchmark_solver(
    *,
    memory: Mapping[str, Any],
    arena_shape: Mapping[str, Any],
) -> dict[str, Any]:
    """Return an evidence-backed benchmark recommendation, never execution."""
    signature = workload_signature(arena_shape)
    profiles = dict(memory.get("profiles") or {})
    profile = profiles.get(signature)
    if not isinstance(profile, Mapping):
        return {
            "schema_version": "empire.solver_performance_recommendation.v1",
            "status": "UNAVAILABLE",
            "reason": "no_matching_workload_profile",
            "signature": signature,
            "execution_authority": "none",
        }
    solver = profile.get("recommended_benchmark_solver")
    if not solver:
        return {
            "schema_version": "empire.solver_performance_recommendation.v1",
            "status": "UNAVAILABLE",
            "reason": "insufficient_repeated_solver_evidence",
            "signature": signature,
            "execution_authority": "none",
        }
    return {
        "schema_version": "empire.solver_performance_recommendation.v1",
        "status": "AVAILABLE",
        "signature": signature,
        "recommended_benchmark_solver": solver,
        "recommendation_only": True,
        "automatic_production_routing_changed": False,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }
