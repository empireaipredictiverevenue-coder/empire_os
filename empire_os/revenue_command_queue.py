"""Revenue Command Queue projection for Founder Console.

This is a read-only coordination layer over canonical EmpireOS evidence.
It does not create another CRM, buyer store, opportunity engine, or revenue
ledger. It translates existing Next-Best Actions and commercial runtime truth
into a compact queue showing what can move toward revenue now, what is blocked,
and what requires a founder gate or external event.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.commercial_funnel import build_funnel_runtime
from empire_os.next_best_action import build_next_best_action_runtime
from empire_os.revenue_pulse import build_revenue_pulse_runtime


SCHEMA_VERSION = "empire.revenue_command_queue.v1"

_BLOCKER_BY_ACTION = {
    "enrich_identity": "account_research_incomplete",
    "research_more": "canonical_readiness_evidence_incomplete",
    "verify_decision_maker": "decision_maker_identity_unverified",
    "prepare_buyer_review": None,
    "conversation_follow_up": "commercial_intent_not_observed",
    "terms_candidate": "binding_terms_absent",
    "payment_review": "payment_request_authority_gated",
    "fulfilment_review": "fulfilment_not_observed",
}

_STAGE_DEPTH = {
    "DISCOVERED": 1,
    "ICP_MATCH": 2,
    "SIGNAL_ACTIVE": 2,
    "RESEARCHED": 3,
    "READY": 4,
    "CONTACTED": 5,
    "ENGAGED": 6,
    "CONVERSATION": 7,
    "COMMERCIAL_INTENT": 8,
    "TERMS": 9,
    "PAYMENT_PENDING": 10,
    "PAID": 11,
    "FULFILLED": 12,
    "EXPANSION": 13,
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _evidence_refs(action: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []

    entity_id = _clean(action.get("entity_id"))
    prospect_id = _clean(action.get("prospect_id"))
    if entity_id:
        refs.append(f"business_entity:{entity_id}")
    if prospect_id:
        refs.append(f"prospect:{prospect_id}")

    evidence = action.get("evidence")
    if isinstance(evidence, Mapping):
        for key, value in evidence.items():
            if not value:
                continue
            if key.endswith("_ref") and isinstance(value, str):
                refs.append(value)
            elif key.endswith("_id") and isinstance(value, str):
                kind = key.removesuffix("_id")
                refs.append(f"{kind}:{value}")

    return list(dict.fromkeys(refs))


def _queue_item(action: Mapping[str, Any]) -> dict[str, Any]:
    recommended = _clean(action.get("recommended_action")) or "hold"
    authority = _clean(action.get("authority")) or "observe"
    state = _clean(action.get("current_factual_state")) or "UNKNOWN"
    waiting_external = action.get("waiting_external") is True
    founder_gate = action.get("founder_gate_required") is True

    if recommended == "hold" and waiting_external:
        blocker = "external_event_pending"
    elif recommended == "hold":
        blocker = "no_stronger_evidence_backed_action"
    else:
        blocker = _BLOCKER_BY_ACTION.get(recommended)

    reversible_internal = (
        recommended
        if authority == "internal_write"
        and not founder_gate
        and not waiting_external
        else None
    )

    return {
        "entity_id": _clean(action.get("entity_id")) or None,
        "company_name": _clean(action.get("company_name")) or None,
        "prospect_id": _clean(action.get("prospect_id")) or None,
        "current_commercial_state": state,
        "commercial_stage_depth": _STAGE_DEPTH.get(state),
        "product_code": None,
        "offer_known": False,
        "recommended_action": recommended,
        "next_reversible_internal_action": reversible_internal,
        "blocker": blocker,
        "reason": _clean(action.get("reason")) or None,
        "authority": authority,
        "founder_gate_required": founder_gate,
        "waiting_external": waiting_external,
        "evidence_refs": _evidence_refs(action),
        "recommendation_only": True,
        "external_execution_authorized": False,
        "payment_authorized": False,
        "revenue_recognition_authorized": False,
    }


def _sort_key(item: Mapping[str, Any]) -> tuple[int, int, str]:
    # Revenue proximity is descriptive, not predictive: later observed canonical
    # states appear first. Within the same state, internal reversible work comes
    # before waiting/external/gated work.
    depth = int(item.get("commercial_stage_depth") or 0)
    if item.get("next_reversible_internal_action"):
        lane = 0
    elif item.get("founder_gate_required") is True:
        lane = 1
    elif item.get("waiting_external") is True:
        lane = 3
    else:
        lane = 2
    return (-depth, lane, _clean(item.get("company_name")).casefold())


def build_revenue_command_queue(
    *,
    next_best_actions: Mapping[str, Any],
    commercial_funnel: Mapping[str, Any],
    revenue_pulse: Mapping[str, Any],
) -> dict[str, Any]:
    actions = next_best_actions.get("actions")
    action_rows = actions if isinstance(actions, list) else []

    items = [
        _queue_item(row)
        for row in action_rows
        if isinstance(row, Mapping)
    ]
    items.sort(key=_sort_key)

    system_blocker = (
        _clean(revenue_pulse.get("highest_priority_blocker"))
        or _clean(commercial_funnel.get("next_event"))
        or None
    )

    current_stage = (
        _clean(commercial_funnel.get("current_stage"))
        or "unknown"
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "source_of_truth": {
            "next_best_action": "canonical_runtime_projection",
            "commercial_funnel": "canonical_runtime_projection",
            "revenue_pulse": "canonical_runtime_projection",
        },
        "current_commercial_stage": current_stage,
        "highest_priority_blocker": system_blocker,
        "recognized_revenue_cents": (
            revenue_pulse.get("recognized_revenue_truth", {})
            .get("recognized_revenue_cents")
            if isinstance(
                revenue_pulse.get("recognized_revenue_truth"),
                Mapping,
            )
            else None
        ),
        "realized_gp_cents": (
            revenue_pulse.get("recognized_revenue_truth", {})
            .get("realized_gp_cents")
            if isinstance(
                revenue_pulse.get("recognized_revenue_truth"),
                Mapping,
            )
            else None
        ),
        "item_count": len(items),
        "reversible_internal_count": sum(
            item["next_reversible_internal_action"] is not None
            for item in items
        ),
        "founder_gate_count": sum(
            item["founder_gate_required"] is True
            for item in items
        ),
        "waiting_external_count": sum(
            item["waiting_external"] is True
            for item in items
        ),
        "items": items,
        "actual_revenue_inferred": False,
        "forecast_used_as_revenue_truth": False,
        "external_execution_authorized": False,
        "payment_authorized": False,
        "database_mutation_authorized": False,
        "unknown_stays_unknown": True,
    }


def build_revenue_command_queue_runtime(repo_root: Path) -> dict[str, Any]:
    next_best = build_next_best_action_runtime(repo_root)
    funnel = build_funnel_runtime(repo_root)
    pulse = build_revenue_pulse_runtime(repo_root)

    return {
        "available": (
            next_best.get("available") is True
            or funnel.get("available") is True
            or pulse.get("available") is True
        ),
        **build_revenue_command_queue(
            next_best_actions=next_best,
            commercial_funnel=funnel,
            revenue_pulse=pulse,
        ),
    }
