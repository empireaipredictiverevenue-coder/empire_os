import pytest

pytest.importorskip("dimod")
pytest.importorskip("dwave.system")

from empire_os.optimization_problem_factory import build_problem_ir
from empire_os.solver_adapters.dwave_hybrid_cqm import (
    build_readiness,
    compile_cqm,
    credential_presence,
    discover_limits,
    submit,
)


def _problem():
    return build_problem_ir(
        workload_key="dwave_cqm_fixture",
        workload_type="generic_binary_portfolio",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=[
            {"variable": "x::a", "evidence_refs": ["ev:a"]},
            {"variable": "x::b", "evidence_refs": ["ev:b"]},
        ],
        objective={
            "sense": "MAXIMIZE",
            "linear": {"x::a": 10, "x::b": 7},
            "quadratic": {},
        },
        constraints=[
            {
                "name": "budget_like",
                "coefficients": {"x::a": 2, "x::b": 1},
                "sense": "<=",
                "rhs": 2,
            }
        ],
        time_budget_ms=6000,
        cost_budget_minor_units=100,
        representations=("CQM",),
    )


def _request(problem):
    return {
        "status": "READY",
        "request_id": "qpu:test",
        "problem_fingerprint": problem["problem_fingerprint"],
        "provider": "dwave",
        "solver": "dwave_hybrid_cqm",
        "backend_ref": "dwave:hybrid-cqm",
        "time_budget_ms": 6000,
        "cost_budget_minor_units": 100,
        "approval_ref": "founder:bounded-external-qpu-benchmark:2026-10-02",
    }


def _policy(rate=1):
    return {
        "currency": "GBP",
        "minor_units_per_quota_second": rate,
        "evidence_ref": "account-cost-policy:test",
    }


def test_compile_cqm_preserves_general_linear_constraint():
    problem = _problem()
    result = compile_cqm(problem)

    assert result["status"] == "AVAILABLE"
    assert result["problem_fingerprint"] == problem["problem_fingerprint"]
    assert result["variable_count"] == 2
    assert result["constraint_count"] == 1
    assert list(result["cqm"].constraints) == ["budget_like"]
    assert result["provider_call_performed"] is False


def test_credential_presence_exposes_no_secret_value():
    result = credential_presence(
        env={"DWAVE_API_TOKEN": "super-secret-token"}
    )

    assert result["credential_material_present"] is True
    assert result["token_env_present"] is True
    assert result["credential_values_exposed"] is False
    assert "super-secret-token" not in repr(result)


def test_readiness_holds_without_credentials_and_cost_policy():
    problem = _problem()
    result = build_readiness(
        request=_request(problem),
        problem=problem,
        env={},
        account_cost_policy=None,
    )

    assert result["status"] == "HELD"
    assert "dwave_credentials_required" in result["readiness_blockers"]
    assert "verified_account_cost_policy_required" in result[
        "readiness_blockers"
    ]
    assert result["network_call_performed"] is False


class _FakeSampler:
    def min_time_limit(self, cqm):
        assert cqm.num_variables() == 2
        return 5.0


def test_limit_discovery_enforces_provider_minimum_and_budget():
    problem = _problem()
    request = _request(problem)
    readiness = build_readiness(
        request=request,
        problem=problem,
        env={"DWAVE_API_TOKEN": "present"},
        account_cost_policy=_policy(rate=10),
    )

    result = discover_limits(
        readiness=readiness,
        request=request,
        problem=problem,
        allow_network_discovery=True,
        sampler_factory=_FakeSampler,
    )

    assert result["status"] == "READY_TO_SUBMIT"
    assert result["minimum_time_limit_seconds"] == 5.0
    assert result["estimated_compute_cost_minor_units"] == 50.0
    assert result["provider_call_performed"] is False


def test_limit_discovery_holds_when_minimum_cost_exceeds_cap():
    problem = _problem()
    request = _request(problem)
    request["cost_budget_minor_units"] = 20
    readiness = build_readiness(
        request=request,
        problem=problem,
        env={"DWAVE_API_TOKEN": "present"},
        account_cost_policy=_policy(rate=10),
    )

    result = discover_limits(
        readiness=readiness,
        request=request,
        problem=problem,
        allow_network_discovery=True,
        sampler_factory=_FakeSampler,
    )

    assert result["status"] == "HELD"
    assert "dwave_estimated_cost_exceeds_or_lacks_budget" in result[
        "readiness_blockers"
    ]


def test_submit_never_calls_provider_without_explicit_external_call_gate():
    problem = _problem()
    limits = {
        "status": "READY_TO_SUBMIT",
        "selected_time_limit_seconds": 5.0,
        "estimated_compute_cost_minor_units": 50.0,
    }

    result = submit(
        limits=limits,
        request=_request(problem),
        problem=problem,
        perform_external_call=False,
    )

    assert result["status"] == "HELD"
    assert result["reason"] == "external_provider_call_not_authorized"
    assert result["provider_call_performed"] is False
