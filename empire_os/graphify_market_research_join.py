"""Explicit, observation-only research juxtaposition for Graphify revenue lanes.

This is NOT a forecast or a buyer-fit model. Input market snapshots must
originate from the existing predictive market feature owner and retain its
point-in-time/provenance controls. Taxonomy joins require an approved mapping;
no semantic/LLM guess or inference is made here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

SCHEMA = "empire.graphify.market_research_join.v1"
LANE_SCHEMA = "empire.graphify.revenue_feature_snapshot.v1"
MARKET_SCHEMA = "empire.predictive_revenue.market_feature_snapshot.v1"
MARKETS = frozenset({"roofing", "solar", "hvac", "agency", "b2b", "law"})
MAX_LANES = 300
MAX_MARKETS = 10


def _sha(data: Any) -> str:
    return sha256(json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _aware(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("invalid time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid time") from exc
    if parsed.utcoffset() is None:
        raise ValueError("timezone-aware time required")
    return parsed.astimezone(timezone.utc)


def _validate_hash(packet: Mapping[str, Any], hash_field: str) -> None:
    token = packet.get(hash_field)
    if not isinstance(token, str) or len(token) != 64:
        raise ValueError("missing original source packet hash")
    raw = {k: v for k, v in packet.items() if k != hash_field}
    if _sha(raw) != token:
        raise ValueError("tampered source packet")


def prepare_graph_market_research_join(
    *, lane_snapshot: Mapping[str, Any],
    market_feature_packet: Mapping[str, Any],
    approved_product_market_map: Mapping[str, str],
) -> dict[str, Any]:
    """Join only owner-reviewed public taxonomies, never claims of buyer intent.

    The original market owner must construct its packet through its own
    build_point_in_time_market_features(...), not an arbitrary web scrape.
    This adapter independently rechecks the critical no-prediction gates.
    """
    if not isinstance(lane_snapshot, Mapping) or not isinstance(market_feature_packet, Mapping):
        raise ValueError("invalid graph research inputs")
    lane = lane_snapshot
    market = market_feature_packet
    if (lane.get("schema_version") != LANE_SCHEMA
            or lane.get("mode") != "OBSERVE"
            or lane.get("execution_authority") != "none"
            or lane.get("forecast_produced") is not False
            or lane.get("model_training_authorized") is not False
            or lane.get("buyer_identity_verified") is not False
            or lane.get("commercial_rights_verified") is not False):
        raise ValueError("invalid graph revenue feature authority")
    _validate_hash(lane, "snapshot_sha256")
    if (market.get("schema_version") != MARKET_SCHEMA
            or market.get("status") != "TIME_SAFE_RESEARCH_FEATURES_NOT_PREDICTIVE_FORECASTS"
            or market.get("mode") != "OBSERVE"
            or market.get("execution_authority") != "none"
            or market.get("model_training_activated") is not False
            or market.get("revenue_or_buyer_predicted") is not False
            or market.get("future_source_information_used") is not False
            or market.get("backdated_fabrication_allowed") is not False
            or market.get("verified_terminal_outcome_pairs") != 0
            or market.get("historical_forecast_registry_receipt") is not None
            or market.get("source_graph_schema_version") != "empire.flagship.market_knowledge_graph.v1"):
        raise ValueError("untrusted market feature packet")
    _validate_hash(market, "feature_packet_sha256")
    issued = _aware(lane.get("issued_at"))
    if _aware(market.get("feature_issued_at")) != issued:
        raise ValueError("market and lane feature issuances must match")
    if _aware(market.get("graph_captured_at")) > issued:
        raise ValueError("future market graph used for earlier issuance")
    if (type(lane.get("horizon_days")) is not int or
            lane["horizon_days"] != market.get("prospective_horizon_days")):
        raise ValueError("inconsistent market feature horizon")
    if (type(market.get("prospective_horizon_days")) is not int or
            not 1 <= market["prospective_horizon_days"] <= 90):
        raise ValueError("invalid forecasting horizon")
    rows = lane.get("feature_rows")
    mrows = market.get("market_features")
    if (not isinstance(rows, list) or len(rows) > MAX_LANES or
            lane.get("feature_count") != len(rows)
            or not isinstance(mrows, list) or len(mrows) != len(MARKETS)
            or market.get("market_count") != len(mrows)):
        raise ValueError("invalid graph feature counts")

    by_market: dict[str, dict[str, Any]] = {}
    for row in mrows:
        if not isinstance(row, Mapping) or row.get("market_vertical") not in MARKETS:
            raise ValueError("invalid source market")
        vert = row["market_vertical"]
        if vert in by_market:
            raise ValueError("duplicate market")
        for field in ("forecast_probability", "forecast_revenue_cents"):
            if row.get(field) is not None:
                raise ValueError("market packet illegally contains forecast")
        if (row.get("predictive_model_training_ready") is not False
                or row.get("market_demand_zero_verified") is not False
                or row.get("public_posts_are_independent_buyer_samples") is not False):
            raise ValueError("market research has been promoted to buyer truth")
        count = row.get("distinct_attributable_public_posts")
        sources = row.get("source_venue_count")
        if (type(count) is not int or type(sources) is not int
                or not 0 <= count <= 10000 or not 0 <= sources <= 10000):
            raise ValueError("invalid market feature counts")
        lineage = row.get("feature_lineage_sha256")
        if (not isinstance(lineage, str) or len(lineage) != 64 or
                any(c not in "0123456789abcdef" for c in lineage)):
            raise ValueError("missing or invalid market feature lineage")
        by_market[vert] = dict(row)

    if set(by_market) != MARKETS:
        raise ValueError("incomplete canonical market feature universe")
    if (not isinstance(approved_product_market_map, Mapping)
            or len(approved_product_market_map) > 100):
        raise ValueError("explicit approved taxonomy map required")
    crosswalk: dict[str, str] = {}
    for product, vertical in approved_product_market_map.items():
        if (not isinstance(product, str) or not product
                or len(product) > 100 or vertical not in by_market):
            raise ValueError("invalid approved taxonomy mapping")
        crosswalk[product] = vertical

    joined = []
    seen_lanes: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("invalid lane feature")
        ref = row.get("lane_ref")
        if not isinstance(ref, str) or not ref.startswith("revenue:") or ref in seen_lanes:
            raise ValueError("invalid or duplicate lane")
        seen_lanes.add(ref)
        if (row.get("conversion_probability") is not None
                or row.get("forecast_demand_units") is not None
                or row.get("realized_revenue_usd") is not None
                or row.get("verified_buyer_capacity") is not None):
            raise ValueError("lane snapshot contains unauthenticated economic claim")
        for fld in ("reported_buyer_demand_link_count",
                    "reported_buyer_capacity_link_count",
                    "demand_quantity_unknown_edge_count",
                    "fresh_evidence_edge_count"):
            n = row.get(fld)
            if type(n) is not int or not 0 <= n <= 100000:
                raise ValueError("invalid lane evidence count")
        names = row.get("product_categories")
        if not isinstance(names, list) or len(names) > 20:
            raise ValueError("invalid lane category list")
        matched = sorted({crosswalk[v] for v in names if v in crosswalk})
        if len(matched) > 1:
            raise ValueError("ambiguous taxonomy mapping for a lane")
        m = by_market.get(matched[0]) if matched else None
        joined.append({
            "lane_ref": ref,
            "matched_market_vertical": matched[0] if matched else None,
            "mapping_status": "EXPLICIT_TAXONOMY_MATCH_RESEARCH_ONLY" if m else "NO_APPROVED_MARKET_MAPPING",
            "reported_buyer_demand_links": row["reported_buyer_demand_link_count"],
            "reported_buyer_capacity_links": row["reported_buyer_capacity_link_count"],
            "unknown_demand_edges": row["demand_quantity_unknown_edge_count"],
            "fresh_lane_evidence_edges": row["fresh_evidence_edge_count"],
            "public_forum_observation_count": m["distinct_attributable_public_posts"] if m else None,
            "public_research_venue_count": m["source_venue_count"] if m else None,
            "market_source_lineage_sha256": m["feature_lineage_sha256"] if m else None,
            "buyer_capacity_verified": False,
            "demand_or_purchase_intent_verified": False,
            "commercial_rights_verified": False,
            "predictive_uplift_verified": False,
            "forecast_probability": None,
            "forecast_net_revenue": None,
        })

    result = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "status": "RESEARCH_COMPARISON_ONLY_NO_BUYER_OR_REVENUE_PROOF",
        "feature_issued_at": issued.isoformat(),
        "horizon_days": lane["horizon_days"],
        "source_market_feature_sha256": market["feature_packet_sha256"],
        "source_lane_feature_sha256": lane["snapshot_sha256"],
        "joined_lane_count": len(joined),
        "matched_market_count": len({
            row["matched_market_vertical"] for row in joined
            if row["matched_market_vertical"] is not None
        }),
        "matched_lane_count": sum(
            row["matched_market_vertical"] is not None for row in joined
        ),
        "joined_lanes": joined,
        "model_training_authorized": False,
        "campaign_execution_authorized": False,
    }
    result["comparison_sha256"] = _sha(result)
    return result
