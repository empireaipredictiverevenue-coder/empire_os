"""External quantum/hybrid provider planning for Empire Optimization Fabric.

This module prepares provider-bound benchmark plans only. It never submits
jobs, never reads credentials, never spends money and never grants execution
authority.

D-Wave is the first provider contract because Empire already supports safe QUBO
and generic CQM-style problem representations. Hybrid CQM and direct-QPU BQM
remain distinct lanes with distinct prerequisites.
"""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.optimization_qubo import build_safe_qubo


SCHEMA_VERSION = "empire.quantum_provider_plan.v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _enabled(value: Any) -> bool:
    return str(value or "").strip().lower() in {
        "1", "true", "yes", "on", "enabled",
    }


def _base_blockers(
    problem: Mapping[str, Any],
    *,
    provider_enabled: bool,
    allow_external_benchmark: bool,
) -> list[str]:
    blockers: list[str] = []
    if not provider_enabled:
        blockers.append("external_provider_not_enabled")
    if not allow_external_benchmark:
        blockers.append("external_qpu_benchmark_not_authorized_for_route")
    if problem.get("time_budget_ms") is None:
        blockers.append("time_budget_required")
    if problem.get("cost_budget_minor_units") is None:
        blockers.append("cost_budget_required_for_external_solver")
    return blockers


def build_dwave_hybrid_cqm_plan(
    problem: Mapping[str, Any],
    *,
    provider_enabled: bool = False,
    allow_external_benchmark: bool = False,
) -> dict[str, Any]:
    """Prepare a D-Wave Leap hybrid CQM benchmark plan without submission."""
    if str(problem.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "execution_authority": "none",
        }

    representations = {
        _text(value).upper()
        for value in (problem.get("representations") or ())
        if _text(value)
    }
    blockers = _base_blockers(
        problem,
        provider_enabled=provider_enabled,
        allow_external_benchmark=allow_external_benchmark,
    )
    if "CQM" not in representations:
        blockers.append("cqm_representation_not_available")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "provider": "dwave",
        "provider_mode": "leap_hybrid_cqm",
        "model_type": "CQM",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "variable_count": problem.get("variable_count"),
        "constraint_count": problem.get("constraint_count"),
        "time_budget_ms": problem.get("time_budget_ms"),
        "cost_budget_minor_units": problem.get(
            "cost_budget_minor_units"
        ),
        "provider_enabled": provider_enabled,
        "external_benchmark_authorized": allow_external_benchmark,
        "submission_ready": not blockers,
        "blockers": sorted(set(blockers)),
        "credential_presence_checked": False,
        "provider_minimum_runtime_checked": False,
        "provider_solver_properties_checked": False,
        "external_solver_called": False,
        "qpu_direct": False,
        "hybrid_quantum_classical": True,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }


def build_dwave_direct_qpu_plan(
    problem: Mapping[str, Any],
    *,
    provider_enabled: bool = False,
    allow_external_benchmark: bool = False,
    num_reads: int = 100,
) -> dict[str, Any]:
    """Prepare a direct D-Wave QPU BQM plan without provider contact."""
    if num_reads <= 0:
        raise ValueError("num_reads must be positive")
    if str(problem.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "execution_authority": "none",
        }

    qubo = build_safe_qubo(problem)
    blockers = _base_blockers(
        problem,
        provider_enabled=provider_enabled,
        allow_external_benchmark=allow_external_benchmark,
    )
    if str(qubo.get("status") or "").upper() != "AVAILABLE":
        blockers.append(
            "safe_qubo_required:"
            + str(qubo.get("reason") or "qubo_unavailable")
        )

    # Direct-QPU execution additionally requires a live topology/embedding
    # preflight. We do not query provider properties in this planning module.
    blockers.append("qpu_topology_embedding_preflight_required")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "provider": "dwave",
        "provider_mode": "direct_qpu_bqm",
        "model_type": "BQM",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "safe_qubo": qubo,
        "num_reads": int(num_reads),
        "time_budget_ms": problem.get("time_budget_ms"),
        "cost_budget_minor_units": problem.get(
            "cost_budget_minor_units"
        ),
        "provider_enabled": provider_enabled,
        "external_benchmark_authorized": allow_external_benchmark,
        "submission_ready": False,
        "blockers": sorted(set(blockers)),
        "credential_presence_checked": False,
        "qpu_topology_embedding_preflight_required": True,
        "provider_solver_properties_checked": False,
        "external_solver_called": False,
        "qpu_direct": True,
        "hybrid_quantum_classical": False,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }


def build_dwave_provider_matrix(
    problem: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    allow_external_benchmark: bool = False,
) -> dict[str, Any]:
    """Expose both D-Wave lanes under one provider-neutral review packet."""
    source = dict(env or {})
    provider_enabled = _enabled(
        source.get("EMPIRE_QPU_DWAVE_ENABLED")
    )
    hybrid = build_dwave_hybrid_cqm_plan(
        problem,
        provider_enabled=provider_enabled,
        allow_external_benchmark=allow_external_benchmark,
    )
    direct = build_dwave_direct_qpu_plan(
        problem,
        provider_enabled=provider_enabled,
        allow_external_benchmark=allow_external_benchmark,
    )
    return {
        "schema_version": "empire.quantum_provider_matrix.v1",
        "status": "AVAILABLE",
        "provider": "dwave",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "lanes": {
            "hybrid_cqm": hybrid,
            "direct_qpu_bqm": direct,
        },
        "any_submission_ready": any(
            lane.get("submission_ready") is True
            for lane in (hybrid, direct)
        ),
        "external_solver_called": False,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }
