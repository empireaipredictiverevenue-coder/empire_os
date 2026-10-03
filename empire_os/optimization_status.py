"""Read-only status for the Empire-owned Intelligence Optimization Fabric."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.business_optimization_product import (
    build_business_optimization_catalog,
)
from empire_os.solver_intelligence import discover_solver_runtime


OUTPUT = Path("runtime/predictive_cloud/optimization_fabric_latest.json")
AUTOMATION_STATUS = Path(
    "runtime/business_optimization/automation_latest.json"
)
SOURCE_READINESS = Path(
    "runtime/business_optimization/source_readiness_latest.json"
)
SCHEMA_VERSION = "empire.optimization.status.v2"


def build_optimization_status(
    *,
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    runtime = discover_solver_runtime(env=env)
    packages = dict(runtime.get("packages") or {})
    built_in = dict(runtime.get("built_in_solvers") or {})
    market = dict(runtime.get("market_reference_adapters") or {})
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    business_catalog = build_business_optimization_catalog()

    exact_ready = bool(built_in.get("classical_exact_reference"))
    branch_bound_ready = bool(built_in.get("empire_branch_bound"))
    annealing_ready = bool(built_in.get("empire_annealing"))
    parallel_tempering_ready = bool(
        built_in.get("empire_parallel_tempering")
    )
    qaoa_simulator_ready = bool(
        built_in.get("empire_qaoa_simulator")
    )
    tabu_ready = bool(built_in.get("empire_tabu"))
    greedy_ready = bool(built_in.get("classical_greedy_reference"))

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "mode": "OBSERVE",
        "generated_at": current.isoformat(),
        "execution_authority": "none",
        "ownership_model": "empire_owned_runtime",
        "capabilities": {
            "exact_binary_reference": exact_ready,
            "empire_branch_bound": branch_bound_ready,
            "partitioned_empire_branch_bound": branch_bound_ready,
            "safe_qubo_compiler": True,
            "empire_quantum_inspired_annealing": annealing_ready,
            "empire_parallel_tempering": parallel_tempering_ready,
            "empire_qaoa_simulator": qaoa_simulator_ready,
            "empire_tabu": tabu_ready,
            "benchmark_arena": True,
            "solver_performance_memory": True,
            "solver_policy": True,
            "compute_job_protocol": True,
            "greedy_binary_fallback": greedy_ready,
            "problem_integrity_fingerprint": True,
            "predictive_cloud_scenario_optimization": True,
            "agi_optimization_bridge": True,
            "whole_business_optimization": True,
            "business_optimization_automation": True,
            "business_optimization_source_readiness": True,
        },
        "business_optimization_product": {
            "product_key": business_catalog["product_code"],
            "product_family": business_catalog["product_name"],
            "domain_count": business_catalog["workload_count"],
            "domains": sorted(business_catalog["workloads"]),
            "third_party_runtime_required": False,
            "global_business_optimum_claimed": False,
        },
        "market_reference_capabilities": {
            "ortools_cp_sat": bool(market.get("ortools_cp_sat")),
            "dwave_local_simulated_annealing": bool(
                market.get("dwave_local_simulated_annealing")
            ),
            "dwave_hybrid_cqm_sdk": bool(market.get("dwave_hybrid_cqm")),
            "qiskit_runtime": bool(packages.get("qiskit")),
            "amazon_braket_runtime": bool(packages.get("amazon_braket")),
            "market_references_feed_production_policy": False,
        },
        "third_party_services": {
            "execution_allowed": False,
            "provider_submission_allowed": False,
            "credential_use_allowed": False,
            "network_solver_calls_allowed": False,
            "policy": "research_and_market_benchmark_reference_only",
        },
        "runtime_packages_observed": packages,
        "local_classical_reference_ready": exact_ready,
        "scalable_classical_ready": branch_bound_ready,
        "local_quantum_inspired_ready": annealing_ready,
        "external_qpu_enabled_count": 0,
        "external_qpu_adapter_ready_count": 0,
        "external_qpu_called": False,
        "third_party_runtime_allowed": False,
        "automatic_production_routing": False,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "commercial_authority": "none",
        "financial_authority": "none",
    }


def _read_runtime_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def refresh_optimization_status(repo_root: Path) -> dict[str, Any]:
    payload = build_optimization_status()
    automation = _read_runtime_json(repo_root / AUTOMATION_STATUS)
    readiness = _read_runtime_json(repo_root / SOURCE_READINESS)
    payload["business_optimization_automation"] = {
        "status": automation.get("status") or "UNAVAILABLE",
        "automation_enabled": automation.get("automation_enabled") is True,
        "processed_request_count": automation.get(
            "processed_request_count"
        ),
        "recomputed_request_count": automation.get(
            "recomputed_request_count"
        ),
        "decision_changed_count": automation.get(
            "decision_changed_count"
        ),
        "third_party_service_called": automation.get(
            "third_party_service_called"
        ),
        "automatic_business_action_allowed": automation.get(
            "automatic_business_action_allowed"
        ),
        "ready_workload_count": readiness.get("ready_workload_count"),
        "blocked_workload_count": readiness.get(
            "blocked_workload_count"
        ),
        "generated_request_count": readiness.get(
            "generated_request_count"
        ),
        "synthetic_economics_generated": readiness.get(
            "synthetic_economics_generated"
        ),
        "execution_authority": "none",
    }
    path = repo_root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
