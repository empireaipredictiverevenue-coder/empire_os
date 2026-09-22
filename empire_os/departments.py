"""Canonical Empire AI department registry.

Departments are durable operating units. Agents/models are replaceable workers
inside them. Astra Executive delegates goals to departments; Control Fabric
governs the components/tools used by those departments.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class DepartmentSpec:
    key: str
    name: str
    mission: str
    components: tuple[str, ...]
    agent_roles: tuple[str, ...]
    kpis: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    authority: str
    blueprint_refs: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_departments() -> tuple[DepartmentSpec, ...]:
    return (
        DepartmentSpec(
            key="strategy",
            name="Strategy & Executive",
            mission=(
                "Set priorities, allocate attention/capital, coordinate "
                "departments and evaluate company-wide outcomes."
            ),
            components=("astra_executive", "astra", "control_fabric"),
            agent_roles=("supervisor", "executive_operations"),
            kpis=(
                "realized_gross_profit",
                "goal_completion_rate",
                "decision_latency",
                "forecast_vs_actual",
            ),
            inputs=(
                "predictive_cloud_state",
                "revenue_pulse",
                "department_status",
                "economic_memory",
            ),
            outputs=(
                "company_goals",
                "department_objectives",
                "resource_priorities",
                "founder_gates",
            ),
            authority="internal_write",
            blueprint_refs=("docs/STRATEGY_DEPARTMENT_BLUEPRINT.md",),
        ),
        DepartmentSpec(
            key="marketing_growth",
            name="Marketing & Growth",
            mission=(
                "Create, capture, convert and expand profitable demand using "
                "evidence-backed positioning, campaigns, search and lifecycle."
            ),
            components=(
                "marketing",
                "search_intelligence",
                "demand_genesis",
                "conversion_intelligence",
            ),
            agent_roles=("marketing", "growth"),
            kpis=(
                "marketing_sourced_recognized_revenue",
                "realized_gross_profit",
                "cac",
                "qualified_intent",
                "pipeline_created",
                "search_to_revenue",
            ),
            inputs=(
                "market_intelligence",
                "buyer_questions",
                "search_gaps",
                "product_evidence",
                "rd_findings",
            ),
            outputs=(
                "positioning",
                "campaigns",
                "content",
                "qualified_demand",
                "growth_experiments",
            ),
            authority="internal_write",
            blueprint_refs=("docs/MARKETING_DEPARTMENT_BLUEPRINT.md",),
        ),
        DepartmentSpec(
            key="sales_revenue",
            name="Sales & Revenue",
            mission=(
                "Convert genuine buyer evidence into conversations, terms, "
                "payment and expansion without fabricating commercial state."
            ),
            components=(
                "identity_enrichment",
                "conversation_os",
                "buyer_review",
                "commercial_terms",
                "revenue_pulse",
            ),
            agent_roles=("sales", "closer"),
            kpis=(
                "qualified_conversations",
                "commercial_terms",
                "verified_payments",
                "recognized_revenue",
                "realized_gross_profit",
                "sales_cycle_time",
            ),
            inputs=(
                "qualified_demand",
                "buyer_state",
                "offers",
                "pricing",
                "proof",
            ),
            outputs=(
                "buyer_conversations",
                "commercial_terms",
                "payment_requests",
                "commercial_outcomes",
            ),
            authority="governed_external",
            blueprint_refs=(),
        ),
        DepartmentSpec(
            key="rd_innovation",
            name="Research & Development",
            mission=(
                "Convert scientific, technical and commercial uncertainty into "
                "validated capabilities, IP and product advantages."
            ),
            components=(
                "predictive_cloud_opportunity_loop",
                "empire_coder",
                "quant_brain",
                "experiment_intelligence",
            ),
            agent_roles=(
                "research",
                "deep_research",
                "product_research",
                "engineering",
            ),
            kpis=(
                "validated_research",
                "benchmark_improvement",
                "uncertainty_reduction",
                "time_to_transfer",
                "commercial_impact",
                "value_of_information",
            ),
            inputs=(
                "customer_pain",
                "market_gaps",
                "production_bottlenecks",
                "model_calibration",
                "frontier_research",
            ),
            outputs=(
                "research_findings",
                "prototypes",
                "benchmarks",
                "transfer_packages",
                "new_capabilities",
            ),
            authority="internal_write",
            blueprint_refs=("docs/RD_DEPARTMENT_BLUEPRINT.md",),
        ),
        DepartmentSpec(
            key="product",
            name="Product",
            mission=(
                "Turn validated customer problems and R&D capability into "
                "coherent products, offers, packaging and roadmaps."
            ),
            components=(
                "commercial_product_catalog",
                "opportunity_factory",
                "digital_twin",
            ),
            agent_roles=("product_research", "product_manager"),
            kpis=(
                "activation",
                "retention",
                "time_to_value",
                "product_gross_profit",
                "validated_feature_adoption",
            ),
            inputs=(
                "rd_transfer",
                "customer_evidence",
                "market_opportunities",
                "usage_outcomes",
            ),
            outputs=(
                "product_requirements",
                "product_catalog",
                "offers",
                "roadmap",
                "release_candidates",
            ),
            authority="internal_write",
            blueprint_refs=(),
        ),
        DepartmentSpec(
            key="engineering",
            name="Engineering & Platform",
            mission=(
                "Build, test, operate and improve secure reliable EmpireOS "
                "capabilities from approved product and architecture plans."
            ),
            components=("empire_coder", "ops_sentinel", "control_fabric"),
            agent_roles=("engineering", "coder"),
            kpis=(
                "deployment_quality",
                "test_pass_rate",
                "latency",
                "reliability",
                "cost_efficiency",
                "incident_rate",
            ),
            inputs=(
                "product_requirements",
                "rd_transfer",
                "architecture",
                "incidents",
            ),
            outputs=(
                "code",
                "tests",
                "services",
                "runtime_health",
                "technical_evidence",
            ),
            authority="internal_write",
            blueprint_refs=(),
        ),
        DepartmentSpec(
            key="data_quant",
            name="Data, Quant & Predictive Intelligence",
            mission=(
                "Measure reality, quantify uncertainty, forecast outcomes, "
                "evaluate economics and verify model/decision performance."
            ),
            components=(
                "quant_brain",
                "predictive_intelligence",
                "predictive_cloud_status",
                "intelligence_fabric",
            ),
            agent_roles=("data_analysis", "quantitative_research"),
            kpis=(
                "calibration_error",
                "forecast_accuracy",
                "data_freshness",
                "uncertainty_coverage",
                "decision_value",
            ),
            inputs=(
                "canonical_observations",
                "forecasts",
                "verified_outcomes",
                "economic_data",
            ),
            outputs=(
                "decision_packets",
                "forecasts",
                "risk_analysis",
                "calibration",
                "value_of_information",
            ),
            authority="observe",
            blueprint_refs=("docs/QUANTITATIVE_INTELLIGENCE_ARCHITECTURE.md",),
        ),
        DepartmentSpec(
            key="market_intelligence",
            name="Market & Opportunity Intelligence",
            mission=(
                "Continuously discover and validate markets, triggers, gaps, "
                "buyers, territories and emerging commercial opportunities."
            ),
            components=(
                "predictive_cloud_opportunity_loop",
                "market_opportunity_agent",
                "intelligence_fabric",
                "search_fabric",
            ),
            agent_roles=("research", "deep_research"),
            kpis=(
                "qualified_opportunities",
                "evidence_quality",
                "opportunity_stage_velocity",
                "research_cost",
                "commercial_validation_rate",
            ),
            inputs=(
                "sensor_mesh",
                "search",
                "community_intent",
                "competitors",
                "physical_signals",
            ),
            outputs=(
                "opportunity_radar",
                "market_maps",
                "evidence_routes",
                "tam_icp",
                "research_briefs",
            ),
            authority="internal_write",
            blueprint_refs=("docs/GLOBAL_OPPORTUNITY_GROWTH_DOCTRINE.md",),
        ),
        DepartmentSpec(
            key="customer_success",
            name="Customer & Revenue Operations",
            mission=(
                "Drive onboarding, adoption, retention, expansion and accurate "
                "customer/commercial state through the canonical CRM."
            ),
            components=("revenue_crm", "conversation_os"),
            agent_roles=("customer_success",),
            kpis=(
                "activation",
                "retention",
                "expansion_revenue",
                "time_to_value",
                "customer_outcomes",
            ),
            inputs=(
                "customer_state",
                "usage",
                "conversations",
                "fulfilment_outcomes",
            ),
            outputs=(
                "lifecycle_actions",
                "retention_signals",
                "expansion_opportunities",
                "customer_evidence",
            ),
            authority="governed_external",
            blueprint_refs=(),
        ),
        DepartmentSpec(
            key="operations_fulfilment",
            name="Operations & Fulfilment",
            mission=(
                "Deliver sold outcomes reliably, manage capacity and turn "
                "commercial promises into verified fulfilment evidence."
            ),
            components=("fulfilment_readiness", "ops_sentinel"),
            agent_roles=("operations",),
            kpis=(
                "fulfilment_cycle_time",
                "delivery_quality",
                "capacity_utilization",
                "service_level",
                "fulfilment_cost",
            ),
            inputs=(
                "commercial_terms",
                "product_runbooks",
                "capacity",
                "customer_requirements",
            ),
            outputs=(
                "fulfilment",
                "delivery_evidence",
                "capacity_state",
                "operational_outcomes",
            ),
            authority="governed_external",
            blueprint_refs=(),
        ),
        DepartmentSpec(
            key="finance_capital",
            name="Finance & Capital",
            mission=(
                "Protect cash, measure unit economics and allocate capital "
                "toward evidence-backed risk-adjusted returns."
            ),
            components=("capital_allocator", "quant_brain", "revenue_pulse"),
            agent_roles=("finance",),
            kpis=(
                "realized_gross_profit",
                "cash_exposure",
                "capital_efficiency",
                "payback",
                "portfolio_concentration",
            ),
            inputs=(
                "recognized_revenue",
                "verified_costs",
                "forecasts",
                "risk",
                "capital_requests",
            ),
            outputs=(
                "capital_reviews",
                "budget_recommendations",
                "unit_economics",
                "portfolio_analysis",
            ),
            authority="founder_gate",
            blueprint_refs=(),
        ),
        DepartmentSpec(
            key="risk_compliance",
            name="Risk, Legal & Compliance",
            mission=(
                "Constrain company action to approved legal, policy, privacy, "
                "security and authority boundaries."
            ),
            components=("control_fabric", "outbound_governor"),
            agent_roles=("legal_compliance", "security"),
            kpis=(
                "policy_violations",
                "suppression_integrity",
                "security_findings",
                "authority_breaches",
                "audit_completeness",
            ),
            inputs=(
                "planned_actions",
                "jurisdiction",
                "consent",
                "security_state",
            ),
            outputs=(
                "allow_deny_decisions",
                "risk_findings",
                "compliance_evidence",
                "required_gates",
            ),
            authority="founder_gate",
            blueprint_refs=(),
        ),
        DepartmentSpec(
            key="partnerships_distribution",
            name="Partnerships & Distribution",
            mission=(
                "Build scalable buyer, partner, affiliate, agency, reseller and "
                "distribution channels with verified capacity and economics."
            ),
            components=("buyer_capacity_readiness", "strategic_partnerships"),
            agent_roles=("partnerships", "business_development"),
            kpis=(
                "active_partners",
                "verified_capacity",
                "partner_pipeline",
                "partner_revenue",
                "distribution_coverage",
            ),
            inputs=(
                "market_opportunities",
                "buyer_capacity",
                "partner_candidates",
                "product_catalog",
            ),
            outputs=(
                "distribution_paths",
                "partner_capacity",
                "co_marketing",
                "channel_opportunities",
            ),
            authority="governed_external",
            blueprint_refs=(),
        ),
    )


def department_map() -> dict[str, DepartmentSpec]:
    return {row.key: row for row in default_departments()}


def component_department_map() -> dict[str, tuple[str, ...]]:
    result: dict[str, list[str]] = {}
    for department in default_departments():
        for component in department.components:
            result.setdefault(component, []).append(department.key)
    return {
        component: tuple(sorted(keys))
        for component, keys in result.items()
    }


def departments_for_component(component: str) -> tuple[str, ...]:
    return component_department_map().get(str(component).strip(), ())


def validate_departments(
    *,
    registered_components: Iterable[str],
) -> dict[str, Any]:
    available = {str(value).strip() for value in registered_components}
    missing: dict[str, list[str]] = {}
    for department in default_departments():
        unresolved = [
            component
            for component in department.components
            if component not in available
        ]
        if unresolved:
            missing[department.key] = unresolved
    return {
        "schema_version": "empire.department_registry_validation.v1",
        "department_count": len(default_departments()),
        "fully_wired_department_count": (
            len(default_departments()) - len(missing)
        ),
        "departments_with_missing_components": missing,
        "all_components_registered": not missing,
    }
