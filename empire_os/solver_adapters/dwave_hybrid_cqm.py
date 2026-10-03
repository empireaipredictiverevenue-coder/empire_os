"""Bounded D-Wave Leap Hybrid CQM provider adapter.

The adapter compiles canonical Empire Optimization IR to a native CQM and
exposes readiness/limit-discovery/submission boundaries. It never submits
unless the caller explicitly authorizes the external call and provides a
verified account cost policy.

Cash cost remains UNKNOWN unless an account-specific quota-to-currency mapping
is supplied as evidence. D-Wave charge_time is tracked separately as provider
quota usage.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import time
from typing import Any, Callable, Mapping

from empire_os.optimization_problem_factory import validate_problem_integrity


SCHEMA_VERSION = "empire.solver_adapter.dwave_hybrid_cqm.v1"


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


def _nonnegative(value: Any, name: str) -> float:
    number = _number(value, name)
    if number < 0:
        raise ValueError(f"{name} must be nonnegative")
    return number


def _load_runtime():
    try:
        import dimod
        from dwave.system import LeapHybridCQMSampler
    except ImportError:
        return None, None
    return dimod, LeapHybridCQMSampler


def credential_presence(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Report credential/config presence without exposing secret values."""
    source = dict(os.environ if env is None else env)
    token_present = bool(
        _text(source.get("DWAVE_API_TOKEN"))
        or _text(source.get("D-WAVE_API_TOKEN"))
    )
    configured_path = _text(source.get("DWAVE_CONFIG_FILE"))
    candidates = [
        Path(configured_path) if configured_path else None,
        Path.home() / ".config" / "dwave" / "dwave.conf",
        Path.home() / ".dwave" / "dwave.conf",
        Path("/etc/dwave/dwave.conf"),
    ]
    existing = [
        str(path)
        for path in candidates
        if path is not None and path.is_file()
    ]
    return {
        "token_env_present": token_present,
        "config_file_present": bool(existing),
        "config_paths_present": existing,
        "credential_material_present": token_present or bool(existing),
        "credential_values_exposed": False,
    }


def compile_cqm(problem: Mapping[str, Any]) -> dict[str, Any]:
    """Compile canonical binary linear/quadratic IR to D-Wave CQM."""
    integrity = validate_problem_integrity(problem)
    if str(integrity.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_integrity_failed",
            "integrity": integrity,
            "execution_authority": "none",
        }
    if _text(problem.get("variable_type")).upper() != "BINARY":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "binary_variables_only_in_adapter_v1",
            "execution_authority": "none",
        }

    dimod, _ = _load_runtime()
    if dimod is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "dwave_system_not_installed",
            "execution_authority": "none",
        }

    rows = [
        dict(row)
        for row in (problem.get("variables") or ())
        if isinstance(row, Mapping)
    ]
    variables = {
        _text(row.get("variable")): dimod.Binary(_text(row.get("variable")))
        for row in rows
        if _text(row.get("variable"))
    }
    if not variables:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_variables",
            "execution_authority": "none",
        }

    objective = dict(problem.get("objective") or {})
    linear = dict(objective.get("linear") or {})
    quadratic = dict(objective.get("quadratic") or {})

    expression = None
    for variable, coefficient in linear.items():
        name = str(variable)
        if name not in variables:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "UNAVAILABLE",
                "reason": "objective_references_unknown_variable",
                "variable": name,
                "execution_authority": "none",
            }
        term = _number(coefficient, f"objective:{name}") * variables[name]
        expression = term if expression is None else expression + term

    for raw_key, coefficient in quadratic.items():
        key = str(raw_key)
        left, sep, right = key.partition("|")
        if not sep or left not in variables or right not in variables:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "UNAVAILABLE",
                "reason": "invalid_quadratic_objective_key",
                "key": key,
                "execution_authority": "none",
            }
        term = (
            _number(coefficient, f"quadratic:{key}")
            * variables[left]
            * variables[right]
        )
        expression = term if expression is None else expression + term

    if expression is None:
        first = next(iter(variables.values()))
        expression = 0.0 * first

    source_sense = _text(objective.get("sense")).upper()
    if source_sense == "MAXIMIZE":
        provider_expression = -expression
    elif source_sense == "MINIMIZE":
        provider_expression = expression
    else:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "unsupported_objective_sense",
            "execution_authority": "none",
        }

    cqm = dimod.ConstrainedQuadraticModel()
    cqm.set_objective(provider_expression)

    for index, raw in enumerate(problem.get("constraints") or ()):
        if not isinstance(raw, Mapping):
            continue
        label = _text(raw.get("name")) or f"constraint::{index}"
        coefficients = dict(raw.get("coefficients") or {})
        lhs = None
        for variable, coefficient in coefficients.items():
            name = str(variable)
            if name not in variables:
                return {
                    "schema_version": SCHEMA_VERSION,
                    "status": "UNAVAILABLE",
                    "reason": "constraint_references_unknown_variable",
                    "constraint": label,
                    "variable": name,
                    "execution_authority": "none",
                }
            term = (
                _number(coefficient, f"constraint:{label}:{name}")
                * variables[name]
            )
            lhs = term if lhs is None else lhs + term
        if lhs is None:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "UNAVAILABLE",
                "reason": "constant_constraint_requires_separate_review",
                "constraint": label,
                "execution_authority": "none",
            }

        rhs = _number(raw.get("rhs"), f"constraint:{label}:rhs")
        sense = _text(raw.get("sense"))
        if sense == "<=":
            cqm.add_constraint(lhs <= rhs, label=label)
        elif sense == ">=":
            cqm.add_constraint(lhs >= rhs, label=label)
        elif sense in {"==", "="}:
            cqm.add_constraint(lhs == rhs, label=label)
        else:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "UNAVAILABLE",
                "reason": "unsupported_constraint_sense",
                "constraint": label,
                "execution_authority": "none",
            }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "source_objective_sense": source_sense,
        "provider_objective_sense": "MINIMIZE",
        "variable_count": cqm.num_variables(),
        "constraint_count": len(cqm.constraints),
        "supported_problem_type": "CQM",
        "cqm": cqm,
        "provider_call_performed": False,
        "network_call_performed": False,
        "execution_authority": "none",
    }


def build_readiness(
    *,
    request: Mapping[str, Any],
    problem: Mapping[str, Any],
    env: Mapping[str, str] | None = None,
    account_cost_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare D-Wave benchmark readiness without network access."""
    compiled = compile_cqm(problem)
    credentials = credential_presence(env=env)
    blockers: list[str] = []

    if str(request.get("status") or "").upper() != "READY":
        blockers.append("qpu_request_not_ready")
    if _text(request.get("provider")) != "dwave":
        blockers.append("provider_mismatch")
    if _text(request.get("solver")) != "dwave_hybrid_cqm":
        blockers.append("solver_mismatch")
    if str(compiled.get("status") or "").upper() != "AVAILABLE":
        blockers.append("cqm_compile_failed")
    if not credentials["credential_material_present"]:
        blockers.append("dwave_credentials_required")

    policy = (
        dict(account_cost_policy)
        if isinstance(account_cost_policy, Mapping)
        else {}
    )
    rate = policy.get("minor_units_per_quota_second")
    evidence_ref = _text(policy.get("evidence_ref"))
    currency = _text(policy.get("currency"))
    if rate is None or not evidence_ref or not currency:
        blockers.append("verified_account_cost_policy_required")
        rate_value = None
    else:
        try:
            rate_value = _nonnegative(
                rate,
                "minor_units_per_quota_second",
            )
        except ValueError:
            blockers.append("verified_account_cost_policy_invalid")
            rate_value = None

    return {
        "schema_version": "empire.dwave_hybrid_cqm.readiness.v1",
        "status": "READY_FOR_LIMIT_DISCOVERY" if not blockers else "HELD",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "request_id": request.get("request_id"),
        "provider": "dwave",
        "solver": "dwave_hybrid_cqm",
        "compiled_cqm_available": (
            str(compiled.get("status") or "").upper() == "AVAILABLE"
        ),
        "credential_presence": credentials,
        "account_cost_policy": {
            "currency": currency or None,
            "minor_units_per_quota_second": rate_value,
            "evidence_ref": evidence_ref or None,
        },
        "readiness_blockers": sorted(set(blockers)),
        "network_call_performed": False,
        "provider_call_performed": False,
        "funds_committed": False,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }


def discover_limits(
    *,
    readiness: Mapping[str, Any],
    request: Mapping[str, Any],
    problem: Mapping[str, Any],
    allow_network_discovery: bool = False,
    sampler_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Discover D-Wave minimum runtime and bound cost before submission."""
    if str(readiness.get("status") or "").upper() != "READY_FOR_LIMIT_DISCOVERY":
        return {
            "schema_version": "empire.dwave_hybrid_cqm.limits.v1",
            "status": "HELD",
            "reason": "dwave_readiness_not_satisfied",
            "network_call_performed": False,
            "provider_call_performed": False,
            "execution_authority": "none",
        }
    if not allow_network_discovery:
        return {
            "schema_version": "empire.dwave_hybrid_cqm.limits.v1",
            "status": "HELD",
            "reason": "network_discovery_not_authorized",
            "network_call_performed": False,
            "provider_call_performed": False,
            "execution_authority": "none",
        }

    compiled = compile_cqm(problem)
    if str(compiled.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": "empire.dwave_hybrid_cqm.limits.v1",
            "status": "UNAVAILABLE",
            "reason": "cqm_compile_failed",
            "network_call_performed": False,
            "provider_call_performed": False,
            "execution_authority": "none",
        }

    _, sampler_type = _load_runtime()
    if sampler_factory is None:
        if sampler_type is None:
            return {
                "schema_version": "empire.dwave_hybrid_cqm.limits.v1",
                "status": "UNAVAILABLE",
                "reason": "dwave_system_not_installed",
                "network_call_performed": False,
                "provider_call_performed": False,
                "execution_authority": "none",
            }
        sampler_factory = sampler_type

    started = time.perf_counter()
    sampler = sampler_factory()
    minimum_seconds = float(sampler.min_time_limit(compiled["cqm"]))
    discovery_wall_ms = (time.perf_counter() - started) * 1000.0

    max_seconds = _number(request.get("time_budget_ms"), "time_budget_ms") / 1000.0
    rate = readiness["account_cost_policy"]["minor_units_per_quota_second"]
    estimated_minor_units = (
        minimum_seconds * float(rate)
        if rate is not None
        else None
    )
    cost_budget = _number(
        request.get("cost_budget_minor_units"),
        "cost_budget_minor_units",
    )

    blockers: list[str] = []
    if minimum_seconds > max_seconds:
        blockers.append("dwave_minimum_runtime_exceeds_time_budget")
    if (
        estimated_minor_units is None
        or estimated_minor_units > cost_budget
    ):
        blockers.append("dwave_estimated_cost_exceeds_or_lacks_budget")

    return {
        "schema_version": "empire.dwave_hybrid_cqm.limits.v1",
        "status": "READY_TO_SUBMIT" if not blockers else "HELD",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "request_id": request.get("request_id"),
        "minimum_time_limit_seconds": minimum_seconds,
        "selected_time_limit_seconds": minimum_seconds,
        "time_budget_seconds": max_seconds,
        "estimated_compute_cost_minor_units": (
            round(estimated_minor_units, 8)
            if estimated_minor_units is not None
            else None
        ),
        "cost_budget_minor_units": cost_budget,
        "cost_estimate_is_policy_derived": estimated_minor_units is not None,
        "readiness_blockers": sorted(set(blockers)),
        "network_call_performed": True,
        "provider_call_performed": False,
        "provider_job_submitted": False,
        "discovery_wall_clock_ms": round(discovery_wall_ms, 6),
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }


def _source_objective_value(
    problem: Mapping[str, Any],
    assignment: Mapping[str, int],
) -> float:
    objective = dict(problem.get("objective") or {})
    value = sum(
        float(coefficient) * int(assignment.get(str(variable), 0))
        for variable, coefficient in dict(objective.get("linear") or {}).items()
    )
    for key, coefficient in dict(objective.get("quadratic") or {}).items():
        left, sep, right = str(key).partition("|")
        if not sep:
            raise ValueError("invalid quadratic objective key")
        value += (
            float(coefficient)
            * int(assignment.get(left, 0))
            * int(assignment.get(right, 0))
        )
    return value


def submit(
    *,
    limits: Mapping[str, Any],
    request: Mapping[str, Any],
    problem: Mapping[str, Any],
    perform_external_call: bool = False,
    sampler_factory: Callable[[], Any] | None = None,
    label: str = "EmpireOS bounded QPU benchmark",
) -> dict[str, Any]:
    """Submit one bounded hybrid CQM benchmark when every gate is satisfied."""
    if str(limits.get("status") or "").upper() != "READY_TO_SUBMIT":
        return {
            "schema_version": "empire.dwave_hybrid_cqm.result.v1",
            "status": "HELD",
            "reason": "dwave_limits_not_ready",
            "provider_call_performed": False,
            "execution_authority": "none",
        }
    if not perform_external_call:
        return {
            "schema_version": "empire.dwave_hybrid_cqm.result.v1",
            "status": "HELD",
            "reason": "external_provider_call_not_authorized",
            "provider_call_performed": False,
            "execution_authority": "none",
        }

    compiled = compile_cqm(problem)
    if str(compiled.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": "empire.dwave_hybrid_cqm.result.v1",
            "status": "UNAVAILABLE",
            "reason": "cqm_compile_failed",
            "provider_call_performed": False,
            "execution_authority": "none",
        }

    _, sampler_type = _load_runtime()
    if sampler_factory is None:
        if sampler_type is None:
            return {
                "schema_version": "empire.dwave_hybrid_cqm.result.v1",
                "status": "UNAVAILABLE",
                "reason": "dwave_system_not_installed",
                "provider_call_performed": False,
                "execution_authority": "none",
            }
        sampler_factory = sampler_type

    sampler = sampler_factory()
    started = time.perf_counter()
    sampleset = sampler.sample_cqm(
        compiled["cqm"],
        time_limit=float(limits["selected_time_limit_seconds"]),
        label=label,
    )
    resolve = getattr(sampleset, "resolve", None)
    if callable(resolve):
        resolve()
    wall_clock_ms = (time.perf_counter() - started) * 1000.0

    feasible_rows = [
        row
        for row in sampleset.data(fields=["sample", "energy", "is_feasible"])
        if bool(row.is_feasible)
    ]
    if not feasible_rows:
        return {
            "schema_version": "empire.dwave_hybrid_cqm.result.v1",
            "status": "UNAVAILABLE",
            "reason": "provider_returned_no_feasible_sample",
            "problem_fingerprint": problem.get("problem_fingerprint"),
            "provider_call_performed": True,
            "wall_clock_ms": round(wall_clock_ms, 6),
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    first = min(feasible_rows, key=lambda row: float(row.energy))
    assignment = {
        str(variable): int(value)
        for variable, value in dict(first.sample).items()
    }
    timing = dict((sampleset.info or {}).get("timing") or {})
    charge_time_us = timing.get("charge_time")
    run_time_us = timing.get("run_time")
    qpu_access_time_us = timing.get("qpu_access_time")
    rate = limits.get("estimated_compute_cost_minor_units")
    estimated_for_minimum = rate

    provider_job_ref = None
    wait_id = getattr(sampleset, "wait_id", None)
    if callable(wait_id):
        try:
            provider_job_ref = wait_id()
        except Exception:
            provider_job_ref = None
    provider_job_ref = provider_job_ref or (sampleset.info or {}).get("problem_id")

    policy = dict(
        (request.get("account_cost_policy") or {})
        if isinstance(request.get("account_cost_policy"), Mapping)
        else {}
    )
    del policy

    return {
        "schema_version": "empire.dwave_hybrid_cqm.result.v1",
        "status": "AVAILABLE",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "provider": "dwave",
        "solver": "dwave_hybrid_cqm",
        "backend_ref": request.get("backend_ref"),
        "provider_job_ref": provider_job_ref,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "provider_call_performed": True,
        "network_call_performed": True,
        "assignment": assignment,
        "selected_variables": sorted(
            variable for variable, value in assignment.items() if value == 1
        ),
        "objective_value": round(
            _source_objective_value(problem, assignment),
            8,
        ),
        "constraints_satisfied": True,
        "wall_clock_ms": round(wall_clock_ms, 6),
        "provider_charge_time_us": charge_time_us,
        "provider_run_time_us": run_time_us,
        "qpu_access_time_us": qpu_access_time_us,
        "provider_compute_cost_minor_units": None,
        "provider_cash_cost_known": False,
        "preflight_estimated_cost_minor_units": estimated_for_minimum,
        "benchmark_evidence_only": True,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }
