"""Read-only, point-in-time features from the existing BuyerDemandGraph.

For the EXISTING predictive decision owner; does not predict revenue, train
models, authenticate buyers, reserve capacity or create real-world evidence.
Only direct, source-referenced commercial graph edges are summarized.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any

from empire_os.buyer_demand_graph import BuyerDemandGraph
from empire_os.graphify_dual_bridge import project_buyer_demand

SCHEMA = "empire.graphify.revenue_feature_snapshot.v1"
MAX_AGE_DAYS = 30
MAX_HORIZON_DAYS = 90


def _date(value: str) -> datetime:
    if not isinstance(value, str) or len(value) > 60:
        raise ValueError("invalid observed_at")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid observed_at") from exc
    if dt.utcoffset() is None:
        raise ValueError("observed_at must be timezone aware")
    return dt.astimezone(timezone.utc)


def build_graph_feature_snapshot(
    graph: BuyerDemandGraph, *, issued_at: datetime, privacy_key: bytes,
    approved_category_labels: frozenset[str] = frozenset(),
    horizon_days: int = 30, max_age_days: int = 14,
) -> dict[str, Any]:
    """Return evidence-count features; never infer demand or forecast value.

    Events after issuance fail closed. Old observations are excluded from
    feature counts and reported explicitly. Missing demand quantities stay
    unknown. Capacity is NEVER summed as buyers can share cross-lane limits.
    """
    if not isinstance(issued_at, datetime) or issued_at.utcoffset() is None:
        raise ValueError("trusted timezone-aware issuance required")
    if (type(horizon_days) is not int or
            not 1 <= horizon_days <= MAX_HORIZON_DAYS):
        raise ValueError("invalid horizon_days")
    if (type(max_age_days) is not int or
            not 1 <= max_age_days <= MAX_AGE_DAYS):
        raise ValueError("invalid max_age_days")

    issued = issued_at.astimezone(timezone.utc)
    # This revalidates the typed commercial graph against canonical constraints.
    revenue = project_buyer_demand(
        graph, privacy_key=privacy_key,
        approved_category_labels=approved_category_labels,
    )
    nodes = {item["id"]: item for item in revenue["nodes"]}
    lanes = {k: {"lane_ref": k, "product_categories": set(),
                 "market_categories": set(), "buyers_with_reported_demand": set(),
                 "buyers_with_reported_capacity": set(), "source_signal_refs": set(),
                 "demand_quantity_known_edges": 0,
                 "demand_quantity_unknown_edges": 0,
                 "capacity_quantity_known_edges": 0,
                 "fresh_evidence_edges": 0, "stale_evidence_edges": 0,
                 "evidence_fingerprints": set()}
             for k, node in nodes.items() if node["type"] == "lane"}
    stale_cutoff = issued - timedelta(days=max_age_days)
    for edge in revenue["edges"]:
        observed = _date(edge["observed_at"])
        if observed > issued:
            raise ValueError("future evidence cannot influence earlier issuance")
        source = edge["source"]
        target = edge["target"]
        if target not in lanes:
            raise ValueError("commercial relation target must be an existing lane")
        row = lanes[target]
        if observed < stale_cutoff:
            row["stale_evidence_edges"] += 1
            continue
        row["fresh_evidence_edges"] += 1
        row["evidence_fingerprints"].update(edge["evidence_fingerprints"])
        relation = edge["relation"]
        if relation == "PRODUCT_DEFINES_LANE":
            row["product_categories"].add(nodes[source]["label"])
        elif relation == "MARKET_DEFINES_LANE":
            row["market_categories"].add(nodes[source]["label"])
        elif relation == "SIGNAL_SUPPORTS_LANE":
            row["source_signal_refs"].add(source)
        elif relation == "BUYER_DEMANDS_LANE":
            row["buyers_with_reported_demand"].add(source)
            key = ("demand_quantity_known_edges" if
                   edge["demand_units"] is not None else
                   "demand_quantity_unknown_edges")
            row[key] += 1
        elif relation == "BUYER_HAS_CAPACITY_FOR_LANE":
            row["buyers_with_reported_capacity"].add(source)
            if edge["capacity_remaining"] is not None:
                row["capacity_quantity_known_edges"] += 1
        else:
            raise ValueError("unsupported commercial relation")

    features = []
    for lane, row in sorted(lanes.items()):
        # The graph structure is evidence of a relationship only, not a signed
        # commercial agreement or proof a household needs a service.
        fresh = row["fresh_evidence_edges"]
        features.append({
            "lane_ref": lane,
            "product_categories": sorted(row["product_categories"]),
            "market_categories": sorted(row["market_categories"]),
            "reported_buyer_demand_link_count":
                len(row["buyers_with_reported_demand"]),
            "reported_buyer_capacity_link_count":
                len(row["buyers_with_reported_capacity"]),
            "source_signal_link_count": len(row["source_signal_refs"]),
            "demand_quantity_known_edge_count":
                row["demand_quantity_known_edges"],
            "demand_quantity_unknown_edge_count":
                row["demand_quantity_unknown_edges"],
            "capacity_quantity_known_edge_count":
                row["capacity_quantity_known_edges"],
            "fresh_evidence_edge_count": fresh,
            "stale_evidence_edge_count": row["stale_evidence_edges"],
            "evidence_fingerprints": sorted(row["evidence_fingerprints"]),
            "feature_eligibility": "OWNER_REVIEW_REQUIRED" if fresh else "NO_FRESH_EVIDENCE",
            "verified_buyer_capacity": None,
            "realized_revenue_usd": None,
            "conversion_probability": None,
            "forecast_demand_units": None,
        })
    result = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "model_training_authorized": False,
        "forecast_produced": False,
        "buyer_identity_verified": False,
        "commercial_rights_verified": False,
        "issued_at": issued.isoformat(),
        "horizon_days": horizon_days,
        "max_age_days": max_age_days,
        "feature_count": len(features),
        "feature_rows": features,
    }
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
    result["snapshot_sha256"] = sha256(payload.encode("utf-8")).hexdigest()
    return result
