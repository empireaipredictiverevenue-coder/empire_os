"""Conservative machine-readable capability registry for EmpireOS completion.

This registry reconciles the canonical Master Remaining Checklist with repository
implementation evidence.  It never treats code presence as production completion;
all workstreams require separate live/runtime reconciliation before CHECKLIST DONE.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from empire_os.master_execution_ledger import LedgerItem, parse_checklist


@dataclass(frozen=True)
class WorkstreamSpec:
    key: str
    name: str
    owner: str
    checklist_terms: tuple[str, ...]
    module_patterns: tuple[str, ...]
    authority: str = "internal_write"


WORKSTREAMS: tuple[WorkstreamSpec, ...] = (
    WorkstreamSpec("control_plane", "Control Plane / Astra / Execution Plane", "engineering", ("Astra Executive", "Agent & Tool Execution Plane", "Architecture-first engineering doctrine", "Reconciliation / anti-loss controls"), ("astra*.py", "*execution_plane*.py", "control_fabric*.py", "department_*.py")),
    WorkstreamSpec("data_cloud", "Data Cloud / EmpireDB / Data Fabric", "data_quant", ("Production cleanup / infrastructure", "Reconciliation / anti-loss controls"), ("data_cloud*.py", "data_fabric*.py", "*_repository.py")),
    WorkstreamSpec("signal_sensor_mesh", "Signal & Sensor Mesh", "market_intelligence", ("Automate recurring intelligence", "Market Sweeps / Revenue GPS"), ("signal_*.py", "source_*.py", "crawler_*.py", "site_crawler.py"), "observe"),
    WorkstreamSpec("identity_graph", "Identity / Entity / Contact Graph", "sales_revenue", ("Buyer acquisition / commercial loop", "TAM / Market Intelligence"), ("identity_*.py", "enterprise_contact*.py", "companies_house_identity.py", "official_license_identity.py", "prospect_enrichment.py")),
    WorkstreamSpec("intelligence_fabric", "Intelligence Fabric", "data_quant", ("Predictive Cloud convergence", "Autonomous Business Loop"), ("intelligence_*.py", "agent_intelligence.py", "vertical_intelligence_runtime.py")),
    WorkstreamSpec("predictive_cloud_quant", "Predictive Cloud / Quant / Decision Intelligence", "data_quant", ("Predictive Cloud convergence", "Quant Brain / Decision Verification"), ("predictive*.py", "future_trend_intelligence.py", "opportunity_quant_review.py")),
    WorkstreamSpec("opportunity_factory", "Opportunity Radar / Foundry / Factory", "market_intelligence", ("Autonomous Predictive Cloud / Opportunity Loop", "Market Sweeps / Revenue GPS"), ("opportunity_*.py", "market_sweep_revenue_gps.py")),
    WorkstreamSpec("marketplace_auction", "Marketplace / Opportunity Auction / Bidding", "sales_revenue", ("Blueprint phases 6–18 preservation", "Salvage / half-built / gated completion lane"), ("marketplace*.py", "opportunity_auction.py", "buyer_marketplace_webhooks.py")),
    WorkstreamSpec("revenue_exchange", "Revenue Exchange / Allocation / Capacity", "sales_revenue", ("Blueprint phases 6–18 preservation", "Buyer acquisition / commercial loop"), ("revenue_exchange*.py", "buyer_allocation*.py", "buyer_capacity*.py")),
    WorkstreamSpec("commercial_exchange", "Commercial Exchange / Inventory / Pricing", "product", ("Commercial/product economics across Empire", "Buyer acquisition / commercial loop"), ("commercial_exchange*.py", "commercial_pricing*.py", "commercial_offer_book.py", "commercial_product*.py")),
    WorkstreamSpec("product_factory", "Product Factory / Revenue Compiler", "product", ("Commercial/product economics across Empire", "Managed Service first-cash offer"), ("revenue_compiler.py", "predictive_revenue_products.py", "phase4_exchange_mrr_products.py", "seed_sku_products.py", "mrr_product_recovery.py")),
    WorkstreamSpec("buyer_acquisition", "Buyer Acquisition / Buyer Intelligence", "sales_revenue", ("Buyer acquisition / commercial loop", "TAM / Market Intelligence"), ("buyer_*.py", "omega_buyer_readiness.py", "lead_intelligence*.py")),
    WorkstreamSpec("outreach_deliverability", "Outreach / Deliverability", "sales_revenue", ("Buyer acquisition / commercial loop", "Business agents to build"), ("outbound_*.py", "outreach_*.py")),
    WorkstreamSpec("conversation_closer", "Conversation OS / AI Closer", "sales_revenue", ("Buyer acquisition / commercial loop", "Business agents to build", "Blueprint phases 6–18 preservation"), ("conversation_*.py", "closer_*.py", "agi_closer.py", "buyer_reply_operations_agent.py")),
    WorkstreamSpec("voice_calls", "Voice / Calls", "sales_revenue", ("Buyer acquisition / commercial loop",), ("voice_*.py", "vonage_call_transport.py", "call_manager.py", "buyer_call_*.py")),
    WorkstreamSpec("search_intelligence", "Search / SEO / AEO / GEO", "marketing_growth", ("Search / SEO / AEO / GEO product family", "Organic + AI Recommendation Intelligence"), ("search_*.py", "organic_search_*.py", "competitor_search_presence.py")),
    WorkstreamSpec("marketing_media", "Marketing / Campaigns / Media Intelligence", "marketing_growth", ("Autonomous Business Loop", "Founder Console"), ("marketing*.py", "campaigns.py", "owned_campaign_*.py", "media_*.py", "traffic_specialist.py")),
    WorkstreamSpec("vertical_intelligence", "Vertical Intelligence Nodes", "market_intelligence", ("Permit Intelligence", "Property Intelligence", "Private Capital / Roll-Up Intelligence", "Storm Leads Multiplier"), ("permit_*.py", "private_capital*.py", "storm_*.py", "solar_*.py", "legal_mass_tort_intelligence.py", "spatial_physical_intelligence.py")),
    WorkstreamSpec("digital_twin", "Digital Twin / Scenario", "data_quant", ("Account / Buyer Digital Twin", "Blueprint phases 6–18 preservation"), ("digital_twin*.py", "account_digital_twin.py", "supply_quality_twin.py"), "observe"),
    WorkstreamSpec("capital_allocator", "Capital Allocator / Portfolio", "strategy", ("Blueprint phases 6–18 preservation", "Quant Brain / Decision Verification"), ("capital_*.py",), "observe"),
    WorkstreamSpec("payments_settlement", "Payments / USDT-BSC / Settlement", "finance", ("Buyer acquisition / commercial loop", "Phase exit / real-money proof"), ("bsc_*.py", "payment_*.py", "a2a_settle_bridge.py")),
    WorkstreamSpec("fulfilment_outcomes", "Fulfilment / Outcomes", "operations_fulfilment", ("Buyer acquisition / commercial loop", "Phase exit / real-money proof"), ("*fulfilment*.py", "commercial_event_repository.py")),
    WorkstreamSpec("economic_memory", "Economic Memory / Revenue OS Learning", "data_quant", ("Cortex learning loop", "Quant Brain / Decision Verification", "Phase exit / real-money proof"), ("economic_memory.py", "revenue_os_*.py"), "observe"),
    WorkstreamSpec("experiment_causal", "Experiment / Causal Engine", "rd_innovation", ("Blueprint phases 6–18 preservation", "Quant Brain / Decision Verification"), ("experiment_*.py",), "observe"),
    WorkstreamSpec("revenue_crm", "Revenue CRM / Retention / Customer Success", "sales_revenue", ("Blueprint phases 6–18 preservation", "Business agents to build"), ("revenue_crm*.py",)),
    WorkstreamSpec("saas_network", "SaaS / Multi-tenant / White Label / Affiliate", "product", ("Blueprint phases 6–18 preservation", "Salvage / half-built / gated completion lane"), ("whitelabel.py", "affiliate.py", "commercial_usage_metering.py", "self_serve_checkout*.py", "predictive_revenue_self_serve.py")),
    WorkstreamSpec("a2a_commerce", "A2A Commerce Network", "product", ("Blueprint phases 6–18 preservation",), ("a2a_*.py",)),
    WorkstreamSpec("founder_console", "Founder Console / Operational Truth", "operations_fulfilment", ("Founder Console", "Reconciliation / anti-loss controls"), ("founder_*.py", "dashboard.py", "revenue_dashboard.py"), "observe"),
    WorkstreamSpec("observability_reliability", "Observability / Self-Heal / Reliability", "engineering", ("Observability / control foundation", "Production cleanup / infrastructure", "Automate recurring intelligence"), ("*self_heal*.py", "ops_healer.py", "model_health.py", "control_fabric_snapshot.py")),
    WorkstreamSpec("model_agent_intelligence", "Model / Agent Intelligence Fabric", "engineering", ("Intelligence Router / Model Upgrade Layer", "AI decision / safety foundation", "Cross-system integrations"), ("model_*.py", "intelligence_router.py", "needle_shadow_router.py", "astra_intelligence_routing.py", "agent_intelligence.py")),
    WorkstreamSpec("revenue_truth", "Revenue Truth / First Revenue / Realized GP", "finance", ("Revenue Pulse", "Phase exit / real-money proof", "Managed Service first-cash offer"), ("first_revenue*.py", "revenue_pulse*.py", "daily_revenue.py", "revenue_invariant_check.py"), "observe"),
)


def _matches_section(item: LedgerItem, terms: Iterable[str]) -> bool:
    section = item.section.lower()
    return any(term.lower() in section for term in terms)


def _modules(root: Path, patterns: Iterable[str]) -> list[str]:
    base = root / "empire_os"
    found: set[str] = set()
    for pattern in patterns:
        for path in base.glob(pattern):
            if path.is_file() and path.suffix == ".py":
                found.add(str(path.relative_to(root)))
    return sorted(found)


def build_completion_capability_registry(
    repo_root: str | Path,
    checklist_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    checklist = Path(checklist_path or root / "docs/MASTER_REMAINING_CHECKLIST.md")
    items = parse_checklist(checklist)
    rows: list[dict[str, Any]] = []

    for spec in WORKSTREAMS:
        scoped = [item for item in items if _matches_section(item, spec.checklist_terms)]
        pending = [item for item in scoped if item.status == "PENDING"]
        done = [item for item in scoped if item.status == "DONE"]
        modules = _modules(root, spec.module_patterns)

        if pending and modules:
            state = "PARTIAL"
        elif pending and not modules:
            state = "NEEDS_WIRING"
        elif not pending and modules:
            state = "CONNECTED"
        else:
            state = "INCUBATE"

        rows.append({
            **asdict(spec),
            "state": state,
            "checklist_total": len(scoped),
            "checklist_done": len(done),
            "checklist_pending": len(pending),
            "pending_items": [item.item for item in pending],
            "module_count": len(modules),
            "module_evidence": modules,
            "runtime_reconciliation_required": True,
            "code_presence_is_not_completion": True,
        })

    return {
        "schema_version": "empire.completion-capability-registry.v1",
        "workstream_count": len(rows),
        "checklist": {
            "source": str(checklist),
            "total": len(items),
            "done": sum(item.status == "DONE" for item in items),
            "pending": sum(item.status == "PENDING" for item in items),
        },
        "workstreams": rows,
        "authority": {
            "live_outbound": "founder_gate",
            "binding_terms": "founder_gate",
            "funds_mainnet": "founder_gate",
            "destructive_infra": "founder_gate",
            "authority_expansion": "founder_gate",
            "registry_execution_authority": "none",
        },
    }
