"""Read-only re-entry of Empire GTM Intelligence into canonical opportunity evidence.

This is an observer/decision adapter for the EXISTING GTM agent, not a new
agent, worker, CRM, publisher, email sender, or authority grant.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.gtm_agent import GTM_AGENT_ID, decide_next_gtm_action
from empire_os.gtm_commercial_source_bridge import observe_product_sources
from empire_os.opportunity_source_custody import source_fresh

RADAR = Path("runtime/opportunity_radar/latest.json")
COMMERCIAL_LOOP = Path("runtime/commercial_loop/latest.json")
OUTPUT = Path("runtime/gtm_pipeline/integration_observer_latest.json")
SOURCE_LANES = {
    "market_sweeps_revenue_gps": "market_gps",
    "community_intent": "community_intent",
    "competitor_market_opportunity": "competitor_market",
    "storm_opportunity": "storm_opportunity",
    "tam_market_intelligence": "tam_market",
}


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _recent_file(path: Path, now: datetime) -> bool:
    if path.is_symlink():
        return False
    try:
        age = now.timestamp() - path.stat().st_mtime
    except OSError:
        return False
    return 0 <= age <= timedelta(hours=24).total_seconds()


def build_gtm_integration_observation(
    radar: Mapping[str, Any],
    commercial_loop: Mapping[str, Any],
    *,
    now: datetime,
    radar_source_fresh: bool,
    commercial_loop_fresh: bool,
    limit: int = 25,
) -> dict[str, Any]:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    bounded = max(1, min(int(limit), 50))
    mode_ok = radar.get("mode") == "OBSERVE"
    sources = radar.get("source_status")
    sources = sources if isinstance(sources, Mapping) else {}
    candidates = radar.get("candidates")
    candidates = candidates if isinstance(candidates, list) else []
    incoming: list[dict[str, Any]] = []
    held = 0
    seen: set[str] = set()
    for raw in candidates[:bounded]:
        if not isinstance(raw, Mapping):
            held += 1
            continue
        key = str(raw.get("opportunity_key") or "").strip()
        source = str(raw.get("source") or "").strip()
        lane = SOURCE_LANES.get(source)
        source_state = sources.get(lane) if lane else None
        admissible = (
            mode_ok and radar_source_fresh and bool(key)
            and lane is not None and isinstance(source_state, Mapping)
            and source_state.get("available") is True
            and raw.get("execution_authority") in (None, "none")
            and isinstance(raw.get("evidence_refs"), list)
            and len(raw.get("evidence_refs") or []) > 0
            and key not in seen
        )
        if not admissible:
            held += 1
            continue
        seen.add(key)
        incoming.append({
            "handoff_id": hashlib.sha256(
                f"{source}|{key}".encode("utf-8")
            ).hexdigest()[:24],
            "source": source,
            "opportunity_key": key,
            "product_key": str(raw.get("offer_key") or "").strip() or None,
            "opportunity_class": str(raw.get("opportunity_class") or ""),
            "evidence_ref_count": len(raw["evidence_refs"]),
            "gtm_next_step": "gtm.plan",
            "status": "INTERNAL_RESEARCH_REVIEW_ONLY",
            "buyer_identity_verified": False,
            "outbound_authorized": False,
            "crm_write_authorized": False,
            "commercial_terms_authorized": False,
            "economic_outcome_verified": False,
        })
    agent: dict[str, Any] | None = None
    if (
        commercial_loop_fresh
        and commercial_loop.get("mode") == "OBSERVE"
    ):
        decision = decide_next_gtm_action(commercial_loop, now=now)
        agent = decision.as_dict()
    return {
        "schema_version": "empire.gtm.integration_observer.v1",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "mode": "OBSERVE",
        "agent_id": GTM_AGENT_ID,
        "agent_decision": agent,
        "commercial_loop_current": bool(agent is not None),
        "radar_evidence_current": bool(mode_ok and radar_source_fresh),
        "source_candidate_count": len(candidates),
        "internal_research_review_count": len(incoming),
        "held_candidate_count": held + max(0, len(candidates) - bounded),
        "handoffs": incoming,
        "authority": "none",
        "execution_authority": "none",
        "crm_write_performed": False,
        "outreach_sent": False,
        "publication_performed": False,
        "payments_executed": False,
        "revenue_recognized": False,
    }


def observe_gtm_integration(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    radar_path = root / RADAR
    loop_path = root / COMMERCIAL_LOOP
    radar = _load(radar_path)
    loop = _load(loop_path)
    payload = build_gtm_integration_observation(
        radar,
        loop,
        now=clock,
        radar_source_fresh=source_fresh(radar_path, radar, now=clock),
        commercial_loop_fresh=_recent_file(loop_path, clock),
    )
    # Existing JEV, owner GSC and independently authorised first-party
    # aggregate receipts remain separate source classes, not CRM candidates.
    payload["product_sources"] = observe_product_sources(root, now=clock)
    output = root / OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(output)
    return payload
