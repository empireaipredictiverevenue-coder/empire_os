"""Runtime-aware solver discovery and routing for Empire Optimization Fabric V2.

Discovery is local/read-only. External QPU execution is never enabled merely by
finding an SDK; an explicit Empire feature flag and an implemented adapter are
both required.
"""
from __future__ import annotations

from importlib.util import find_spec
import os
from typing import Any, Mapping

from empire_os.solver_adapters.greedy_binary import (
    is_safe_monotone_greedy_problem,
)

from empire_os.solver_adapters.exact_binary import DEFAULT_MAX_VARIABLES


SCHEMA_VERSION = "empire.solver_intelligence.v1"
SUPPORTED_EXACT_WORKLOADS = frozenset({
    "buyer_allocation",
    "predictive_action_portfolio",
})


def _installed(module: str) -> bool:
    try:
        return find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _flag(name: str, env: Mapping[str, str]) -> bool:
    return str(env.get(name) or "").strip().lower() in {
        "1", "true", "yes", "on", "enabled",
    }


def discover_solver_runtime(
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Inspect installed SDKs and explicit Empire provider-enable flags."""
    source = dict(os.environ if env is None else env)
    packages = {
        "ortools": _installed("ortools"),
        "pyomo": _installed("pyomo"),
        "dimod": _installed("dimod"),
        "dwave_samplers": _installed("dwave.samplers"),
        "dwave_system": _installed("dwave.system"),
        "qiskit": _installed("qiskit"),
        "pennylane": _installed("pennylane"),
        "amazon_braket": _installed("braket"),
        "cirq": _installed("cirq"),
    }
    provider_flags = {
        "ibm_quantum": _flag("EMPIRE_QPU_IBM_ENABLED", source),
        "dwave": _flag("EMPIRE_QPU_DWAVE_ENABLED", source),
        "amazon_braket": _flag("EMPIRE_QPU_BRAKET_ENABLED", source),
    }

    return {
        "schema_version": "empire.solver_runtime.v1",
        "status": "AVAILABLE",
        "packages": packages,
        "provider_flags": provider_flags,
        "built_in_solvers": {
            "classical_exact_reference": True,
            "classical_greedy_reference": True,
            "empire_branch_bound": True,
            "empire_annealing": True,
            "empire_parallel_tempering": True,
            "empire_qaoa_simulator": True,
            "empire_tabu": True,
        },
        "empire_adapters": {
            "classical_exact_reference": True,
            "classical_greedy_reference": True,
            "empire_branch_bound": True,
            "empire_annealing": True,
            "empire_parallel_tempering": True,
            "empire_qaoa_simulator": True,
            "empire_tabu": True,
        },
        "market_reference_adapters": {
            "ortools_cp_sat": bool(packages.get("ortools")),
            "dwave_local_simulated_annealing": (
                bool(packages.get("dimod"))
                and bool(packages.get("dwave_samplers"))
            ),
            "dwave_hybrid_cqm": bool(packages.get("dwave_system")),
            "ibm_qaoa": False,
            "amazon_braket_qaoa": False,
            "pennylane_qaoa": False,
        },
        "third_party_service_execution_enabled": False,
        "external_provider_execution_enabled": False,
        "external_solver_called": False,
        "credentials_inspected": False,
        "execution_authority": "none",
    }


def _candidate(
    *,
    key: str,
    family: str,
    representation: str,
    installed: bool,
    adapter_implemented: bool,
    externally_enabled: bool | None,
    external: bool,
) -> dict[str, Any]:
    ready = installed and adapter_implemented
    if external:
        ready = ready and externally_enabled is True
    blockers: list[str] = []
    if not installed:
        blockers.append("runtime_dependency_not_installed")
    if not adapter_implemented:
        blockers.append("empire_adapter_not_implemented")
    if external and externally_enabled is not True:
        blockers.append("external_provider_not_enabled")
    return {
        "solver": key,
        "family": family,
        "representation": representation,
        "installed": installed,
        "empire_adapter_implemented": adapter_implemented,
        "external": external,
        "explicit_provider_enable": externally_enabled,
        "runnable": ready,
        "blockers": blockers,
    }


def build_solver_candidates(
    problem: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> list[dict[str, Any]]:
    reps = {
        str(value).strip().upper()
        for value in (problem.get("representations") or ())
        if str(value).strip()
    }
    packages = dict(runtime.get("packages") or {})
    adapters = dict(runtime.get("empire_adapters") or {})
    flags = dict(runtime.get("provider_flags") or {})

    candidates = [
        {
            "solver": "empire_branch_bound",
            "family": "empire_classical_branch_bound",
            "representation": "BINARY_LINEAR",
            "installed": True,
            "empire_adapter_implemented": True,
            "external": False,
            "explicit_provider_enable": None,
            "runnable": (
                str(problem.get("variable_type") or "").strip().upper()
                == "BINARY"
                and not bool(
                    dict(problem.get("objective") or {}).get("quadratic")
                )
                and problem.get("time_budget_ms") is not None
            ),
            "blockers": (
                []
                if (
                    str(problem.get("variable_type") or "").strip().upper()
                    == "BINARY"
                    and not bool(
                        dict(problem.get("objective") or {}).get("quadratic")
                    )
                    and problem.get("time_budget_ms") is not None
                )
                else ["binary_linear_problem_with_time_budget_required"]
            ),
            "empire_owned": True,
            "purpose": "primary_candidate",
        },
        {
            "solver": "empire_annealing",
            "family": "empire_quantum_inspired_annealing",
            "representation": "QUBO",
            "installed": True,
            "empire_adapter_implemented": True,
            "external": False,
            "explicit_provider_enable": None,
            "runnable": "QUBO" in reps,
            "blockers": [] if "QUBO" in reps else ["qubo_representation_required"],
            "empire_owned": True,
            "purpose": "benchmark_only",
        },
        {
            "solver": "empire_parallel_tempering",
            "family": "empire_quantum_inspired_parallel_tempering",
            "representation": "QUBO",
            "installed": True,
            "empire_adapter_implemented": True,
            "external": False,
            "explicit_provider_enable": None,
            "runnable": "QUBO" in reps,
            "blockers": [] if "QUBO" in reps else ["qubo_representation_required"],
            "empire_owned": True,
            "purpose": "benchmark_only",
        },
        {
            "solver": "empire_tabu",
            "family": "empire_quantum_inspired_tabu",
            "representation": "QUBO",
            "installed": True,
            "empire_adapter_implemented": True,
            "external": False,
            "explicit_provider_enable": None,
            "runnable": "QUBO" in reps,
            "blockers": [] if "QUBO" in reps else ["qubo_representation_required"],
            "empire_owned": True,
            "purpose": "benchmark_only",
        },
        {
            "solver": "empire_qaoa_simulator",
            "family": "empire_quantum_qaoa_statevector_simulator",
            "representation": "QUBO",
            "installed": True,
            "empire_adapter_implemented": True,
            "external": False,
            "explicit_provider_enable": None,
            "runnable": (
                "QUBO" in reps
                and int(problem.get("variable_count") or 0) <= 10
            ),
            "blockers": (
                []
                if (
                    "QUBO" in reps
                    and int(problem.get("variable_count") or 0) <= 10
                )
                else ["qubo_and_statevector_limit_required"]
            ),
            "empire_owned": True,
            "purpose": "benchmark_only",
        },
        _candidate(
            key="ortools_cp_sat",
            family="classical_cp_sat",
            representation="BINARY_CONSTRAINED",
            installed=bool(packages.get("ortools")),
            adapter_implemented=bool(adapters.get("ortools_cp_sat")),
            externally_enabled=None,
            external=False,
        ),
        _candidate(
            key="pyomo_mip",
            family="classical_mip",
            representation="LINEAR_INTEGER",
            installed=bool(packages.get("pyomo")),
            adapter_implemented=bool(adapters.get("pyomo_mip")),
            externally_enabled=None,
            external=False,
        ),
    ]
    if "QUBO" in reps:
        candidates.extend([
            _candidate(
                key="local_bqm_quantum_inspired",
                family="quantum_inspired",
                representation="QUBO",
                installed=(
                    bool(packages.get("dimod"))
                    and bool(packages.get("dwave_samplers"))
                ),
                adapter_implemented=bool(
                    adapters.get("local_bqm_quantum_inspired")
                ),
                externally_enabled=None,
                external=False,
            ),
            _candidate(
                key="ibm_qaoa",
                family="qpu_qaoa",
                representation="QUBO",
                installed=bool(packages.get("qiskit")),
                adapter_implemented=bool(adapters.get("ibm_qaoa")),
                externally_enabled=bool(flags.get("ibm_quantum")),
                external=True,
            ),
            _candidate(
                key="amazon_braket_qaoa",
                family="qpu_qaoa",
                representation="QUBO",
                installed=bool(packages.get("amazon_braket")),
                adapter_implemented=bool(adapters.get("amazon_braket_qaoa")),
                externally_enabled=bool(flags.get("amazon_braket")),
                external=True,
            ),
            _candidate(
                key="pennylane_qaoa",
                family="hybrid_quantum",
                representation="QUBO",
                installed=bool(packages.get("pennylane")),
                adapter_implemented=bool(adapters.get("pennylane_qaoa")),
                externally_enabled=None,
                external=False,
            ),
        ])
    if "CQM" in reps:
        candidates.append(
            _candidate(
                key="dwave_hybrid_cqm",
                family="hybrid_quantum",
                representation="CQM",
                installed=bool(packages.get("dwave_system")),
                adapter_implemented=bool(adapters.get("dwave_hybrid_cqm")),
                externally_enabled=bool(flags.get("dwave")),
                external=True,
            )
        )

    for row in candidates:
        if row.get("solver") in {
            "ortools_cp_sat",
            "pyomo_mip",
            "local_bqm_quantum_inspired",
            "ibm_qaoa",
            "amazon_braket_qaoa",
            "pennylane_qaoa",
            "dwave_hybrid_cqm",
        }:
            row["market_reference_only"] = True
            row["purpose"] = "market_reference_only"
            row["runnable"] = False
            row["blockers"] = sorted(set([
                *row.get("blockers", []),
                "third_party_runtime_not_allowed",
            ]))
        if (
            row["solver"] in {"ortools_cp_sat", "pyomo_mip"}
            and problem.get("time_budget_ms") is None
        ):
            row["runnable"] = False
            row["blockers"] = sorted(set([
                *row["blockers"],
                "time_budget_required",
            ]))
        if row["external"] and problem.get("time_budget_ms") is None:
            row["runnable"] = False
            row["blockers"] = sorted(set([
                *row["blockers"],
                "time_budget_required_for_external_solver",
            ]))
        if (
            row["external"]
            and problem.get("cost_budget_minor_units") is None
        ):
            row["runnable"] = False
            row["blockers"] = sorted(set([
                *row["blockers"],
                "cost_budget_required_for_external_solver",
            ]))
    return candidates


def route_solver(
    problem: Mapping[str, Any],
    *,
    runtime: Mapping[str, Any] | None = None,
    exact_variable_limit: int = DEFAULT_MAX_VARIABLES,
    allow_external_qpu_benchmark: bool = False,
) -> dict[str, Any]:
    """Choose a safe primary lane and expose eligible benchmark candidates."""
    if exact_variable_limit <= 0:
        raise ValueError("exact_variable_limit must be positive")
    if str(problem.get("status") or "").strip().upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "execution_authority": "none",
        }

    runtime_packet = dict(runtime or discover_solver_runtime())
    variable_count = int(problem.get("variable_count") or 0)
    workload_type = str(problem.get("workload_type") or "").strip()
    candidates = build_solver_candidates(problem, runtime_packet)

    exact_ir_supported = (
        str(problem.get("variable_type") or "").strip().upper() == "BINARY"
        and variable_count <= exact_variable_limit
    )
    if exact_ir_supported:
        primary = "classical_exact_reference"
        primary_quality = "OPTIMAL_REFERENCE"
        primary_reason = "small_binary_ir_exact_reference"
    else:
        branch_bound = next(
            (
                row
                for row in candidates
                if row["solver"] == "empire_branch_bound"
            ),
            None,
        )
        if branch_bound and branch_bound["runnable"]:
            primary = "empire_branch_bound"
            primary_quality = "BOUNDED_EXACT_OR_INCUMBENT"
            primary_reason = "empire_owned_scalable_binary_linear_solver"
        elif is_safe_monotone_greedy_problem(problem):
            primary = "classical_greedy_reference"
            primary_quality = "HEURISTIC_REFERENCE"
            primary_reason = "empire_owned_safe_monotone_fallback"
        else:
            primary = None
            primary_quality = "UNAVAILABLE"
            primary_reason = "no_empire_owned_solver_for_workload"

    benchmark_lanes: list[dict[str, Any]] = []
    for row in candidates:
        if row["solver"] == "empire_branch_bound":
            if row["solver"] != primary:
                benchmark_lanes.append({
                    **row,
                    "purpose": "empire_reference",
                })
            continue
        if row["solver"] in {
            "empire_annealing",
            "empire_parallel_tempering",
            "empire_tabu",
        }:
            benchmark_lanes.append({
                **row,
                "purpose": "empire_quantum_inspired_benchmark",
            })
            continue
        if row["solver"] == "empire_qaoa_simulator":
            benchmark_lanes.append({
                **row,
                "purpose": "empire_quantum_simulator_benchmark",
            })
            continue
        if row.get("market_reference_only") is True:
            benchmark_lanes.append({
                **row,
                "runnable": False,
                "purpose": "market_reference_only",
            })
            continue
        if row["external"] and not allow_external_qpu_benchmark:
            benchmark_lanes.append({
                **row,
                "runnable": False,
                "blockers": sorted(set([
                    *row["blockers"],
                    "external_qpu_benchmark_not_authorized_for_route",
                ])),
                "purpose": "benchmark_only",
            })
        else:
            benchmark_lanes.append({**row, "purpose": "benchmark_only"})

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "workload_type": workload_type,
        "variable_count": variable_count,
        "exact_variable_limit": int(exact_variable_limit),
        "primary_solver": primary,
        "primary_reference_quality": primary_quality,
        "routing_reason": primary_reason,
        "benchmark_lanes": benchmark_lanes,
        "fallback_chain": [
            *(
                ["classical_exact_reference"]
                if exact_ir_supported
                else []
            ),
            *(
                ["empire_branch_bound"]
                if (
                    str(problem.get("variable_type") or "").strip().upper()
                    == "BINARY"
                    and not bool(
                        dict(problem.get("objective") or {}).get("quadratic")
                    )
                    and problem.get("time_budget_ms") is not None
                )
                else []
            ),
            *(
                ["classical_greedy_reference"]
                if is_safe_monotone_greedy_problem(problem)
                else []
            ),
        ],
        "production_solver_origin": "empire_owned",
        "third_party_runtime_allowed": False,
        "solver_execution_ready": primary is not None,
        "queue_class": (
            "optimization:small"
            if variable_count <= exact_variable_limit
            else "optimization:scalable"
        ),
        "external_qpu_benchmark_allowed": allow_external_qpu_benchmark,
        "external_solver_called": False,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }
