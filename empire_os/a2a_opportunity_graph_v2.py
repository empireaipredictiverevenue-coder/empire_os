"""Privacy-minimised, evidence-scoped opportunity knowledge graph.

Tracks market -> report -> product -> geo -> source/owner dependencies.
Never resolves a private person's identity, asserts unseen buyer relationships,
or treats two observations from the same aggregate as independent confirmation.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import re

from empire_os.a2a_signal_decision_intelligence_v2 import SCHEMA as INTEL_SCHEMA
from empire_os.a2a_data_campaign_release_review import SCHEMA as RELEASE_SCHEMA

SCHEMA = "empire.a2a.opportunity_evidence_graph.v2"
_SAFE = re.compile(r"^[a-z0-9_., /-]{1,120}$")


def make_opportunity_graph(
    decision: Mapping[str, Any], releases: Mapping[str, Any],
) -> dict[str, Any]:
    if (not isinstance(decision, Mapping)
            or decision.get("schema_version") != INTEL_SCHEMA
            or decision.get("execution_authority") != "NONE"
            or decision.get("verified_new_buyers") != 0
            or decision.get("publications") is not False
            or decision.get("outbound") is not False):
        raise ValueError("UNTRUSTED_DECISION_PACKET")
    if (not isinstance(releases, Mapping)
            or releases.get("schema_version") != RELEASE_SCHEMA
            or releases.get("execution_authority") != "NONE"
            or releases.get("launch_ready_campaign_count") != 0):
        raise ValueError("UNTRUSTED_RELEASE_PACKET")
    rows = decision.get("research_priorities")
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("INVALID_RESEARCH_ROWS")
    campaigns = releases.get("campaigns")
    if not isinstance(campaigns, list) or len(campaigns) > 10:
        raise ValueError("INVALID_CAMPAIGN_ROWS")
    nodes: dict[str, dict] = {}
    edges: set[tuple[str, str, str]] = set()
    def node(key: str, kind: str, label: str, *, state: str) -> None:
        if key in nodes:
            if nodes[key]["kind"] != kind:
                raise ValueError("DUPLICATE_CROSS_TYPE_GRAPH_NODE")
            return
        nodes[key] = {"id": key, "kind": kind, "label": label, "state": state}
    def edge(a: str, b: str, rel: str) -> None:
        edges.add((a, b, rel))
    for source in ("community_intent", "revenue_gps"):
        node("source:" + source, "source_report", source,
             state="OWNER_REPORT_FRESHNESS_UNATTESTED")
    node("source:brokerage_catalogue", "source_report", "data_brokerage_catalogue",
         state=("STALE_OWNER_REVIEW" if decision.get("catalogue_stale") is True
                else "OWNER_RESEARCH_REPORT_NOT_LICENCE"))
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("INVALID_GRAPH_RESEARCH_ROW")
        sid, source, niche, metro = (row.get(k) for k in
                                     ("segment_id", "source_class", "niche", "metro"))
        if source not in ("community_intent", "revenue_gps"):
            raise ValueError("UNKNOWN_RESEARCH_SOURCE")
        if (not isinstance(sid, str) or len(sid) != 16
                or any(c not in "0123456789abcdef" for c in sid)):
            raise ValueError("INVALID_GRAPH_SEGMENT_ID")
        if not all(isinstance(t, str) and _SAFE.fullmatch(t) for t in (niche, metro)):
            raise ValueError("UNSAFE_GRAPH_DIMENSION")
        entity = "market:" + sid
        node(entity, "opportunity_hypothesis", niche + " / " + metro,
             state="RESEARCH_ONLY_NOT_VERIFIED_BUYER")
        edge(entity, "source:" + source, "DERIVED_FROM_AGGREGATE_REPORT")
        geo = "geo:" + sha256(metro.encode()).hexdigest()[:14]
        node(geo, "geography_hypothesis", metro,
             state=("NOT_ESTABLISHED" if metro == "not_established"
                    else "GEOGRAPHY_NOT_VERIFIED_BUYER_COVERAGE"))
        edge(entity, geo, "GEO_RESEARCH_HYPOTHESIS")
        product_id = row.get("product_hypothesis")
        if isinstance(product_id, str) and _SAFE.fullmatch(product_id):
            product = "product:" + product_id
            node(product, "data_product_hypothesis", product_id,
                 state="LICENCE_AND_DELIVERABILITY_NOT_CONFIRMED")
            edge(entity, product, "PRODUCT_RELEVANCE_NOT_LICENSE")
            edge(product, "source:brokerage_catalogue", "REQUIRES_LICENCE_REVIEW")
        for step in row.get("next_best_verification_steps") or []:
            if not isinstance(step, Mapping) or not isinstance(step.get("owner"), str):
                raise ValueError("INVALID_RESEARCH_TASK_OWNER")
            owner_name = step["owner"]
            if not _SAFE.fullmatch(owner_name):
                raise ValueError("UNSAFE_TASK_OWNER")
            owner = "owner:" + owner_name
            node(owner, "domain_owner", owner_name, state="EXISTING_OWNER_NOT_TASK_DISPATCH")
            edge(entity, owner, "REQUIRES_OWNER_REVIEW")
    for campaign in campaigns:
        if not isinstance(campaign, Mapping):
            raise ValueError("INVALID_GRAPH_CAMPAIGN")
        cid, niche, metro = (campaign.get(k) for k in
                             ("campaign_id", "sector", "metro"))
        if not isinstance(cid, str) or not cid.startswith("research-only-") or len(cid) > 80:
            raise ValueError("INVALID_GRAPH_CAMPAIGN_ID")
        if not all(isinstance(t, str) and _SAFE.fullmatch(t) for t in (niche, metro)):
            raise ValueError("UNSAFE_GRAPH_CAMPAIGN_DIMENSION")
        cid = "campaign:" + cid
        node(cid, "campaign_draft", niche + " / " + metro,
             state="NOT_APPROVED_NOT_LIVE")
        for row in rows:
            if row.get("niche") == niche and row.get("metro") == metro:
                edge(cid, "market:" + row["segment_id"], "TESTS_MARKET_HYPOTHESIS")
    ordered_nodes = sorted(nodes.values(), key=lambda x: x["id"])
    ordered_edges = [{"from": a, "to": b, "relation": rel}
                     for a, b, rel in sorted(edges)]
    if any(e["from"] not in nodes or e["to"] not in nodes for e in ordered_edges):
        raise ValueError("DANGLING_GRAPH_EDGE")
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE", "execution_authority": "NONE",
        "node_count": len(ordered_nodes), "edge_count": len(ordered_edges),
        "nodes": ordered_nodes, "edges": ordered_edges,
        "source_family_count": 2,
        "source_independence": {
            "community_intent": "ONE_AGGREGATE_FAMILY",
            "revenue_gps": "ONE_AGGREGATE_FAMILY",
            "source_rows_not_independent_commercial_confirmations": True,
        },
        "buyers_verified_through_graph": 0,
        "personal_identity_nodes": 0,
        "finance_claim_nodes": 0,
        "source_licence_grants": 0,
        "calibrated_purchase_probability": None,
        "automatic_learning_from_unverified_outcomes": False,
        "graph_backend": "DETERMINISTIC_JSON_NOT_EXTERNAL_GRAPH_DATABASE",
        "outbound_authority": False, "customer_data_export": False,
    }
