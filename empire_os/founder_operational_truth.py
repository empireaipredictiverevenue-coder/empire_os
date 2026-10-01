"""Read-only founder operational truth across revenue lanes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.a2a_discovery import commerce_discovery_manifest
from empire_os.agent_web import capability_manifest

ROOT = Path("/srv/empire_os")
DEFAULT_PATHS = {
    "revenue_pulse": ROOT / "runtime/revenue_pulse/latest.json",
    "sell_now": ROOT / "runtime/predictive_revenue/sell_now/latest.json",
    "buyer_acquisition": ROOT / "runtime/buyer_acquisition/latest.json",
    "commercial_exchange": ROOT / "runtime/commercial_exchange/latest.json",
    "owned_campaigns": ROOT / "runtime/astra/owned_campaign_activation_v2_prepared/report.json",
}
LANE_STATES = frozenset({"LIVE", "READY", "GATED", "BLOCKED", "OBSERVE", "UNKNOWN"})


def _read(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _lane(
    key: str,
    state: str,
    *,
    detail: str,
    blocker: str | None = None,
    founder_gate: bool = False,
    next_action: str | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if state not in LANE_STATES:
        raise ValueError("invalid operational lane state")
    return {
        "key": key,
        "state": state,
        "detail": detail,
        "blocker": blocker,
        "founder_gate": founder_gate,
        "next_action": next_action,
        "evidence": dict(evidence or {}),
        "execution_authority": "none",
    }


def build_operational_truth(
    *,
    paths: Mapping[str, Path] | None = None,
    public_base_url: str = "https://empire-ai.co.uk",
) -> dict[str, Any]:
    cfg = {**DEFAULT_PATHS, **dict(paths or {})}
    pulse = _read(cfg["revenue_pulse"])
    sell = _read(cfg["sell_now"])
    buyers = _read(cfg["buyer_acquisition"])
    exchange = _read(cfg["commercial_exchange"])
    campaigns = _read(cfg["owned_campaigns"])
    a2a = commerce_discovery_manifest(
        public_base_url=public_base_url,
        public_capability_names=[item["name"] for item in capability_manifest("a2a")],
    )

    lanes: list[dict[str, Any]] = []

    if pulse is None:
        lanes.append(_lane("buyer_conversations", "UNKNOWN", detail="Revenue Pulse unavailable"))
        lanes.append(_lane("verified_revenue", "UNKNOWN", detail="Revenue truth unavailable"))
    else:
        pulse_state = str(pulse.get("pulse_state") or "unknown")
        blocker = str(pulse.get("highest_priority_blocker") or "") or None
        convo_state = "BLOCKED" if blocker == "buyer_conversation" else "OBSERVE"
        lanes.append(_lane(
            "buyer_conversations",
            convo_state,
            detail=f"Revenue Pulse: {pulse_state}",
            blocker=blocker,
            next_action="Advance genuine buyer replies into commercial terms" if blocker == "buyer_conversation" else None,
            evidence={"pulse_state": pulse_state},
        ))
        truth = pulse.get("recognized_revenue_truth")
        cents = truth.get("recognized_revenue_cents") if isinstance(truth, Mapping) else None
        if isinstance(cents, int) and cents > 0:
            revenue_state, revenue_detail = "LIVE", f"Verified recognized revenue: {cents} cents"
        elif cents == 0:
            revenue_state, revenue_detail = "BLOCKED", "Verified recognized revenue is zero"
        else:
            revenue_state, revenue_detail = "UNKNOWN", "Recognized revenue is unknown"
        lanes.append(_lane(
            "verified_revenue",
            revenue_state,
            detail=revenue_detail,
            blocker=blocker if revenue_state != "LIVE" else None,
            evidence={"recognized_revenue_cents": cents},
        ))

    if sell is None:
        lanes.append(_lane("sell_now", "UNKNOWN", detail="Sell Now snapshot unavailable"))
    else:
        count = int(sell.get("sell_now_count") or 0)
        ready = int(sell.get("ready_product_count") or 0)
        review = int(sell.get("needs_review_count") or 0)
        if count > 0:
            state, blocker = "READY", None
        elif ready > 0 and review > 0:
            state, blocker = "BLOCKED", "opportunity_factory_readiness"
        else:
            state, blocker = "OBSERVE", "no_sell_now_route"
        lanes.append(_lane(
            "sell_now",
            state,
            detail=f"{ready} ready products; {count} Sell Now routes; {review} review-gated",
            blocker=blocker,
            next_action="Convert genuine demand/economics/fulfilment evidence into factory-ready routes" if blocker else None,
            evidence={
                "ready_product_count": ready,
                "sell_now_count": count,
                "matched_route_count": sell.get("matched_route_count"),
                "needs_review_count": review,
            },
        ))

    if campaigns is None:
        lanes.append(_lane("owned_free_traffic", "UNKNOWN", detail="Owned campaign preflight unavailable"))
    else:
        requested = int(campaigns.get("campaigns_requested") or 0)
        passed = int(campaigns.get("campaigns_preflight_passed") or 0)
        db_gate = bool(campaigns.get("founder_db_approval_required"))
        published = bool(campaigns.get("publication_performed"))
        if published:
            state, blocker, gate = "LIVE", None, False
        elif db_gate:
            state, blocker, gate = "GATED", "migration_025_owned_campaign_intake", True
        elif requested and passed == requested:
            state, blocker, gate = "READY", None, False
        else:
            state, blocker, gate = "BLOCKED", "owned_campaign_preflight", False
        lanes.append(_lane(
            "owned_free_traffic",
            state,
            detail=f"{passed}/{requested} campaigns preflight-passed; published={published}",
            blocker=blocker,
            founder_gate=gate,
            next_action="Approve migration 025, verify live schema/role, then release owned routes" if gate else None,
            evidence={
                "campaigns_requested": requested,
                "campaigns_preflight_passed": passed,
                "campaigns_blocked": campaigns.get("campaigns_blocked"),
                "publication_performed": published,
            },
        ))

    commercial = a2a.get("commercial_discovery") if isinstance(a2a, Mapping) else None
    auth_status = commercial.get("authentication_status") if isinstance(commercial, Mapping) else None
    a2a_state = "READY" if auth_status == "activated" else "GATED"
    lanes.append(_lane(
        "a2a_commerce",
        a2a_state,
        detail=f"Public A2A discovery is live; commercial authentication={auth_status or 'unknown'}",
        blocker=None if a2a_state == "READY" else "a2a_commercial_authentication_not_activated",
        founder_gate=False,
        next_action="Activate governed authenticated intent-to-review path" if a2a_state != "READY" else None,
        evidence={"authentication_status": auth_status},
    ))

    if buyers is None:
        lanes.append(_lane("buyer_acquisition", "UNKNOWN", detail="Buyer acquisition snapshot unavailable"))
    else:
        sent = bool(buyers.get("outbound_sent"))
        targets = int(buyers.get("icp_priority_target_count") or 0)
        state = "LIVE" if sent else ("READY" if targets > 0 else "OBSERVE")
        lanes.append(_lane(
            "buyer_acquisition",
            state,
            detail=f"{targets} ICP priority targets; outbound_sent={sent}",
            blocker=None if sent else "governed_send_not_executed",
            founder_gate=not sent and targets > 0,
            next_action="Founder-approved person-bound send for genuine ready targets" if not sent and targets > 0 else None,
            evidence={
                "icp_priority_target_count": targets,
                "outbound_sent": sent,
                "sellable_product_demand_count": buyers.get("sellable_product_demand_count"),
            },
        ))

    if exchange is None:
        lanes.append(_lane("commercial_exchange", "UNKNOWN", detail="Commercial Exchange snapshot unavailable"))
    else:
        allocated = int(exchange.get("allocated_count") or 0)
        inventory = int(exchange.get("inventory_count") or 0)
        seats = int(exchange.get("buyer_seat_count") or 0)
        candidates = int(exchange.get("allocation_candidate_count") or 0)
        if allocated > 0:
            state, blocker = "LIVE", None
        elif inventory > 0 and seats > 0 and candidates == 0:
            state, blocker = "BLOCKED", "allocation_candidate_generation"
        else:
            state, blocker = "OBSERVE", "commercial_exchange_not_active"
        lanes.append(_lane(
            "commercial_exchange",
            state,
            detail=f"{inventory} inventory; {seats} buyer seats; {candidates} allocation candidates; {allocated} allocated",
            blocker=blocker,
            next_action="Generate evidence-backed allocation candidates" if blocker else None,
            evidence={
                "inventory_count": inventory,
                "buyer_seat_count": seats,
                "corridor_count": exchange.get("corridor_count"),
                "allocation_candidate_count": candidates,
                "allocated_count": allocated,
            },
        ))

    counts = {state: sum(1 for lane in lanes if lane["state"] == state) for state in sorted(LANE_STATES)}
    return {
        "schema_version": "empire.founder-operational-truth.v1",
        "mode": "OBSERVE",
        "lanes": lanes,
        "summary": {
            "lane_count": len(lanes),
            "by_state": counts,
            "founder_gate_count": sum(1 for lane in lanes if lane["founder_gate"]),
        },
        "external_send": False,
        "payment_action": False,
        "revenue_recognition": False,
        "production_deploy": False,
        "execution_authority": "none",
    }
