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
