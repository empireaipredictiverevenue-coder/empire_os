"""Canonical coding-team batch for Predictive Cloud / AGI / Quantum work."""
from __future__ import annotations

from empire_os.execution_plane_dispatcher import ExecutionRequest


def predictive_cloud_coding_team_requests() -> tuple[ExecutionRequest, ...]:
    return (
        ExecutionRequest(
            request_id="predictive-quantum-exchange-bridge-v1",
            capability="backend_code",
            department="revenue",
            objective=(
                "Implement the governed Revenue Exchange -> Hybrid Optimization "
                "bridge. Create empire_os/revenue_exchange_optimization_bridge.py "
                "and tests/test_revenue_exchange_optimization_bridge.py. Only "
                "allocation proposals already marked ready_for_operator_match_review "
                "with explicit expected_value_cents and evidence_refs may enter the "
                "optimizer. Use build_allocation_optimization_problem and "
                "build_hybrid_optimization_plan. Preserve Unknown != 0. No allocation "
                "execution, pricing mutation, terms acceptance, payment action, or "
                "revenue recognition. Return recommendation-only preview packets."
            ),
            authority="internal_write",
            risk_class="medium",
            source_ref="architecture:agi_predictive_cloud_quantum_v1",
            allowed_paths=(
                "empire_os/revenue_exchange_optimization_bridge.py",
                "tests/test_revenue_exchange_optimization_bridge.py",
            ),
            lease_resources=(
                "path:empire_os/revenue_exchange_optimization_bridge.py",
                "path:tests/test_revenue_exchange_optimization_bridge.py",
            ),
            evidence_domains=(
                "revenue_exchange",
                "buyer_capacity",
                "expected_revenue_value",
                "hybrid_optimization",
            ),
            success_condition=(
                "Evidence-ready proposals produce a hybrid optimization preview; "
                "missing economics/evidence fail closed; no execution authority."
            ),
            required_tests=(
                "tests/test_revenue_exchange_optimization_bridge.py",
                "tests/test_quantum_optimization.py",
                "tests/test_hybrid_optimization.py",
            ),
            priority=95,
            ai_behavior_change=True,
        ),
        ExecutionRequest(
            request_id="predictive-action-portfolio-design-v1",
            capability="parallel_backend_code",
            department="strategy",
            objective=(
                "Produce an OBSERVE-only implementation design for the portfolio "
                "Next-Best-Action optimizer. Review the existing Predictive Revenue "
                "NBA contract, Hybrid Optimization contract and authority boundaries. "
                "Specify inputs, constraints, deterministic baseline, QUBO/CQM export "
                "shape, edge cases and required tests. Do not mutate repository files."
            ),
            authority="observe",
            risk_class="medium",
            source_ref="architecture:agi_predictive_cloud_quantum_v1",
            evidence_domains=(
                "predictive_revenue",
                "next_best_action",
                "portfolio_optimization",
            ),
            success_condition=(
                "Pi produces a bounded implementation design without repository "
                "mutation or authority expansion."
            ),
            required_tests=(
                "tests/test_predictive_revenue_formula.py",
                "tests/test_hybrid_optimization.py",
            ),
            priority=91,
            ai_behavior_change=True,
        ),
        ExecutionRequest(
            request_id="predictive-action-portfolio-implementation-v2",
            capability="backend_code",
            department="strategy",
            objective=(
                "Implement the portfolio Next-Best-Action optimizer in "
                "empire_os/action_portfolio_optimization.py with tests in "
                "tests/test_action_portfolio_optimization.py. Consume only "
                "evidence-backed expected_incremental_value_cents from the existing "
                "Predictive Revenue NBA layer. Optimize a bounded action portfolio "
                "under explicit action budget/capacity constraints. Provide a "
                "deterministic classical baseline plus a provider-neutral binary "
                "optimization export suitable for future QUBO/CQM benchmarking. "
                "Missing costs, values, capacities or evidence stay UNKNOWN. No "
                "external execution or authority expansion."
            ),
            authority="internal_write",
            risk_class="medium",
            source_ref="architecture:agi_predictive_cloud_quantum_v1",
            allowed_paths=(
                "empire_os/action_portfolio_optimization.py",
                "tests/test_action_portfolio_optimization.py",
            ),
            lease_resources=(
                "path:empire_os/action_portfolio_optimization.py",
                "path:tests/test_action_portfolio_optimization.py",
            ),
            evidence_domains=(
                "predictive_revenue",
                "next_best_action",
                "portfolio_optimization",
            ),
            success_condition=(
                "Optimizer selects evidence-backed actions within explicit constraints "
                "and never converts recommendation into execution."
            ),
            required_tests=(
                "tests/test_action_portfolio_optimization.py",
                "tests/test_predictive_revenue_formula.py",
                "tests/test_hybrid_optimization.py",
            ),
            priority=90,
            ai_behavior_change=True,
        ),
        ExecutionRequest(
            request_id="predictive-algorithm-verification-hardening-v1",
            capability="verification",
            department="engineering",
            objective=(
                "Independently review the new Predictive Revenue, Predictive Cloud, "
                "Future-Trend, Quantum Optimization, Hybrid Optimization and AGI "
                "Orchestration modules for truth-boundary regressions. Verify Unknown "
                "!= 0, predicted revenue != actual revenue, quantum advantage is never "
                "claimed without benchmark evidence, and no specialist packet grants "
                "commercial/financial/accounting authority. Produce verification "
                "results only; do not modify production state."
            ),
            authority="observe",
            risk_class="high",
            source_ref="architecture:agi_predictive_cloud_quantum_v1",
            evidence_domains=(
                "predictive_revenue",
                "predictive_cloud",
                "future_trend",
                "quantum_optimization",
                "agi_orchestration",
            ),
            success_condition=(
                "Independent verification identifies any truth, authority, or "
                "regression issues before production promotion."
            ),
            required_tests=(
                "tests/test_predictive_revenue_formula.py",
                "tests/test_predictive_cloud_formula.py",
                "tests/test_future_trend_intelligence.py",
                "tests/test_quantum_optimization.py",
                "tests/test_hybrid_optimization.py",
                "tests/test_agi_orchestrator.py",
                "tests/test_agi_control_api.py",
            ),
            priority=88,
            ai_behavior_change=True,
        ),
        ExecutionRequest(
            request_id="predictive-algorithm-integration-qa-v1",
            capability="integration_qa",
            department="engineering",
            objective=(
                "Run integration QA across the Predictive Revenue -> Predictive Cloud "
                "-> Future-Trend -> AGI Orchestration -> Quantum/Hybrid Optimization "
                "contracts. Check schema compatibility, evidence lineage, read-only "
                "authority, deterministic behavior, and regression-test coverage. "
                "Report blockers and evidence. Do not mutate production or merge code."
            ),
            authority="observe",
            risk_class="high",
            source_ref="architecture:agi_predictive_cloud_quantum_v1",
            evidence_domains=(
                "predictive_revenue",
                "predictive_cloud",
                "agi",
                "quantum",
                "integration_qa",
            ),
            success_condition=(
                "Cross-module contract is independently validated with no hidden "
                "execution or revenue-truth escalation."
            ),
            required_tests=(
                "tests/test_predictive_revenue_formula.py",
                "tests/test_predictive_cloud_formula.py",
                "tests/test_future_trend_intelligence.py",
                "tests/test_quantum_optimization.py",
                "tests/test_hybrid_optimization.py",
                "tests/test_agi_orchestrator.py",
                "tests/test_agi_control_api.py",
            ),
            priority=85,
            ai_behavior_change=True,
        ),
    )
