from empire_os.optimization_problem_factory import (
    compile_allocation_problem,
)
from empire_os.quantum_optimization import (
    build_allocation_optimization_problem,
)
from empire_os.quantum_provider_plan import (
    build_dwave_direct_qpu_plan,
    build_dwave_hybrid_cqm_plan,
    build_dwave_provider_matrix,
)


def _problem(*, capacity=1, time_budget_ms=2000, cost_budget=100):
    source = build_allocation_optimization_problem(
        options=[
            {
                "prospect_id": "p1",
                "buyer_id": "b1",
                "expected_value_cents": 1000,
                "evidence_refs": ["ev:1"],
            },
            {
                "prospect_id": "p1",
                "buyer_id": "b2",
                "expected_value_cents": 800,
                "evidence_refs": ["ev:2"],
            },
        ],
        buyer_capacities={"b1": capacity, "b2": capacity},
    )
    return compile_allocation_problem(
        source,
        time_budget_ms=time_budget_ms,
        cost_budget_minor_units=cost_budget,
    )


def test_dwave_hybrid_plan_is_disabled_by_default():
    plan = build_dwave_hybrid_cqm_plan(_problem())

    assert plan["status"] == "AVAILABLE"
    assert plan["submission_ready"] is False
    assert "external_provider_not_enabled" in plan["blockers"]
    assert "external_qpu_benchmark_not_authorized_for_route" in plan["blockers"]
    assert plan["external_solver_called"] is False
    assert plan["execution_authority"] == "none"


def test_dwave_hybrid_plan_can_become_submission_ready_only_after_explicit_gates():
    plan = build_dwave_hybrid_cqm_plan(
        _problem(),
        provider_enabled=True,
        allow_external_benchmark=True,
    )

    assert plan["submission_ready"] is True
    assert plan["blockers"] == []
    assert plan["credential_presence_checked"] is False
    assert plan["external_solver_called"] is False


def test_direct_qpu_plan_never_skips_topology_embedding_preflight():
    plan = build_dwave_direct_qpu_plan(
        _problem(),
        provider_enabled=True,
        allow_external_benchmark=True,
        num_reads=250,
    )

    assert plan["safe_qubo"]["status"] == "AVAILABLE"
    assert plan["submission_ready"] is False
    assert "qpu_topology_embedding_preflight_required" in plan["blockers"]
    assert plan["num_reads"] == 250
    assert plan["qpu_direct"] is True
    assert plan["quantum_advantage_claimed"] is False


def test_direct_qpu_plan_rejects_problem_without_safe_qubo():
    problem = _problem(capacity=2)
    plan = build_dwave_direct_qpu_plan(
        problem,
        provider_enabled=True,
        allow_external_benchmark=True,
    )

    assert plan["submission_ready"] is False
    assert any(
        blocker.startswith("safe_qubo_required:")
        for blocker in plan["blockers"]
    )


def test_provider_matrix_reads_only_explicit_enable_flag():
    matrix = build_dwave_provider_matrix(
        _problem(),
        env={"EMPIRE_QPU_DWAVE_ENABLED": "true"},
        allow_external_benchmark=False,
    )

    assert matrix["lanes"]["hybrid_cqm"]["provider_enabled"] is True
    assert matrix["lanes"]["hybrid_cqm"]["submission_ready"] is False
    assert matrix["any_submission_ready"] is False
    assert matrix["external_solver_called"] is False
