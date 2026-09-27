"""Scope and modeled delivery economics for the $250k+ private deployment.

These are internal commercial guardrails, not observed historical costs.
They protect delivery scope and margin before binding enterprise terms.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


PRIVATE_DEPLOYMENT_PRICE_CENTS = 25_000_000
DIRECT_FULFILMENT_COST_CEILING_CENTS = 7_500_000
ACQUISITION_COST_CEILING_CENTS = 2_500_000
MIN_CONTRIBUTION_MARGIN_BPS = 6000
TARGET_GROSS_MARGIN_BPS = 7000


@dataclass(frozen=True)
class ScopeWorkstream:
    key: str
    outcome: str
    delivery_budget_cents: int
    acceptance_evidence: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


PRIVATE_DEPLOYMENT_SCOPE: tuple[ScopeWorkstream, ...] = (
    ScopeWorkstream(
        key="commercial_discovery_and_revenue_truth",
        outcome="Canonical revenue truth, funnel boundaries and verified KPI contract.",
        delivery_budget_cents=750_000,
        acceptance_evidence=(
            "revenue_truth_contract",
            "source_inventory",
            "metric_definitions",
        ),
    ),
    ScopeWorkstream(
        key="data_and_system_integration",
        outcome="Governed integration of agreed CRM, revenue, demand and customer systems.",
        delivery_budget_cents=1_750_000,
        acceptance_evidence=(
            "integration_inventory",
            "data_lineage",
            "freshness_checks",
        ),
    ),
    ScopeWorkstream(
        key="predictive_revenue_models",
        outcome="Revenue, conversion, timing, risk and opportunity forecasts with calibration.",
        delivery_budget_cents=1_250_000,
        acceptance_evidence=(
            "forecast_registry",
            "calibration_report",
            "prediction_vs_actual_contract",
        ),
    ),
    ScopeWorkstream(
        key="market_and_opportunity_intelligence",
        outcome="Market, demand, search, competitor and opportunity intelligence for agreed scope.",
        delivery_budget_cents=750_000,
        acceptance_evidence=(
            "opportunity_registry",
            "market_evidence",
            "priority_decision_queue",
        ),
    ),
    ScopeWorkstream(
        key="executive_command_center",
        outcome="Private executive Predictive Revenue command surface and operating views.",
        delivery_budget_cents=750_000,
        acceptance_evidence=(
            "executive_dashboard",
            "role_access_review",
            "decision_brief_contract",
        ),
    ),
    ScopeWorkstream(
        key="governed_agents_and_workflows",
        outcome="Approved agent workflows for research, qualification, sales support and optimization.",
        delivery_budget_cents=1_000_000,
        acceptance_evidence=(
            "authority_matrix",
            "workflow_registry",
            "execution_guard_tests",
        ),
    ),
    ScopeWorkstream(
        key="enterprise_controls_security_and_handover",
        outcome="Enterprise controls, SLO evidence, training, runbooks and production handover.",
        delivery_budget_cents=750_000,
        acceptance_evidence=(
            "enterprise_readiness",
            "runbooks",
            "handover_acceptance",
        ),
    ),
    ScopeWorkstream(
        key="delivery_contingency",
        outcome="Bounded contingency for approved integration and deployment variance.",
        delivery_budget_cents=500_000,
        acceptance_evidence=(
            "change_log",
            "approved_scope_variance",
        ),
    ),
)


def private_deployment_economics() -> dict[str, Any]:
    scope_cost = sum(row.delivery_budget_cents for row in PRIVATE_DEPLOYMENT_SCOPE)
    if scope_cost != DIRECT_FULFILMENT_COST_CEILING_CENTS:
        raise ValueError("private deployment workstream budgets exceed cost ceiling")

    gross_contribution = PRIVATE_DEPLOYMENT_PRICE_CENTS - scope_cost
    contribution_after_acquisition = gross_contribution - ACQUISITION_COST_CEILING_CENTS
    gross_margin_bps = (
        gross_contribution * 10_000 // PRIVATE_DEPLOYMENT_PRICE_CENTS
    )
    contribution_margin_bps = (
        contribution_after_acquisition * 10_000 // PRIVATE_DEPLOYMENT_PRICE_CENTS
    )

    return {
        "schema_version": "empire.predictive-revenue.private-economics.v1",
        "pricing_state": "FOUNDER_APPROVED",
        "price_cents": PRIVATE_DEPLOYMENT_PRICE_CENTS,
        "price_type": "starting_floor",
        "direct_fulfilment_cost_ceiling_cents": DIRECT_FULFILMENT_COST_CEILING_CENTS,
        "acquisition_cost_ceiling_cents": ACQUISITION_COST_CEILING_CENTS,
        "gross_contribution_cents": gross_contribution,
        "contribution_after_acquisition_cents": contribution_after_acquisition,
        "gross_margin_bps_at_ceiling": gross_margin_bps,
        "contribution_margin_bps_at_ceiling": contribution_margin_bps,
        "target_gross_margin_bps": TARGET_GROSS_MARGIN_BPS,
        "minimum_contribution_margin_bps": MIN_CONTRIBUTION_MARGIN_BPS,
        "workstreams": [row.as_dict() for row in PRIVATE_DEPLOYMENT_SCOPE],
        "observed_cost_claim": False,
        "economics_basis": "internal_delivery_budget_ceiling_not_observed_history",
        "recurring_managed_service_price": None,
        "recurring_price_state": "CUSTOM_SCOPE",
        "payment_action": False,
        "actual_revenue": False,
    }
