"""Governed first-wave assignments for the EmpireOS full-completion programme."""
from __future__ import annotations

from empire_os.execution_plane_dispatcher import ExecutionRequest
from empire_os.hermes_control import DEFAULT_BASE_BRANCH


def completion_wave1_requests() -> tuple[ExecutionRequest, ...]:
    return (
        ExecutionRequest(
            request_id="completion-marketplace-auction-readiness-v1",
            capability="backend_code",
            department="sales_revenue",
            objective=(
                "Follow the Architecture-First Engineering Doctrine. First inspect the "
                "existing marketplace, opportunity_auction, Revenue Exchange, buyer "
                "allocation and capacity contracts. Record a bounded architecture delta "
                "in docs/architecture/marketplace_auction_readiness_v1.md, then implement "
                "a canonical read-only marketplace/auction readiness model in "
                "empire_os/marketplace_auction_readiness.py with focused tests. Reuse "
                "existing canonical components; do not create a second marketplace or "
                "settlement path. The readiness model must expose inventory, buyer "
                "eligibility/capacity, bid/price evidence, auction/clearing readiness, "
                "allocation readiness, blockers and evidence refs. Unknown stays unknown. "
                "No bid execution, allocation execution, pricing mutation, terms, payment, "
                "settlement, outbound or revenue-recognition authority."
            ),
            authority="internal_write",
            risk_class="medium",
            source_ref="program:empire_os_full_completion:marketplace_auction",
            base_branch=DEFAULT_BASE_BRANCH,
            allowed_paths=(
                "empire_os/marketplace_auction_readiness.py",
                "tests/test_marketplace_auction_readiness.py",
                "docs/architecture/marketplace_auction_readiness_v1.md",
            ),
            lease_resources=(
                "domain:marketplace_auction_readiness",
                "path:empire_os/marketplace_auction_readiness.py",
                "path:tests/test_marketplace_auction_readiness.py",
                "path:docs/architecture/marketplace_auction_readiness_v1.md",
            ),
            evidence_domains=("marketplace", "opportunity_auction", "revenue_exchange", "buyer_capacity", "buyer_allocation"),
            success_condition=(
                "A deterministic read-only readiness packet truthfully identifies which "
                "marketplace/auction stages are ready or blocked, with evidence refs and "
                "zero consequential authority."
            ),
            required_tests=(
                "tests/test_marketplace_auction_readiness.py",
                "tests/test_opportunity_auction.py",
                "tests/test_revenue_exchange.py",
                "tests/test_revenue_exchange_allocation_readiness.py",
            ),
            priority=100,
        ),
        ExecutionRequest(
            request_id="completion-predictive-calibration-board-v1",
            capability="backend_code",
            department="data_quant",
            objective=(
                "Follow the Architecture-First Engineering Doctrine. Inspect existing "
                "predictive_calibration, Predictive Cloud, Quant Brain, Digital Twin and "
                "verified-outcome contracts. Record a bounded architecture delta in "
                "docs/architecture/predictive_calibration_board_v1.md, then implement or "
                "extend the canonical calibration read model without duplicating existing "
                "calibration ownership. The board must preserve forecast vs actual, Brier/"
                "error/interval-coverage/drift fields only when supported by verified "
                "cohorts, preserve UNKNOWN otherwise, and expose evidence/freshness. It "
                "must not mutate model weights, capital, pricing, commercial state or "
                "revenue truth."
            ),
            authority="internal_write",
            risk_class="medium",
            source_ref="program:empire_os_full_completion:predictive_cloud_quant",
            base_branch=DEFAULT_BASE_BRANCH,
            allowed_paths=(
                "empire_os/predictive_calibration.py",
                "empire_os/predictive_calibration_board.py",
                "tests/test_predictive_calibration_board.py",
                "docs/architecture/predictive_calibration_board_v1.md",
            ),
            lease_resources=(
                "domain:predictive_calibration_board",
                "path:empire_os/predictive_calibration.py",
                "path:empire_os/predictive_calibration_board.py",
                "path:tests/test_predictive_calibration_board.py",
                "path:docs/architecture/predictive_calibration_board_v1.md",
            ),
            evidence_domains=("predictive_cloud", "quant_brain", "verified_outcomes", "digital_twin", "economic_memory"),
            success_condition=(
                "Calibration board reports only evidence-backed calibration metrics and "
                "UNKNOWN for unsupported metrics, with no execution authority."
            ),
            required_tests=(
                "tests/test_predictive_calibration_board.py",
                "tests/test_predictive_cloud_formula.py",
                "tests/test_quant_brain.py",
            ),
            priority=98,
        ),
        ExecutionRequest(
            request_id="completion-founder-master-execution-surface-v1",
            capability="backend_code",
            department="operations_fulfilment",
            objective=(
                "Follow the Architecture-First Engineering Doctrine. Reuse the Founder "
                "Execution Ledger API and current dashboard service. Record an architecture "
                "delta in docs/architecture/founder_master_completion_surface_v1.md, then "
                "add a read-only Founder surface that exposes the completion programme "
                "progress checkpoint and capability registry alongside the existing master "
                "execution ledger. Never infer completion from code. Missing artifacts fail "
                "closed/UNKNOWN. No mutation, deployment, outbound, payment or authority "
                "expansion."
            ),
            authority="internal_write",
            risk_class="low",
            source_ref="program:empire_os_full_completion:founder_console",
            base_branch=DEFAULT_BASE_BRANCH,
            allowed_paths=(
                "empire_os/founder_execution_ledger_api.py",
                "empire_os/founder_dashboard_service.py",
                "tests/test_founder_execution_ledger_api.py",
                "tests/test_founder_dashboard_service_routes.py",
                "docs/architecture/founder_master_completion_surface_v1.md",
            ),
            lease_resources=(
                "domain:founder_master_completion_surface",
                "path:empire_os/founder_execution_ledger_api.py",
                "path:empire_os/founder_dashboard_service.py",
                "path:tests/test_founder_execution_ledger_api.py",
                "path:tests/test_founder_dashboard_service_routes.py",
                "path:docs/architecture/founder_master_completion_surface_v1.md",
            ),
            evidence_domains=("master_execution_ledger", "completion_programme", "founder_operational_truth"),
            success_condition=(
                "Founder read API exposes persisted programme stage, 31 workstreams and "
                "591-item checklist state without creating mutation authority."
            ),
            required_tests=(
                "tests/test_founder_execution_ledger_api.py",
                "tests/test_founder_dashboard_service_routes.py",
                "tests/test_completion_capability_registry.py",
            ),
            priority=96,
        ),
        ExecutionRequest(
            request_id="completion-progress-persistence-v1",
            capability="parallel_backend_code",
            department="engineering",
            objective=(
                "Follow the Architecture-First Engineering Doctrine. Implement the durable "
                "completion-programme checkpoint writer as a production module, replacing "
                "manual ad-hoc JSON writes. Record an architecture delta in "
                "docs/architecture/completion_progress_persistence_v1.md. The helper must "
                "atomically update the current progress snapshot and append immutable stage "
                "checkpoint records containing stage/state/time/branch/commit/owner/evidence/"
                "tests/live verification/blockers/next action. Preserve prior checkpoint "
                "history, reject invalid stage regression unless explicitly marked recovery, "
                "and grant no external/commercial authority."
            ),
            authority="internal_write",
            risk_class="low",
            source_ref="program:empire_os_full_completion:progress_persistence",
            base_branch=DEFAULT_BASE_BRANCH,
            allowed_paths=(
                "empire_os/completion_progress.py",
                "tests/test_completion_progress.py",
                "docs/architecture/completion_progress_persistence_v1.md",
            ),
            lease_resources=(
                "domain:completion_progress_persistence",
                "path:empire_os/completion_progress.py",
                "path:tests/test_completion_progress.py",
                "path:docs/architecture/completion_progress_persistence_v1.md",
            ),
            evidence_domains=("master_execution_ledger", "engineering_checkpoints"),
            success_condition=(
                "Every engineering stage can be atomically checkpointed and append-only "
                "history survives chat/worker changes without authority expansion."
            ),
            required_tests=("tests/test_completion_progress.py",),
            priority=97,
        ),
        ExecutionRequest(
            request_id="completion-marketplace-current-research-v1",
            capability="public_research",
            department="market_intelligence",
            objective=(
                "Research current public architecture patterns relevant to B2B lead/data "
                "marketplaces, capacity-aware auctions, bid clearing, reserve/floor pricing, "
                "territory/exclusivity constraints and anti-gaming controls. Return source-"
                "backed observations and design risks for EmpireOS only. Do not recommend "
                "bypassing Empire truth/authority gates and do not mutate repository or "
                "commercial state."
            ),
            authority="observe",
            risk_class="low",
            source_ref="program:empire_os_full_completion:marketplace_research",
            base_branch=DEFAULT_BASE_BRANCH,
            evidence_domains=("marketplace", "auction", "bidding", "allocation"),
            success_condition="Current public research evidence is captured with provenance for later architecture review.",
            priority=85,
        ),
        ExecutionRequest(
            request_id="completion-control-plane-independent-qa-v1",
            capability="integration_qa",
            department="engineering",
            objective=(
                "Independently verify the full-completion programme foundation: architecture "
                "contract, 31-workstream capability registry, master ledger truth boundary, "
                "production-branch convergence and execution-plane authority invariants. "
                "Report blockers/evidence only. Do not modify production state or promote "
                "candidates."
            ),
            authority="observe",
            risk_class="high",
            source_ref="program:empire_os_full_completion:foundation_qa",
            base_branch=DEFAULT_BASE_BRANCH,
            evidence_domains=("completion_programme", "execution_plane", "control_fabric"),
            success_condition="Independent QA confirms no hidden authority expansion or false completion claims.",
            required_tests=(
                "tests/test_completion_capability_registry.py",
                "tests/test_master_execution_ledger.py",
                "tests/test_execution_plane_dispatcher.py",
                "tests/test_hermes_control.py",
            ),
            priority=90,
        ),
    )
