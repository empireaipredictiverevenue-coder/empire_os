"""Typed scientific evidence pathways across EXISTING Opportunity Factory stages.

Do not confuse a graph of missing evidence with a neural network or causal
model. No model is trained, no probabilities estimated and no inferred sales.
Join canonical radar, factory intake, router and Quant snapshots with exact
same opportunity keys, timestamps and per-row tenant checks, fail closed.
The outcome edge stays BLOCKED until separately verified by Economic Memory.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.opportunity_evidence_router import ROUTES
from empire_os.opportunity_factory_intake import SCORE_KEYS
from empire_os.quant_brain import _DECISION_PACKET_REQUIRED

SCHEMA = "empire.predictive_revenue.evidence_pathways.v1"
SOURCES = {
    "radar": ("runtime/opportunity_radar/latest.json",
              "empire.predictive_cloud.opportunity_radar.v1"),
    "intake": ("runtime/opportunity_factory/intake_latest.json",
               "empire.opportunity_factory_intake_batch.v1"),
    "router": ("runtime/opportunity_factory/evidence_routes_latest.json",
               "empire.opportunity_evidence_routes.v1"),
    "quant": ("runtime/opportunity_factory/quant_review_latest.json",
              "empire.opportunity_quant_review.v1"),
}
MAX_BYTES = 2_000_000
MAX_ROWS = 250
MAX_AGE = timedelta(hours=6)
MAX_SKEW = timedelta(hours=2)
PRIORITY_ORDER = (
    "buyer_intent_normalized_score_required",
    "demand_normalized_score_required",
    "distribution_path_required",
    "offer_key_required",
    "margin_potential_normalized_score_required",
    "distribution_strength_normalized_score_required",
    "fulfilment_readiness_normalized_score_required",
    "urgency_normalized_score_required",
    "independent_evidence_required",
)
STAGES = ("source_observation", "factory_intake", "evidence_router",
          "quant_economics", "commercial_outcome")


class PathwayEvidenceHold(ValueError):
    pass


def _date(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 75:
        raise PathwayEvidenceHold("invalid timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise PathwayEvidenceHold("malformed source timestamp") from exc
    if parsed.utcoffset() is None:
        raise PathwayEvidenceHold("source timestamp must be timezone aware")
    return parsed.astimezone(timezone.utc)


def _validate(source: Mapping[str, Any], name: str, now: datetime):
    schema = SOURCES[name][1]
    if (not isinstance(source, Mapping) or source.get("schema_version") != schema
            or source.get("mode") != "OBSERVE"
            or source.get("execution_authority") != "none"):
        raise PathwayEvidenceHold(f"{name}_source_schema_or_authority")
    stamp = _date(source.get("generated_at"))
    if not timedelta(0) <= now - stamp <= MAX_AGE:
        raise PathwayEvidenceHold(f"{name}_source_stale_or_future")
    field = "candidates" if name == "radar" else "items"
    rows = source.get(field)
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise PathwayEvidenceHold(f"{name}_source_unbounded")
    count_field = ("candidate_count" if name in {"intake", "quant"}
                   else "opportunity_count" if name == "router" else None)
    if count_field is not None and (
        type(source.get(count_field)) is not int or
        source[count_field] != len(rows)
    ):
        raise PathwayEvidenceHold(f"{name}_row_count_mismatch")
    keys = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise PathwayEvidenceHold(f"{name}_non_object_row")
        key = row.get("opportunity_key")
        if not isinstance(key, str) or not 1 <= len(key) <= 180:
            raise PathwayEvidenceHold(f"{name}_identity_invalid")
        if (row.get("tenant_id") not in (None, "")
                or row.get("execution_authority") != "none"):
            raise PathwayEvidenceHold(f"{name}_tenant_or_row_authority")
        keys.append(key)
    if len(set(keys)) != len(keys):
        raise PathwayEvidenceHold(f"{name}_duplicate_identity")
    return {r["opportunity_key"]: r for r in rows}, stamp


def _node(key: str, stage: str) -> str:
    return "path_" + sha256((key + "|" + stage).encode()).hexdigest()[:22]


def _read(repo_root: Path, name: str) -> Mapping[str, Any]:
    root = Path(repo_root).resolve()
    path = root / SOURCES[name][0]
    if (path.is_symlink() or path.parent.is_symlink()
            or (root / "runtime").is_symlink()):
        raise PathwayEvidenceHold("unsafe_source_path")
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
            raise PathwayEvidenceHold(f"{name}_missing_or_unbounded")
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise PathwayEvidenceHold(f"{name}_source_read_error") from exc
    return result


def review_evidence_pathways(
    sources: Mapping[str, Mapping[str, Any]], *,
    as_of: datetime, limit: int = 5,
) -> dict[str, Any]:
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("aware scientific review clock required")
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError("invalid bounded pathway limit")
    now = as_of.astimezone(timezone.utc)
    if not isinstance(sources, Mapping) or set(sources) != set(SOURCES):
        raise PathwayEvidenceHold("missing_or_unknown_evidence_source")
    inventories = {}
    timestamps = []
    for name in SOURCES:
        inventory, observed = _validate(sources[name], name, now)
        inventories[name] = inventory
        timestamps.append(observed)
    if max(timestamps) - min(timestamps) > MAX_SKEW:
        raise PathwayEvidenceHold("source_snapshot_skew_hold")
    anchor = set(inventories["radar"])
    if any(set(rows) != anchor for rows in inventories.values()):
        raise PathwayEvidenceHold("cross_stage_identity_join_mismatch")
    summaries = []
    blocker_occurrences: Counter[str] = Counter()
    for key in sorted(anchor):
        radar = inventories["radar"][key]
        intake = inventories["intake"][key]
        routing = inventories["router"][key]
        quant = inventories["quant"][key]
        packet = quant.get("decision_packet")
        if not isinstance(packet, Mapping) or (
            packet.get("status") not in ("AVAILABLE", "UNAVAILABLE")
            or packet.get("execution_authority") != "none"
            or packet.get("actual_revenue") is not False
            or packet.get("candidate_id") != key
        ):
            raise PathwayEvidenceHold("quant_decision_source_contract_invalid")
        if quant.get("factory_ready") != (intake.get("factory_ready") is True):
            raise PathwayEvidenceHold("quant_factory_readiness_contradiction")
        if (quant.get("prediction_ref") is not None
                and packet.get("status") != "AVAILABLE"):
            raise PathwayEvidenceHold("unavailable_quant_packet_has_prediction_reference")
        missing = packet.get("missing_fields")
        if not isinstance(missing, list) or len(missing) > 40 or len(set(missing)) != len(missing):
            raise PathwayEvidenceHold("invalid_quant_missing_evidence")
        if any(not isinstance(f, str) or f not in _DECISION_PACKET_REQUIRED for f in missing):
            raise PathwayEvidenceHold("unknown_quant_factor")
        if packet["status"] == "UNAVAILABLE" and not missing:
            raise PathwayEvidenceHold("missing_quant_factors_not_explained")
        if packet["status"] == "AVAILABLE" and missing:
            raise PathwayEvidenceHold("available_quant_packet_with_missing_factors")
        routes = routing.get("routes")
        if not isinstance(routes, list) or routing.get("route_count") != len(routes):
            raise PathwayEvidenceHold("router_count_mismatch")
        observed_blockers = intake.get("blockers")
        if (not isinstance(observed_blockers, list)
                or len(set(observed_blockers)) != len(observed_blockers)
                or not all(isinstance(v, str) for v in observed_blockers)):
            raise PathwayEvidenceHold("invalid_factory_blocker_rows")
        if {row.get("blocker") for row in routes if isinstance(row, Mapping)} != set(observed_blockers):
            raise PathwayEvidenceHold("blocker_join_mismatch")
        modes: Counter[str] = Counter()
        for route in routes:
            if not isinstance(route, Mapping):
                raise PathwayEvidenceHold("invalid_route")
            expected = ROUTES.get(route.get("blocker"))
            if expected is None or any(route.get(name) != value for name, value in expected.items()):
                raise PathwayEvidenceHold("untrusted_routing_authority")
            modes[route["mode"]] += 1
            blocker_occurrences[route["blocker"]] += 1
        scores = intake.get("normalized_scores")
        if not isinstance(scores, Mapping) or set(scores) != set(SCORE_KEYS):
            raise PathwayEvidenceHold("invalid_normalized_signal_inventory")
        for value in scores.values():
            if value is not None and (
                type(value) not in (int, float) or not 0 <= value <= 1
            ):
                raise PathwayEvidenceHold("invalid_normalized_score")
        if (intake.get("revenue_verified") is not False
                or radar.get("revenue_inferred") is not False
                or radar.get("buyer_intent_inferred") is not False):
            raise PathwayEvidenceHold("unverified_revenue_or_buyer_claim")
        stage_pass = (
            True,
            intake.get("factory_ready") is True,
            len(routes) == 0,
            packet["status"] == "AVAILABLE",
            False,
        )
        contradictions = []
        if stage_pass[1] and not stage_pass[2]:
            contradictions.append("factory_ready_but_blockers_present")
        if stage_pass[3] and not stage_pass[1]:
            contradictions.append("quant_available_but_factory_not_ready")
        if radar.get("commercial_demand_observed") is True and (
                "buyer_intent_normalized_score_required" in observed_blockers):
            contradictions.append("demand_claim_without_buyer_intent_evidence")
        chosen = next((b for b in PRIORITY_ORDER if b in observed_blockers),
                      sorted(observed_blockers)[0] if observed_blockers else None)
        # Ranking is a transparent evidence-gap heuristic, NOT an estimate
        # of cashflow, success probability, confidence, or causal impact.
        class_count = sum(bool(modes.get(k)) for k in (
            "commercial_observation", "internal_research", "internal_analysis"
        ))
        priority = 2 * len(missing) + 3 * modes["commercial_observation"] + (
            4 if "buyer_intent_normalized_score_required" in observed_blockers else 0
        )
        nodes = [
            {"id": _node(key, stage), "stage": stage,
             "state": "OBSERVED" if i == 0 else
                      "EVIDENCE_READY" if stage_pass[i] else
                      "EVIDENCE_HOLD",
             "commercial_proof": False} for i, stage in enumerate(STAGES)
        ]
        edges = [
            {"from": nodes[i]["id"], "to": nodes[i+1]["id"],
             "evidence_connection": (
                 "UNVERIFIED_OUTCOME" if i == 3
                 else "IDENTITY_JOIN_ONLY" if not stage_pass[i+1]
                 else "SOURCE_JOIN"
             ),
             "downstream_evidence_verified": bool(stage_pass[i+1]) if i < 3 else False,
             "usable_for_model_training": False}
            for i in range(len(nodes)-1)
        ]
        summaries.append({
            "opportunity_ref": "oppref_" + sha256(key.encode()).hexdigest()[:20],
            "niche": radar.get("niche") if isinstance(radar.get("niche"), str) else None,
            "source_stage": "OPPORTUNITY_RADAR_MARKET_RESEARCH",
            "pathway_nodes": nodes,
            "pathway_edges": edges,
            "stages_with_observed_input": sum(stage_pass),
            "quant_packet_available": packet["status"] == "AVAILABLE",
            "factory_ready": stage_pass[1],
            "missing_quant_factors": sorted(missing),
            "missing_quant_factor_count": len(missing),
            "factory_blocker_count": len(observed_blockers),
            "blocker_groups": dict(sorted(modes.items())),
            "first_unverified_requirement": chosen,
            "next_owner": (
                "business_development" if chosen in {
                    "buyer_intent_normalized_score_required",
                    "demand_normalized_score_required",
                } else "market_intelligence" if chosen in {
                    "independent_evidence_required", "urgency_normalized_score_required"
                } else "data_quant" if not chosen else "commercial_operations"
            ),
            "contradictions_to_investigate": contradictions,
            "research_triage_rank": priority,
            "research_triage_rank_is_revenue_probability": False,
            "buyer_or_contract_verified": False,
            "recognized_revenue_cents": None,
            "causal_effect_estimated": False,
            "posterior_probability": None,
            "ready_for_outcome_learning": False,
        })
    summaries.sort(key=lambda x: (
        -x["stages_with_observed_input"],
        len(x["contradictions_to_investigate"]),
        x["missing_quant_factor_count"],
        -x["research_triage_rank"],
        x["opportunity_ref"],
    ))
    contradictory = sum(bool(x["contradictions_to_investigate"]) for x in summaries)
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "status": "EVIDENCE_PATHWAY_REVIEW_READY",
        "source_snapshot_count": len(SOURCES),
        "candidate_count": len(summaries),
        "quant_complete_count": sum(x["quant_packet_available"]
                                  for x in summaries),
        "candidates_with_contradictions": contradictory,
        "all_candidates_are_verified_sales": False,
        "missing_factor_occurrences": dict(sorted(blocker_occurrences.items())),
        "research_shortlist": summaries[:limit],
        "shortlist_only": len(summaries) > limit,
        "source_join_exact_identity_enforced": True,
        "same_candidates_not_independent_buyers": True,
        "causal_inference_performed": False,
        "model_weights_updated": False,
        "buyer_acceptance_verified": False,
        "financial_execution_authorized": False,
        "commercial_outbound_authorized": False,
        "economic_memory_updated": False,
        "external_execution_authorized": False,
        "execution_authority": "none",
    }


def review_evidence_pathways_runtime(
    repo_root: Path, *, as_of: datetime | None = None, limit: int = 5,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    now = as_of or datetime.now(timezone.utc)
    try:
        sources = {name: _read(root, name) for name in SOURCES}
        return review_evidence_pathways(sources, as_of=now, limit=limit)
    except (PathwayEvidenceHold, ValueError) as exc:
        return {
            "schema_version": SCHEMA, "mode": "OBSERVE",
            "generated_at": now.astimezone(timezone.utc).isoformat(),
            "status": "EVIDENCE_PATHWAY_SOURCE_HOLD",
            "reason_code": str(exc)[:100],
            "source_snapshot_count": len(SOURCES),
            "candidate_count": None,
            "quant_complete_count": None,
            "research_shortlist": [],
            "scientific_claims_withheld": True,
            "model_weights_updated": False,
            "economic_memory_updated": False,
            "execution_authority": "none",
        }
