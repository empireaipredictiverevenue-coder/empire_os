"""Scientific point-in-time research features for Predictive Revenue.

This adapter connects the market knowledge graph to Quant/Scientific Agent.
It freezes *observed public market research*, not true demand, buyer intent,
conversion probability, economic return, causation or training labels.

Crucial anti-leakage rule: A market graph built after forecast issuance
cannot be retrospectively used as if it were known earlier. Historical
backtesting requires prior saved snapshots and original signed outcomes.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from empire_os.flagship_market_knowledge_graph import (
    SCHEMA as GRAPH_SCHEMA, SOLUTION_MAP,
)

SCHEMA = "empire.predictive_revenue.market_feature_snapshot.v1"
MARKETS = ("roofing", "solar", "hvac", "agency", "b2b", "law")
MAX_GRAPH_NODES = 600
MAX_GRAPH_EDGES = 1800
MAX_AGE = timedelta(hours=6)
MAX_EVENT_AGE = timedelta(days=14)
MAX_HORIZON_DAYS = 90
HEX24 = re.compile(r"^edge_[0-9a-f]{24}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
KNOWN_RELATIONS = frozenset({
    "RESEARCH_SOURCE_COVERS_VERTICAL",
    "RESEARCH_SOURCE_DECLARES_SCOPE",
    "SOURCE_RESEARCHES_OFFER",
    "MAY_INFORM_OFFER_HYPOTHESIS",
    "MAY_INFORM_DATA_PRODUCT",
    "CITED_FROM_PUBLIC_SOURCE",
    "UNVERIFIED_TOPIC_TAG",
    "REPORTS_ON_RETRIEVAL_HEALTH",
    "EXAMPLE_TEACHES_MARKET",
    "EXAMPLE_ILLUSTRATES_THEME",
})


def _time(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 60:
        raise ValueError("timestamp must be bounded")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValueError("timezone-aware source timestamp required")
    return parsed.astimezone(timezone.utc)


def _sha(value: Any) -> str:
    return sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode()).hexdigest()


def build_point_in_time_market_features(
    graph: Mapping[str, Any], *, issued_at: datetime,
    horizon_days: int = 30,
) -> dict[str, Any]:
    """Safe aggregated, frozen evidence features; no model call or training."""
    if not isinstance(issued_at, datetime) or issued_at.utcoffset() is None:
        raise ValueError("trusted forecast issuance time required")
    now = issued_at.astimezone(timezone.utc)
    if type(horizon_days) is not int or not 1 <= horizon_days <= MAX_HORIZON_DAYS:
        raise ValueError("unsupported commercial forecast horizon")
    if not isinstance(graph, Mapping):
        raise ValueError("invalid graph")
    if (graph.get("schema_version") != GRAPH_SCHEMA
            or graph.get("mode") != "OBSERVE"
            or graph.get("execution_authority") != "none"
            or graph.get("status") != "PARTIAL_MARKET_GRAPH_FROM_EXISTING_SOURCES"
            or graph.get("buyer_conversation_verified") is not False
            or graph.get("customer_roi_verified") is not False
            or graph.get("model_weights_updated") is not False
            or graph.get("community_text_reused_for_training") is not False
            or graph.get("external_crawler_run") is not False
            or graph.get("customer_data_accessed") is not False
            or graph.get("payment_authorized") is not False
            or graph.get("outbound_authorized") is not False):
        raise ValueError("untrusted graph or commercial authority")
    built = _time(graph.get("built_at"))
    if not timedelta(0) <= now - built <= MAX_AGE:
        raise ValueError("graph not captured before prospective issuance or stale")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if (not isinstance(nodes, list) or not isinstance(edges, list)
            or len(nodes) > MAX_GRAPH_NODES or len(edges) > MAX_GRAPH_EDGES
            or graph.get("node_count") != len(nodes)
            or graph.get("edge_count") != len(edges)):
        raise ValueError("graph size or count mismatch")
    index: dict[str, Mapping[str, Any]] = {}
    for item in nodes:
        if (not isinstance(item, Mapping)
                or set(item) != {"node_id", "node_type", "metadata"}
                or not isinstance(item["node_id"], str)
                or len(item["node_id"]) > 170
                or not item["node_id"].startswith(item["node_type"] + ":")
                or not isinstance(item["metadata"], Mapping)
                or item["node_id"] in index):
            raise ValueError("untrusted graph node identity")
        index[item["node_id"]] = item
    record_edge_refs = set()
    links: list[Mapping[str, Any]] = []
    for item in edges:
        if (not isinstance(item, Mapping)
                or set(item) != {"edge_id", "source", "relation", "target",
                                   "provenance_sha256", "observed_at", "claim_status"}
                or not isinstance(item.get("edge_id"), str)
                or not HEX24.fullmatch(item["edge_id"])
                or item["edge_id"] in record_edge_refs
                or item.get("source") not in index
                or item.get("target") not in index
                or item.get("relation") not in KNOWN_RELATIONS
                or item.get("claim_status") != "CATEGORICAL_SOURCE_RELATION_NOT_BUYER_PROOF"
                or not isinstance(item.get("provenance_sha256"), str)
                or not HEX64.fullmatch(item["provenance_sha256"])):
            raise ValueError("untrusted graph edge identity/authority")
        record_edge_refs.add(item["edge_id"])
        if item["observed_at"] is not None:
            observed = _time(item["observed_at"])
            if observed > built or observed > now:
                raise ValueError("future source included in prospective features")
        links.append(item)

    by_vertical: dict[str, set[str]] = {market: set() for market in MARKETS}
    for e in links:
        if e["relation"] == "RESEARCH_SOURCE_COVERS_VERTICAL":
            if (index[e["source"]]["node_type"] != "research_source"
                    or index[e["target"]]["node_type"] != "market_vertical"):
                raise ValueError("spoofed source-to-market relation")
            market = e["target"].removeprefix("market_vertical:")
            if market in by_vertical:
                by_vertical[market].add(e["source"])

    post_source: dict[str, tuple[str, datetime]] = {}
    for e in links:
        if e["relation"] != "CITED_FROM_PUBLIC_SOURCE":
            continue
        if (index[e["source"]]["node_type"] != "public_observation"
                or index[e["target"]]["node_type"] != "research_source"
                or e["observed_at"] is None
                or e["source"] in post_source):
            raise ValueError("untrusted, ambiguous public observation lineage")
        observed = _time(e["observed_at"])
        if observed < now - MAX_EVENT_AGE:
            continue
        post_source[e["source"]] = (e["target"], observed)

    tags: dict[str, set[str]] = {}
    for e in links:
        if e["relation"] != "UNVERIFIED_TOPIC_TAG":
            continue
        if (index[e["source"]]["node_type"] != "public_observation"
                or index[e["target"]]["node_type"] != "problem_theme"
                or e["target"].removeprefix("problem_theme:") not in SOLUTION_MAP
                or e["observed_at"] is None):
            raise ValueError("spoofed public theme tag")
        if e["source"] not in post_source:
            raise ValueError("topic tag without attributable time-safe public evidence")
        if _time(e["observed_at"]) != post_source[e["source"]][1]:
            raise ValueError("source/topic chronology conflict")
        tags.setdefault(e["source"], set()).add(
            e["target"].removeprefix("problem_theme:")
        )

    features = []
    for market in MARKETS:
        eligible = by_vertical[market]
        posts = [
            (post, recorded) for post, (source, recorded) in post_source.items()
            if source in eligible
        ]
        topics = Counter(
            topic for post, _ in posts for topic in tags.get(post, set())
        )
        age_buckets = [0, 0, 0]
        for _, observed in posts:
            age_days = (now - observed).total_seconds() / 86400
            age_buckets[0 if age_days < 3 else 1 if age_days < 7 else 2] += 1
        source_digest = _sha({
            "market": market,
            "captured_at": built.isoformat(),
            "research_source_nodes": sorted(eligible),
            "attributed_public_observation_ids": sorted(post for post, _ in posts),
            "topic_tags": sorted(topics.items()),
        })
        features.append({
            "market_vertical": market,
            "source_venue_count": len(eligible),
            "distinct_attributable_public_posts": len(posts),
            "public_post_recency_0_2d": age_buckets[0],
            "public_post_recency_3_6d": age_buckets[1],
            "public_post_recency_7_13d": age_buckets[2],
            "unverified_problem_theme_counts": dict(sorted(topics.items())),
            "feature_lineage_sha256": source_digest,
            "empirical_conversion_labels": 0,
            "public_posts_are_independent_buyer_samples": False,
            "source_selection_bias": "FORUM_OBSERVATION_ONLY",
            "market_demand_zero_verified": False,
            "forecast_probability": None,
            "forecast_revenue_cents": None,
            "predictive_model_training_ready": False,
            "readiness_status": (
                "DESCRIPTIVE_MARKET_SIGNALS_ONLY"
                if posts else "NO_ATTRIBUTABLE_PUBLIC_MARKET_EVIDENCE"
            ),
        })

    observation = {
        "schema_version": SCHEMA,
        "status": "TIME_SAFE_RESEARCH_FEATURES_NOT_PREDICTIVE_FORECASTS",
        "mode": "OBSERVE",
        "graph_captured_at": built.isoformat(),
        "feature_issued_at": now.isoformat(),
        "prospective_horizon_until": (
            now + timedelta(days=horizon_days)
        ).isoformat(),
        "prospective_horizon_days": horizon_days,
        "source_graph_schema_version": GRAPH_SCHEMA,
        "market_features": features,
        "market_count": len(features),
        "observed_public_post_total": sum(
            r["distinct_attributable_public_posts"] for r in features
        ),
        "held_public_observations": graph.get("unattributed_or_invalid_observations"),
        "approved_scenario_lessons_are_not_training_labels": True,
        "future_source_information_used": False,
        "backdated_fabrication_allowed": False,
        "historical_forecast_registry_receipt": None,
        "verified_terminal_outcome_pairs": 0,
        "minimum_verified_outcomes_for_calibration": 20,
        "independent_market_sampling_established": False,
        "model_training_activated": False,
        "revenue_or_buyer_predicted": False,
        "crm_writes": False,
        "external_execution": False,
        "execution_authority": "none",
    }
    observation["feature_packet_sha256"] = _sha(observation)
    return observation


def review_market_feature_prediction_gap(
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Bounded Founder/Scientific Agent briefing, not a customer prediction."""
    if (not isinstance(packet, Mapping)
            or packet.get("schema_version") != SCHEMA
            or packet.get("status") != "TIME_SAFE_RESEARCH_FEATURES_NOT_PREDICTIVE_FORECASTS"
            or packet.get("execution_authority") != "none"
            or packet.get("historical_forecast_registry_receipt") is not None
            or packet.get("verified_terminal_outcome_pairs") != 0
            or packet.get("revenue_or_buyer_predicted") is not False
            or packet.get("model_training_activated") is not False):
        raise ValueError("untrusted predictive market feature packet")
    digest = packet.get("feature_packet_sha256")
    data = dict(packet)
    data.pop("feature_packet_sha256", None)
    if digest != _sha(data):
        raise ValueError("tampered market feature packet")
    rows = packet.get("market_features")
    if not isinstance(rows, list) or len(rows) != len(MARKETS):
        raise ValueError("unknown market feature universe")
    if [row.get("market_vertical") for row in rows] != list(MARKETS):
        raise ValueError("out-of-scope or duplicated market feature")
    from empire_os.quant_brain import quant_decision_packet
    # Quant Brain is the EXISTING scientific/commercial contract. The
    # graph has no validated economics, so pass ZERO factors, not invented
    # probability, revenue, conversion or a fake risk-adjusted ranking.
    quant_holds=[]
    for row in rows:
        quant = quant_decision_packet(
            candidate_id="market_research_" + row["market_vertical"],
            inputs={}, trials=100, seed=0,
        )
        if (quant.get("status") != "UNAVAILABLE"
                or quant.get("execution_authority") != "none"
                or not isinstance(quant.get("missing_fields"), list)):
            raise ValueError("quant evaluation cannot promote market-only research")
        quant_holds.append({
            "market_vertical":row["market_vertical"],
            "quant_status":"UNAVAILABLE",
            "missing_commercial_inputs":quant["missing_fields"],
            "source_feature_lineage_sha256":row["feature_lineage_sha256"],
            "verified_buyer_terms":False,
            "market_features_alone_sufficient_for_quant":False,
        })
    return {
        "schema_version": "empire.predictive_revenue.market_feature_readiness.v1",
        "status": "SCIENTIFIC_EVIDENCE_PREPARED_FORECAST_HELD",
        "market_count": len(rows),
        "market_features_with_observed_public_topics": sum(
            row["readiness_status"] == "DESCRIPTIVE_MARKET_SIGNALS_ONLY"
            for row in rows
        ),
        "time_safe_packet_sha256": digest,
        "canonical_quant_brain_missing_inputs": quant_holds,
        "ready_quant_packet_count": 0,
        "market_preparation": [
            {
                "market_vertical": row["market_vertical"],
                "source_venue_count": row["source_venue_count"],
                "distinct_public_posts": row["distinct_attributable_public_posts"],
                "problem_themes": [
                    {"theme": topic, "unverified_public_tag_count": count}
                    for topic, count in sorted(
                        row["unverified_problem_theme_counts"].items(),
                        key=lambda value: (-value[1], value[0])
                    )[:3]
                ],
                "forecast_ready": False,
            }
            for row in rows
        ],
        "next_evidence_action": "RECORD_ORIGINAL_MARKET_FEATURES_THEN_LINK_VERIFIED_FORECAST_OUTCOMES",
        "missing_ground_truth": "ORIGINAL_BUYER_TERMS_AND_TERMINAL_OUTCOMES",
        "public_forum_selection_bias": True,
        "independent_validation_available": False,
        "brier_evaluation_available": False,
        "realized_revenue_verified": False,
        "prediction_issued": False,
        "execution_authority": "none",
    }
