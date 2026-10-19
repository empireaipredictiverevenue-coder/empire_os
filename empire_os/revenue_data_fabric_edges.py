"""Read-only code-edge manifest for the existing Empire revenue data fabric.

Source code existence is *not* evidence that an edge is connected at runtime.
No imports of agent modules, no network, no database, no environment secrets.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class IntelligenceEdge:
    layer: str
    source_file: str
    sink_file: str
    evidence_required: str
    commercial_value: str


EDGES: tuple[IntelligenceEdge, ...] = (
    IntelligenceEdge(
        "treg_optional_provider_to_own_source_intelligence_policy",
        "empire_os/treg_source_policy.py",
        "empire_os/source_intelligence.py",
        "zero-spend cap, read-only business-only purpose, third-party processor "
        "and individual source-use rights, no secret upload or paid tool calls",
        "compare vendor discovery/enrichment capabilities without replacing "
        "EmpireDB, Scrapling or our existing Waterfall",
    ),
    IntelligenceEdge(
        "listmonk_historic_audience_to_consent_suppression_recovery_gate",
        "empire_os/listmonk_recovery_boundary.py",
        "empire_os/founder_lead_supply_api.py",
        "original PostgreSQL volume verification, password rotation, active "
        "double opt-in and canonical suppression/opt-out reconciliation; no send",
        "recover newsletter system only after verifying historical data and "
        "separately approved private restoration, without mass-mailing cold leads",
    ),
    IntelligenceEdge(
        "buyer_qualification_and_canonical_exchange_to_leadgen_revenue_queue",
        "empire_os/leadgen_revenue_activation_queue.py",
        "empire_os/founder_lead_supply_api.py",
        "six-hour current founder buyer evidence, verified separate canonical "
        "Exchange inventory, first-party research references and no false "
        "buyer-territory match, capacity or send authority",
        "prioritise truthful B2B buyer verification gaps against existing "
        "niche supply before founder-approved commercial outreach",
    ),
    IntelligenceEdge(
        "official_research_ledgers_to_existing_canonical_prospect_preflight",
        "empire_os/official_source_canonical_preflight.py",
        "empire_os/crawler_data_repository.py",
        "three bounded provenance-verified private official-source ledgers, "
        "zero intent inflation, limited read-only canonical lookup, no ingest RPC",
        "make UK solar canonical preparation measurable and hold US sources "
        "until separate acquisition rights and verified company identities",
    ),
    IntelligenceEdge(
        "official_vertical_source_catalog_and_bounded_dental_pilot",
        "empire_os/official_vertical_source_packs.py",
        "empire_os/nppes_dental_source.py",
        "CMS NPI-2 organisation-only limited API, no patient/provider records, "
        "no automatic bulk download or canonical lead claims",
        "observed US dental business entity evidence for private source research",
    ),
    IntelligenceEdge(
        "official_cslb_contractor_csv_review",
        "empire_os/official_vertical_source_packs.py",
        "empire_os/cslb_contractor_csv_source.py",
        "licence and file-use review, local official CSV, roofing/HVAC/solar classifications",
        "add US licensed-contractor evidence without unverified state APIs",
    ),
    IntelligenceEdge(
        "scrapling_sniper_handoff_to_canonical_exchange_inventory_preview",
        "empire_os/scrapling_sniper_handoff.py",
        "empire_os/lead_exchange_live_inventory.py",
        "review packet separation, canonical EmpireDB Exchange bounded selection, "
        "fresh verified read-only snapshot, no inventory promotion or buyer allocation",
        "show honest observed inventory by niche and corridor in private founder console",
    ),
    IntelligenceEdge(
        "legacy_lead_sniper_to_canonical_empiredb_review_queue",
        "empire_os/agents/lead_sniper_agent.py",
        "empire_os/lead_sniper_repository.py",
        "registered firm-only source rights and corporate identity, existing "
        "EmpireDB review reader, independent queue write authority and dedup",
        "retire Supabase endpoint without creating another sniper platform",
    ),
    IntelligenceEdge(
        "scout_review_and_empiredb_exchange_readiness",
        "empire_os/revenue_sniper_scanner_review.py",
        "empire_os/revenue_sniper_dispatch_readiness.py",
        "fresh verified contract snapshots from existing buyer scout, review "
        "readiness, EmpireDB Exchange, with counters reconciled and scopes separate",
        "identify real source, first-party identity and buyer capacity blockers "
        "without extra scans, new leads or outbound action",
    ),
    IntelligenceEdge(
        "existing_buyer_scout_to_review_only_revenue_sniper",
        "empire_os/buyer_acquisition_scout.py",
        "empire_os/revenue_sniper_scanner_review.py",
        "fresh OBSERVE scout evidence, B2B company/lane validation and buyer "
        "verification holds; never auto-send or invent buyer capacity",
        "triage live scanner discoveries without activating legacy sniper",
    ),
    IntelligenceEdge(
        "legacy_neural_scanner_to_source_rights_gate",
        "empire_os/scanner.py",
        "empire_os/scanner_source_contract_bridge.py",
        "explicit registered source and country rights, provenance, firm-only "
        "review and sensitive data exclusion",
        "reuse existing US/UK scanner shapes without false canonical leads",
    ),
    IntelligenceEdge(
        "scrapling_observation_to_canonical_identity_review",
        "empire_os/scrapling_source_evidence.py",
        "empire_os/scrapling_identity_review.py",
        "complete stable read-only canonical identity snapshot and independent "
        "source rights, no phone-only/cross-market auto-merge or new lead claims",
        "protect canonical deduplication and lead-supply inventory truth",
    ),
    IntelligenceEdge(
        "scrapling_review_to_owned_waterfall",
        "empire_os/scrapling_source_evidence.py",
        "empire_os/waterfall_source_bridge.py",
        "independent company identity, source rights, niche/jurisdiction policy; "
        "no inferred first-party site, customer lead or outbound authority",
        "safely plan vertical-specific use of OUR existing Waterfall",
    ),
    IntelligenceEdge(
        "empire_owned_contact_waterfall",
        "empire_os/waterfall.py",
        "empire_os/prospect_enrichment.py",
        "same business ID, lawful source permission, validated bound contact, "
        "provenance and expiry; separate offline review of adapter integration",
        "improve our OWN waterfall, never clone a vendor waterfall",
    ),
    IntelligenceEdge(
        "legal_mass_tort_firm_intelligence",
        "empire_os/legal_mass_tort_intelligence.py",
        "empire_os/buyer_demand_graph.py",
        "firm-level public law and court market signals, jurisdiction and B2B "
        "buyer evidence; prohibit individual claimant targeting",
        "evidence-led legal analytics without sensitive consumer profiling",
    ),
    IntelligenceEdge(
        "claims_insurance_buyer_governance",
        "empire_os/claims_exchange/engine.py",
        "empire_os/buyer_claim_provenance.py",
        "carrier, TPA, contractor and licensed claims partner differentiated; "
        "verify jurisdiction, licences, authority and permitted commercial basis",
        "lawful fixed-scope analytics and buyer-network research",
    ),
    IntelligenceEdge(
        "insurance_distribution_b2b_demand",
        "empire_os/buyer_acquisition_scout.py",
        "empire_os/lead_supply_intelligence.py",
        "distinguish insurers and TPAs from agents and brokers; prove B2B "
        "firm identity, buyer need and commercially active capacity",
        "insurance distribution and enterprise analytics market coverage",
    ),
    IntelligenceEdge(
        "source_governance",
        "empire_os/source_intelligence.py",
        "empire_os/scrapling_source_evidence.py",
        "source-specific rights, terms, robots, privacy and document receipt",
        "defensible acquisition and rights-aware datasets",
    ),
    IntelligenceEdge(
        "crawler_to_identity",
        "empire_os/crawler_runner.py",
        "empire_os/prospect_ingest.py",
        "canonical id with source receipt; duplicates and conflicting entities tracked",
        "real niche lead counts instead of crawler request totals",
    ),
    IntelligenceEdge(
        "entity_resolution",
        "empire_os/prospect_ingest.py",
        "empire_os/prospect_enrichment.py",
        "registered business/domain match and human-reviewed uncertain merges",
        "no double selling and cleaner account records",
    ),
    IntelligenceEdge(
        "source_to_qualification",
        "empire_os/prospect_enrichment.py",
        "empire_os/qualification_worker_v2.py",
        "timestamped source fields, actual verification, canonical qualification id",
        "higher usable lead yield",
    ),
    IntelligenceEdge(
        "qualification_to_omega",
        "empire_os/lead_scoring_v2.py",
        "empire_os/intelligence/omega.py",
        "current v2 qualification id plus Omega evidence of same entity",
        "calibrated readiness, not scraped-count scores",
    ),
    IntelligenceEdge(
        "outcome_to_cortex",
        "empire_os/cortex_learning_loop.py",
        "empire_os/economic_memory.py",
        "same paid-and-delivered order; real customer feedback and no test events",
        "realised source economics and long-term model feedback",
    ),
    IntelligenceEdge(
        "market_to_demand",
        "empire_os/market_sweep_revenue_gps.py",
        "empire_os/buyer_demand_graph.py",
        "niche+metro+time+entity-level demand evidence, not unrelated market noise",
        "commercially prioritized crawl targets",
    ),
    IntelligenceEdge(
        "predictive_to_inventory",
        "empire_os/predictive_intelligence.py",
        "empire_os/lead_supply_intelligence.py",
        "calibrated forecast, freshness and matched canonical lead cohort",
        "explainable territory demand/supply outlook",
    ),
    IntelligenceEdge(
        "verified_seats_to_exchange",
        "empire_os/buyer_allocation.py",
        "empire_os/lead_supply_intelligence.py",
        "active signed capacity, price, delivery route and currency",
        "truthful self-serve inventory and priced territories",
    ),
    IntelligenceEdge(
        "supply_to_founder",
        "empire_os/lead_supply_intelligence.py",
        "empire_os/founder_lead_supply_api.py",
        "complete canonical DB count + source overlap + scoring coverage",
        "operational founder niche dashboard",
    ),
    IntelligenceEdge(
        "supply_to_self_serve",
        "empire_os/lead_supply_intelligence.py",
        "empire_os/exchange_self_serve.py",
        "tenant authority, rights, verified commercial seats, billing and fulfilment",
        "safe subscription and territory commerce",
    ),
)

def inspect_code_edges(root: Path) -> dict:
    """Check file existence only. NEVER upgrade this to live-edge verification."""
    if not isinstance(root, Path):
        raise TypeError("root must be pathlib.Path")
    entries = []
    for edge in EDGES:
        d = asdict(edge)
        d["source_code_present"] = (root / edge.source_file).is_file()
        d["sink_code_present"] = (root / edge.sink_file).is_file()
        d["code_complete"] = d["source_code_present"] and d["sink_code_present"]
        d["runtime_linkage_verified"] = False
        d["status"] = (
            "CODE_PRESENT_RUNTIME_UNVERIFIED" if d["code_complete"]
            else "SOURCE_OR_SINK_MISSING"
        )
        entries.append(d)
    return {
        "schema_version": "empire.revenue_data_fabric_code_edges.v1",
        "mode": "READ_ONLY",
        "canonical_database": "EmpireDB PostgreSQL",
        "network_access": False,
        "database_writes": False,
        "payment_activation": False,
        "outbound": False,
        "runtime_linkages_verified": 0,
        "edges": entries,
    }
