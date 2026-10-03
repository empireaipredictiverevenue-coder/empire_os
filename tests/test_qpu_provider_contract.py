from empire_os.intelligence_optimization_fabric import (
    build_allocation_fabric_plan,
)
from empire_os.qpu_provider_contract import (
    build_qpu_benchmark_request,
    normalize_qpu_benchmark_result,
)
from empire_os.quantum_optimization import (
    build_allocation_optimization_problem,
)


def _source():
    return build_allocation_optimization_problem(
        options=[
            {
                "prospect_id": "p1",
                "buyer_id": "b1",
                "expected_value_cents": 1000,
                "evidence_refs": ["ev:p1-b1"],
            }
        ],
        buyer_capacities={"b1": 1},
    )


def _runtime(*, adapter=True, provider_enabled=True):
    return {
        "packages": {
            "ortools": True,
            "pyomo": False,
            "dimod": True,
            "dwave_samplers": True,
            "dwave_system": False,
            "qiskit": True,
            "pennylane": False,
            "amazon_braket": False,
            "cirq": False,
        },
        "provider_flags": {
            "ibm_quantum": provider_enabled,
            "dwave": False,
            "amazon_braket": False,
        },
        "empire_adapters": {
            "ortools_cp_sat": True,
            "pyomo_mip": False,
            "local_bqm_quantum_inspired": True,
            "dwave_hybrid_cqm": False,
            "ibm_qaoa": adapter,
            "amazon_braket_qaoa": False,
            "pennylane_qaoa": False,
        },
    }


def _benchmark(plan):
    return {
        "status": "AVAILABLE",
        "problem_fingerprint": plan["problem_fingerprint"],
        "baseline_solver": "classical_exact_binary_ir",
        "run_count": 2,
    }


def _plan(*, cost_budget=100, allow=True, adapter=True, enabled=True):
    return build_allocation_fabric_plan(
        _source(),
        runtime=_runtime(
            adapter=adapter,
            provider_enabled=enabled,
        ),
        time_budget_ms=2000,
        cost_budget_minor_units=cost_budget,
        allow_external_qpu_benchmark=allow,
    )


def test_qpu_request_is_held_without_operator_authorization():
    request = build_qpu_benchmark_request(
        _plan(),
        provider="ibm_quantum",
        solver_key="ibm_qaoa",
        backend_ref="backend:placeholder",
        evidence_refs=["benchmark:intent"],
        baseline_benchmark=_benchmark(_plan()),
        external_benchmark_authorized=False,
        approval_ref=None,
    )

    assert request["status"] == "HELD"
    assert (
        "operator_external_qpu_benchmark_authorization_required"
        in request["readiness_blockers"]
    )
    assert request["provider_call_performed"] is False
    assert request["funds_committed"] is False


def test_qpu_request_requires_cost_budget():
    request = build_qpu_benchmark_request(
        _plan(cost_budget=None),
        provider="ibm_quantum",
        solver_key="ibm_qaoa",
        backend_ref="backend:placeholder",
        evidence_refs=["benchmark:intent"],
        baseline_benchmark=_benchmark(_plan(cost_budget=None)),
        external_benchmark_authorized=True,
        approval_ref="approval:test",
    )

    assert request["status"] == "UNAVAILABLE"
    assert request["reason"] == "cost_budget_required_for_external_qpu"


def test_qpu_request_requires_installed_adapter_and_provider_enable():
    plan = _plan(adapter=False, enabled=False)
    request = build_qpu_benchmark_request(
        plan,
        provider="ibm_quantum",
        solver_key="ibm_qaoa",
        backend_ref="backend:placeholder",
        evidence_refs=["benchmark:intent"],
        baseline_benchmark=_benchmark(plan),
        external_benchmark_authorized=True,
        approval_ref="approval:test",
    )

    assert request["status"] == "HELD"
    assert "empire_provider_adapter_not_implemented" in request[
        "readiness_blockers"
    ]
    assert "provider_not_explicitly_enabled" in request[
        "readiness_blockers"
    ]


def test_qpu_request_stays_held_even_when_legacy_gates_pass():
    plan = _plan()
    request = build_qpu_benchmark_request(
        plan,
        provider="ibm_quantum",
        solver_key="ibm_qaoa",
        backend_ref="backend:placeholder",
        evidence_refs=["benchmark:intent"],
        baseline_benchmark=_benchmark(plan),
        external_benchmark_authorized=True,
        approval_ref="approval:test",
    )

    assert request["status"] == "HELD"
    assert (
        "third_party_service_execution_prohibited_by_empire_policy"
        in request["readiness_blockers"]
    )
    assert request["provider_submission_allowed"] is False
    assert request["third_party_service_execution_allowed"] is False
    assert request["research_only"] is True
    assert request["provider_call_performed"] is False
    assert request["provider_credentials_inspected"] is False
    assert request["classical_baseline_verified"] is True
    assert request["approval_ref"] == "approval:test"
    assert request["quantum_advantage_claimed"] is False
    assert request["execution_authority"] == "none"




def _offline_research_request(plan):
    return {
        "status": "READY",
        "request_id": "offline-market-reference",
        "problem_fingerprint": plan["problem_fingerprint"],
        "provider": "ibm_quantum",
        "solver": "ibm_qaoa",
        "backend_ref": "backend:placeholder",
    }

def test_provider_result_must_match_problem_fingerprint_and_include_cost():
    plan = _plan()
    request = _offline_research_request(plan)

    mismatch = normalize_qpu_benchmark_result(
        request=request,
        provider_result={
            "problem_fingerprint": "wrong",
            "objective_value": 1000,
            "constraints_satisfied": True,
            "wall_clock_ms": 100,
            "provider_compute_cost_minor_units": 5,
        },
    )
    assert mismatch["status"] == "UNAVAILABLE"
    assert mismatch["reason"] == "problem_fingerprint_mismatch"

    missing_cost = normalize_qpu_benchmark_result(
        request=request,
        provider_result={
            "problem_fingerprint": request["problem_fingerprint"],
            "objective_value": 1000,
            "constraints_satisfied": True,
            "wall_clock_ms": 100,
        },
    )
    assert missing_cost["status"] == "UNAVAILABLE"
    assert "provider_compute_cost_minor_units" in missing_cost[
        "missing_fields"
    ]


def test_normalized_qpu_result_is_still_benchmark_evidence_only():
    plan = _plan()
    request = _offline_research_request(plan)

    result = normalize_qpu_benchmark_result(
        request=request,
        provider_result={
            "problem_fingerprint": request["problem_fingerprint"],
            "provider": "ibm_quantum",
            "backend_ref": "backend:placeholder",
            "provider_job_ref": "ibm-job:observed-1",
            "observed_at": "2026-10-02T21:35:00+00:00",
            "provider_call_performed": True,
            "objective_value": 1000,
            "constraints_satisfied": True,
            "wall_clock_ms": 100,
            "provider_compute_cost_minor_units": 5,
            "queue_time_ms": 20,
        },
    )

    assert result["status"] == "AVAILABLE"
    assert result["benchmark_evidence_only"] is True
    assert result["provider_call_performed"] is True
    assert result["production_promotion_ready"] is False
    assert result["quantum_advantage_claimed"] is False
    assert result["execution_authority"] == "none"


def test_normalizer_refuses_unproven_provider_call():
    plan = _plan()
    request = _offline_research_request(plan)

    result = normalize_qpu_benchmark_result(
        request=request,
        provider_result={
            "problem_fingerprint": request["problem_fingerprint"],
            "provider": "ibm_quantum",
            "backend_ref": "backend:placeholder",
            "provider_job_ref": "ibm-job:unproven",
            "observed_at": "2026-10-02T21:35:00+00:00",
            "provider_call_performed": False,
            "objective_value": 1000,
            "constraints_satisfied": True,
            "wall_clock_ms": 100,
            "provider_compute_cost_minor_units": 5,
        },
    )

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "provider_call_evidence_required"
    assert result["provider_call_performed"] is False


def test_normalizer_requires_timezone_aware_provider_observation():
    plan = _plan()
    request = _offline_research_request(plan)

    result = normalize_qpu_benchmark_result(
        request=request,
        provider_result={
            "problem_fingerprint": request["problem_fingerprint"],
            "provider": "ibm_quantum",
            "backend_ref": "backend:placeholder",
            "provider_job_ref": "ibm-job:observed-2",
            "observed_at": "2026-10-02T21:35:00",
            "provider_call_performed": True,
            "objective_value": 1000,
            "constraints_satisfied": True,
            "wall_clock_ms": 100,
            "provider_compute_cost_minor_units": 5,
        },
    )

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "provider_result_evidence_invalid"
    assert "timezone-aware" in result["detail"]

def test_qpu_request_requires_same_problem_classical_baseline():
    plan = _plan()
    request = build_qpu_benchmark_request(
        plan,
        provider="ibm_quantum",
        solver_key="ibm_qaoa",
        backend_ref="backend:placeholder",
        evidence_refs=["benchmark:intent"],
        baseline_benchmark={
            "status": "AVAILABLE",
            "problem_fingerprint": "different",
            "baseline_solver": "classical_exact_binary_ir",
            "run_count": 3,
        },
        external_benchmark_authorized=True,
        approval_ref="approval:test",
    )

    assert request["status"] == "HELD"
    assert "same_problem_classical_benchmark_required" in request[
        "readiness_blockers"
    ]
