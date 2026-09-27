"""Canonical execution phase plan for EmpireOS.

Blueprint v6 remains the architecture reference. This module is the bounded
execution-order contract agreed after the architecture had accumulated parallel
work across many historical phases.

It is read-only planning metadata: it grants no production, commercial,
payment, accounting or execution authority.
"""
from __future__ import annotations

from typing import Any


CLOSEOUT_SEQUENCE = (
    "build",
    "integrate",
    "test",
    "verify",
    "surface_in_founder_console",
    "upgrade_and_enhance",
    "revenue_expansion",
    "retest",
    "close_phase",
)


PHASES: tuple[dict[str, Any], ...] = (
    {
        "phase": "3F",
        "title": "Intelligence & Learning Closeout",
        "status": "CLOSED_EVIDENCE_GATED",
        "objective": (
            "Close the verified intelligence, Economic Memory, predictive "
            "provenance, recovery-audit and Founder Console feedback loop."
        ),
        "completion": (
            "Economic Memory is evidence-gated; Predictive Intelligence uses "
            "verified provenance; recovered assets have implementation "
            "evidence; Founder Console exposes status; relevant tests and "
            "runtime verification are complete."
        ),
        "revenue_features": (
            "opportunity_value_scoring",
            "outcome_based_product_development",
            "commercial_diagnostics_foundation",
        ),
    },
    {
        "phase": "4",
        "title": "Commercial Exchange",
        "status": "CURRENT",
        "objective": (
            "Turn qualified opportunities into governed inventory with "
            "Supabase-native lanes, corridors, buyer seats and capacity."
        ),
        "completion": (
            "A real qualified opportunity can enter inventory and receive a "
            "deterministic auditable buyer-allocation proposal without "
            "inventing identity, price, terms or capacity."
        ),
        "revenue_features": (
            "buyer_seat_subscriptions",
            "corridor_subscriptions",
            "dynamic_buyer_pricing",
            "overflow_monetisation",
            "margin_aware_routing",
            "demand_pre_selling",
            "reserved_future_capacity",
            "territory_and_exclusivity_premiums",
        ),
    },
    {
        "phase": "5",
        "title": "Revenue Engine",
        "status": "QUEUED",
        "objective": (
            "Close the genuine commercial loop from real acquisition through "
            "verified BSC/USDT settlement, fulfilment and Revenue Truth."
        ),
        "completion": (
            "At least one genuine transaction can traverse the governed "
            "architecture without synthetic evidence or invented intermediate "
            "commercial state."
        ),
        "revenue_features": (
            "transaction_fees",
            "managed_closing",
            "fulfilment_fees",
            "sales_assist_subscription",
            "ai_closer_product",
            "revenue_leak_detection",
            "next_best_product",
            "margin_optimisation",
        ),
    },
    {
        "phase": "6",
        "title": "Growth & Market Intelligence",
        "status": "QUEUED",
        "objective": (
            "Scale evidence-backed opportunity creation across market, storm, "
            "property, capital, permit, search and competitor intelligence."
        ),
        "completion": (
            "Intelligence domains feed a common evidence-to-opportunity "
            "pipeline instead of disconnected mini-systems."
        ),
        "revenue_features": (
            "revenue_pulse_subscription",
            "storm_intelligence",
            "permit_intelligence",
            "private_capital_intelligence",
            "property_intelligence",
            "competitor_audience_intelligence",
            "tam_and_market_entry_reports",
            "private_intelligence_feeds",
            "benchmark_products",
        ),
    },
    {
        "phase": "7",
        "title": "Autonomous GTM",
        "status": "QUEUED",
        "objective": (
            "Automate repeatable research, prospecting, enrichment, follow-up, "
            "conversation support, nurture and account growth under governance."
        ),
        "completion": (
            "Internal GTM work runs continuously within standing authority; "
            "real-world founder gates remain enforced."
        ),
        "revenue_features": (
            "outbound_as_a_service",
            "managed_prospecting",
            "ai_sdr",
            "ai_follow_up",
            "campaign_management",
            "appointment_generation",
            "content_automation",
            "conversion_optimisation_retainer",
            "expansion_and_upsell_engine",
            "automated_cross_sell",
        ),
    },
    {
        "phase": "8",
        "title": "Productisation & Monetisation",
        "status": "QUEUED",
        "objective": (
            "Package proven Empire capabilities into repeatable SaaS, managed, "
            "enterprise, white-label, partner and data products."
        ),
        "completion": (
            "Products have governed identity, fulfilment, economics, pricing "
            "evidence, buyer surfaces and measurable delivery."
        ),
        "revenue_features": (
            "saas_tiers",
            "enterprise_data_api",
            "white_label",
            "enterprise_licensing",
            "reseller_plans",
            "affiliate_partner_revenue",
            "commercial_diagnostics_product",
            "marketplace_and_data_feeds",
            "managed_growth",
        ),
    },
    {
        "phase": "9",
        "title": "Scale & Reliability",
        "status": "QUEUED",
        "objective": (
            "Harden EmpireOS for production scale, resilience, security, "
            "multi-tenancy, reconciliation and operational visibility."
        ),
        "completion": (
            "The platform meets defined reliability, isolation, monitoring, "
            "performance and recovery requirements at target load."
        ),
        "revenue_features": (
            "enterprise_sla_tiers",
            "dedicated_infrastructure",
            "premium_data_retention",
            "advanced_governance",
            "priority_support",
            "usage_based_compute_and_data",
            "churn_and_renewal_intelligence",
            "retention_optimisation",
        ),
    },
    {
        "phase": "10",
        "title": "Advanced Autonomy",
        "status": "QUEUED",
        "objective": (
            "Add controlled self-improving planning, specialist agents, "
            "economic optimisation and Empire Coder capabilities."
        ),
        "completion": (
            "Autonomous optimisation remains evidence-bounded, reviewable and "
            "unable to silently expand production or financial authority."
        ),
        "revenue_features": (
            "autonomous_revenue_operator",
            "autonomous_research_teams",
            "agent_subscriptions",
            "specialist_agent_marketplace",
            "enterprise_private_agents",
            "outcome_driven_product_selection",
            "economic_optimisation",
        ),
    },
)


def build_canonical_phase_plan() -> dict[str, Any]:
    current = next(
        (row for row in PHASES if row["status"] == "CURRENT"),
        None,
    )
    return {
        "schema_version": "empire.canonical-phase-plan.v1",
        "current_phase": current["phase"] if current else None,
        "current_phase_title": current["title"] if current else None,
        "closeout_sequence": list(CLOSEOUT_SEQUENCE),
        "phases": [
            {
                **row,
                "revenue_features": list(row["revenue_features"]),
            }
            for row in PHASES
        ],
        "phase_skipping_allowed": False,
        "new_ideas_interrupt_current_phase": False,
        "allowed_interrupt_reasons": [
            "genuine_blocker",
            "security_issue",
            "revenue_critical_dependency",
            "fundamental_correctness_issue",
        ],
        "upgrade_and_enhance_required": True,
        "revenue_expansion_required": True,
        "execution_authority": "none",
    }
