"""Provider-neutral external QPU benchmark contract for EmpireOS.

This module prepares and validates benchmark requests/results only. It does not
inspect credentials, call a provider, move funds, or grant execution authority.
External QPU work remains an explicitly authorized benchmark action.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from empire_os.optimization_problem_factory import validate_problem_integrity


SCHEMA_VERSION = "empire.qpu_provider_contract.v1"

PROVIDERS = {
    "ibm_quantum": {
        "solver_keys": {"ibm_qaoa"},
        "representations": {"QUBO"},
    },
    "dwave": {
        "solver_keys": {"dwave_hybrid_cqm"},
        "representations": {"CQM"},
    },
    "amazon_braket": {
        "solver_keys": {"amazon_braket_qaoa"},
        "representations": {"QUBO"},
    },
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any, name: str) -> float:
    if value is None:
        raise ValueError(f"{name} required")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be finite")
    return number


def _positive(value: Any, name: str) -> float:
    number = _number(value, name)
    if number <= 0:
        raise ValueError(f"{name} must be positive")
    return number


def _nonnegative(value: Any, name: str) -> float:
    number = _number(value, name)
    if number < 0:
        raise ValueError(f"{name} must be nonnegative")
    return number


def _observed_at(value: Any) -> str:
    text = _text(value)
    if not text:
        raise ValueError("observed_at required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    return parsed.isoformat()


def _request_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _candidate_lane(
    fabric_plan: Mapping[str, Any],
    *,
    solver_key: str,
) -> Mapping[str, Any] | None:
    route = fabric_plan.get("solver_route")
    if not isinstance(route, Mapping):
        return None
    for raw in route.get("benchmark_lanes") or ():
        if (
            isinstance(raw, Mapping)
            and _text(raw.get("solver")) == solver_key
        ):
            return raw
    return None


def build_qpu_benchmark_request(
    fabric_plan: Mapping[str, Any],
    *,
    provider: str,
    solver_key: str,
    backend_ref: str,
    evidence_refs: Sequence[Any],
    baseline_benchmark: Mapping[str, Any] | None = None,
    external_benchmark_authorized: bool = False,
    approval_ref: str | None = None,
) -> dict[str, Any]:
    """Build a bounded request for a future external provider adapter.

    This function never performs the provider call.
    """
    if str(fabric_plan.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "fabric_plan_unavailable",
            "execution_authority": "none",
        }

    provider_key = _text(provider)
    solver = _text(solver_key)
    backend = _text(backend_ref)
    if provider_key not in PROVIDERS:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "unsupported_qpu_provider",
            "provider": provider_key or None,
            "execution_authority": "none",
        }
    if solver not in PROVIDERS[provider_key]["solver_keys"]:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "solver_provider_mismatch",
            "provider": provider_key,
            "solver": solver or None,
            "execution_authority": "none",
        }
    if not backend:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "backend_ref_required",
            "provider": provider_key,
            "solver": solver,
            "execution_authority": "none",
        }

    problem = fabric_plan.get("problem")
    if not isinstance(problem, Mapping):
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_missing",
            "execution_authority": "none",
        }

    integrity = validate_problem_integrity(problem)
    if str(integrity.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "qpu_problem_integrity_failed",
            "integrity": integrity,
            "execution_authority": "none",
        }

    fingerprint = _text(problem.get("problem_fingerprint"))
    if not fingerprint:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "problem_fingerprint_required",
            "execution_authority": "none",
        }

    time_budget = problem.get("time_budget_ms")
    cost_budget = problem.get("cost_budget_minor_units")
    if time_budget is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "time_budget_required_for_external_qpu",
            "problem_fingerprint": fingerprint,
            "execution_authority": "none",
        }
    if cost_budget is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "cost_budget_required_for_external_qpu",
            "problem_fingerprint": fingerprint,
            "execution_authority": "none",
        }
    try:
        time_budget_value = _positive(time_budget, "time_budget_ms")
        cost_budget_value = _positive(
            cost_budget,
            "cost_budget_minor_units",
        )
    except ValueError as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "invalid_external_qpu_budget",
            "detail": str(exc),
            "problem_fingerprint": fingerprint,
            "execution_authority": "none",
        }

    representations = {
        _text(value).upper()
        for value in (problem.get("representations") or ())
        if _text(value)
    }
    required_representations = set(
        PROVIDERS[provider_key]["representations"]
    )
    if not representations.intersection(required_representations):
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "provider_representation_not_available",
            "provider": provider_key,
            "solver": solver,
            "required_representations": sorted(required_representations),
            "available_representations": sorted(representations),
            "execution_authority": "none",
        }

    lane = _candidate_lane(fabric_plan, solver_key=solver)
    if lane is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "solver_lane_not_present_in_router",
            "provider": provider_key,
            "solver": solver,
            "execution_authority": "none",
        }

    benchmark = (
        baseline_benchmark
        if isinstance(baseline_benchmark, Mapping)
        else {}
    )
    benchmark_status = str(
        benchmark.get("status") or ""
    ).upper()
    benchmark_fingerprint = _text(
        benchmark.get("problem_fingerprint")
    )
    baseline_ready = (
        benchmark_status == "AVAILABLE"
        and benchmark_fingerprint == fingerprint
        and _text(benchmark.get("baseline_solver")) != ""
        and int(benchmark.get("run_count") or 0) >= 1
    )

    refs = tuple(sorted({
        _text(ref)
        for ref in evidence_refs
        if _text(ref)
    }))
    if not refs:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "evidence_refs_required",
            "problem_fingerprint": fingerprint,
            "execution_authority": "none",
        }

    provider_enabled = lane.get("explicit_provider_enable") is True
    router_external_allowed = (
        fabric_plan.get("external_qpu_benchmark_allowed") is True
    )
    readiness_blockers: list[str] = []
    if lane.get("empire_adapter_implemented") is not True:
        readiness_blockers.append("empire_provider_adapter_not_implemented")
    if lane.get("installed") is not True:
        readiness_blockers.append("provider_runtime_not_installed")
    if not provider_enabled:
        readiness_blockers.append("provider_not_explicitly_enabled")
    if not router_external_allowed:
        readiness_blockers.append(
            "router_external_qpu_benchmark_not_enabled"
        )
    if not baseline_ready:
        readiness_blockers.append(
            "same_problem_classical_benchmark_required"
        )
    if external_benchmark_authorized is not True:
        readiness_blockers.append(
            "operator_external_qpu_benchmark_authorization_required"
        )
    approval = _text(approval_ref)
    if not approval:
        readiness_blockers.append("approval_ref_required")

    # Empire policy: third-party solver/QPU services are research references
    # only. No credential, flag, approval or budget can promote them into the
    # Empire production/runtime execution path.
    readiness_blockers.append(
        "third_party_service_execution_prohibited_by_empire_policy"
    )

    payload = {
        "problem_fingerprint": fingerprint,
        "provider": provider_key,
        "solver": solver,
        "backend_ref": backend,
        "time_budget_ms": time_budget_value,
        "cost_budget_minor_units": cost_budget_value,
        "representations": sorted(representations),
        "evidence_refs": refs,
    }

    ready = False
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "HELD",
        "request_id": _request_id(payload),
        **payload,
        "router_lane": dict(lane),
        "readiness_blockers": sorted(set(readiness_blockers)),
        "external_benchmark_authorized": (
            external_benchmark_authorized is True
        ),
        "approval_ref": approval or None,
        "classical_baseline_verified": baseline_ready,
        "baseline_solver": benchmark.get("baseline_solver"),
        "baseline_run_count": benchmark.get("run_count"),
        "provider_credentials_inspected": False,
        "provider_call_performed": False,
        "funds_committed": False,
        "research_only": True,
        "provider_submission_allowed": False,
        "third_party_service_execution_allowed": False,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "commercial_authority": "none",
        "financial_authority": "none",
        "execution_authority": "none",
    }


def normalize_qpu_benchmark_result(
    *,
    request: Mapping[str, Any],
    provider_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize externally obtained market-reference evidence offline.

    This parser performs no provider call and does not make third-party service
    execution permissible inside EmpireOS.
    """
    if str(request.get("status") or "").upper() != "READY":
        return {
            "schema_version": "empire.qpu_benchmark_result.v1",
            "status": "UNAVAILABLE",
            "reason": "qpu_request_not_ready",
            "provider_call_performed": False,
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    expected_fingerprint = _text(request.get("problem_fingerprint"))
    observed_fingerprint = _text(
        provider_result.get("problem_fingerprint")
    )
    if observed_fingerprint != expected_fingerprint:
        return {
            "schema_version": "empire.qpu_benchmark_result.v1",
            "status": "UNAVAILABLE",
            "reason": "problem_fingerprint_mismatch",
            "expected_problem_fingerprint": expected_fingerprint,
            "observed_problem_fingerprint": (
                observed_fingerprint or None
            ),
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    required = (
        "objective_value",
        "constraints_satisfied",
        "wall_clock_ms",
        "provider_compute_cost_minor_units",
        "provider_job_ref",
        "observed_at",
        "provider",
        "backend_ref",
        "provider_call_performed",
    )
    missing = [
        field
        for field in required
        if provider_result.get(field) is None
    ]
    if missing:
        return {
            "schema_version": "empire.qpu_benchmark_result.v1",
            "status": "UNAVAILABLE",
            "reason": "provider_result_evidence_incomplete",
            "missing_fields": missing,
            "problem_fingerprint": expected_fingerprint,
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    if provider_result.get("provider_call_performed") is not True:
        return {
            "schema_version": "empire.qpu_benchmark_result.v1",
            "status": "UNAVAILABLE",
            "reason": "provider_call_evidence_required",
            "problem_fingerprint": expected_fingerprint,
            "provider_call_performed": False,
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    observed_provider = _text(provider_result.get("provider"))
    observed_backend = _text(provider_result.get("backend_ref"))
    if (
        observed_provider != _text(request.get("provider"))
        or observed_backend != _text(request.get("backend_ref"))
    ):
        return {
            "schema_version": "empire.qpu_benchmark_result.v1",
            "status": "UNAVAILABLE",
            "reason": "provider_or_backend_identity_mismatch",
            "problem_fingerprint": expected_fingerprint,
            "expected_provider": request.get("provider"),
            "observed_provider": observed_provider or None,
            "expected_backend_ref": request.get("backend_ref"),
            "observed_backend_ref": observed_backend or None,
            "provider_call_performed": True,
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    provider_job_ref = _text(provider_result.get("provider_job_ref"))
    if not provider_job_ref:
        return {
            "schema_version": "empire.qpu_benchmark_result.v1",
            "status": "UNAVAILABLE",
            "reason": "provider_job_ref_required",
            "problem_fingerprint": expected_fingerprint,
            "provider_call_performed": True,
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    try:
        observed_at = _observed_at(provider_result.get("observed_at"))
        objective = _number(
            provider_result["objective_value"],
            "objective_value",
        )
        wall_clock = _nonnegative(
            provider_result["wall_clock_ms"],
            "wall_clock_ms",
        )
        compute_cost = _nonnegative(
            provider_result["provider_compute_cost_minor_units"],
            "provider_compute_cost_minor_units",
        )
        queue_time = (
            _nonnegative(
                provider_result.get("queue_time_ms"),
                "queue_time_ms",
            )
            if provider_result.get("queue_time_ms") is not None
            else None
        )
    except ValueError as exc:
        return {
            "schema_version": "empire.qpu_benchmark_result.v1",
            "status": "UNAVAILABLE",
            "reason": "provider_result_evidence_invalid",
            "detail": str(exc),
            "problem_fingerprint": expected_fingerprint,
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    feasible = provider_result.get("constraints_satisfied")
    if not isinstance(feasible, bool):
        return {
            "schema_version": "empire.qpu_benchmark_result.v1",
            "status": "UNAVAILABLE",
            "reason": "constraints_satisfied_must_be_boolean",
            "problem_fingerprint": expected_fingerprint,
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    return {
        "schema_version": "empire.qpu_benchmark_result.v1",
        "status": "AVAILABLE",
        "request_id": request.get("request_id"),
        "problem_fingerprint": expected_fingerprint,
        "provider": request.get("provider"),
        "solver": request.get("solver"),
        "backend_ref": request.get("backend_ref"),
        "provider_job_ref": provider_job_ref,
        "observed_at": observed_at,
        "objective_value": objective,
        "constraints_satisfied": feasible,
        "wall_clock_ms": wall_clock,
        "provider_compute_cost_minor_units": compute_cost,
        "queue_time_ms": queue_time,
        "provider_call_performed": True,
        "benchmark_evidence_only": True,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "human_review_required": True,
        "execution_authority": "none",
    }
