"""Evidence-first decision control for the existing EmpireOS Founder Console.

Fuses the canonical Revenue Command Queue and the validated ASTRA executive
observer into one deduplicated, freshness-checked priority view. It does NOT
dispatch work, contact customers, alter databases, approve terms, or move money.
A decision can be prepared without being authorised to execute.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.buyer_capacity_action_brief import build_buyer_capacity_action_brief
from empire_os.executive_founder_status import read_executive_founder_status
from empire_os.next_best_action import build_next_best_action_runtime
from empire_os.revenue_command_queue import build_revenue_command_queue_runtime
from empire_os.revenue_pulse import build_revenue_pulse_runtime

SCHEMA_VERSION = "empire.predictive_decision_control.v1"
ACTION_SNAPSHOT_MAX_AGE = timedelta(hours=6)
REVENUE_PULSE_MAX_AGE = timedelta(hours=6)
MAX_ITEMS = 500
# Explicit, bounded set of existing NBA actions; a novel label cannot silently
# acquire an internal-preparation privilege.
ACTION_POLICY = {
    "fulfilment_review": ("fulfilment", "REVIEW_REQUIRED", 94),
    "payment_review": ("finance", "FOUNDER_DECISION", 87),
    "terms_candidate": ("sales", "FOUNDER_DECISION", 83),
    "conversation_follow_up": ("crm", "GOVERNED_EXTERNAL", 76),
    "prepare_buyer_review": ("sales", "INTERNAL_PREPARATION", 64),
    "verify_decision_maker": ("sales_research", "INTERNAL_PREPARATION", 60),
    "research_more": ("sales_research", "INTERNAL_PREPARATION", 46),
    "enrich_identity": ("sales_research", "INTERNAL_PREPARATION", 42),
    "hold": ("operations", "WAITING_EXTERNAL", 12),
}
STAGE_DEPTH = {
    "DISCOVERED": 1, "ICP_MATCH": 2, "SIGNAL_ACTIVE": 2, "RESEARCHED": 3,
    "READY": 4, "CONTACTED": 5, "ENGAGED": 6, "CONVERSATION": 7,
    "COMMERCIAL_INTENT": 8, "TERMS": 9, "PAYMENT_PENDING": 10,
    "PAID": 11, "FULFILLED": 12, "EXPANSION": 13,
}
EXECUTIVE_POLICY = {
    "RESTORE_VERIFIED_DEPARTMENT_FINALISATION": ("operations", 82),
    "RESTORE_FRESH_OPPORTUNITY_SOURCE_PROOF": ("revenue_operations", 80),
    "RESTORE_FOUNDER_MAILBOX_READ_OBSERVABILITY": ("crm", 78),
    "DEDUPLICATE_AND_TRIAGE_FOUNDER_ATTENTION": ("chief_of_staff", 62),
    "PREPARE_FOUNDER_PRIORITY_AND_BLOCKER_BRIEF": ("chief_of_staff", 58),
    "VERIFY_FOUNDER_NOTIFICATION_EVIDENCE": ("chief_of_staff", 54),
    "VERIFY_ASTRA_DISPATCHER": ("operations", 77),
    "REVALIDATE_CURRENT_PARTNER_EVIDENCE": ("sales", 66),
    "OBTAIN_HUMAN_BUYING_BRIEF": ("sales", 72),
    "RESOLVE_TERMS_SOURCE_CONSENT_AND_SANDBOX": ("sales", 69),
    "WAIT_AND_CLASSIFY_NEW_PROVIDER_REPLY": ("crm", 52),
    "RECONCILE_MAILBOX_AND_CRM_BEFORE_ANY_OUTREACH": ("crm", 74),
    "VERIFY_PRIOR_CONTACT_AND_PARTNER_FIT": ("sales", 66),
    "REVIEW_SUBSTANTIVE_REPLY_AND_PROPOSE_FOUNDER_ACTION": ("crm", 78),
    "QUALIFY_NO_UPFRONT_PERFORMANCE_PILOT": ("sales", 70),
    "VERIFY_DOWNSTREAM_BUYER_TERMS_CAPACITY": ("business_development", 98),
}


def _stamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except (ValueError, OverflowError, TypeError):
        return None


def _clean(value: Any, limit: int = 240) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _key(*parts: str) -> str:
    data = "\x1f".join(parts).encode("utf-8")
    return sha256(data).hexdigest()[:20]


def _snapshot_status(
    snapshot: Mapping[str, Any],
    *,
    as_of: datetime,
) -> str:
    if not snapshot.get("available"):
        return "MISSING"
    if (snapshot.get("schema_version") != "empire.next_best_action_snapshot.v1"
            or snapshot.get("mode") != "OBSERVE"
            or snapshot.get("execution_authority") != "none"
            or snapshot.get("outreach_authorized") is not False
            or snapshot.get("payment_authorized") is not False
            or not isinstance(snapshot.get("actions"), list)):
        return "UNTRUSTED"
    stamp = _stamp(snapshot.get("generated_at"))
    if stamp is None:
        return "UNTRUSTED"
    delta = as_of - stamp
    if delta < timedelta(0):
        return "FUTURE_HELD"
    if delta > ACTION_SNAPSHOT_MAX_AGE:
        return "STALE"
    return "FRESH"


def _trusted_queue(queue: Mapping[str, Any]) -> bool:
    return (queue.get("schema_version") == "empire.revenue_command_queue.v1"
            and queue.get("mode") == "OBSERVE"
            and queue.get("execution_authority") == "none"
            and queue.get("payment_authorized") is False
            and queue.get("external_execution_authorized") is False
            and queue.get("database_mutation_authorized") is False
            and isinstance(queue.get("items"), list))


def _buyer_task(
    item: Mapping[str, Any],
    *,
    source_status: str,
    canonical_signatures: set[tuple[str, str, str, str]],
) -> dict[str, Any]:
    entity = _clean(item.get("entity_id"), 128)
    prospect = _clean(item.get("prospect_id"), 128)
    action = _clean(item.get("recommended_action"), 100)
    state = _clean(item.get("current_commercial_state"), 48)
    policy = ACTION_POLICY.get(action)
    authority = item.get("authority")
    founder_gate = item.get("founder_gate_required") is True
    waiting = item.get("waiting_external") is True
    refs = item.get("evidence_refs")
    references = sorted({
        _clean(v, 250) for v in (refs if isinstance(refs, list) else [])
        if _clean(v, 250)
    })[:24]

    # The queue's internal-work field is only a descriptive suggestion, never
    # an execution grant; exact action and authority must agree.
    internal_ready = (
        bool(entity or prospect)
        and source_status == "FRESH"
        and policy is not None
        and policy[1] == "INTERNAL_PREPARATION"
        and authority == "internal_write"
        and item.get("next_reversible_internal_action") == action
        and not founder_gate and not waiting
        and item.get("external_execution_authorized") is False
        and item.get("payment_authorized") is False
    )

    if not (entity or prospect) or not references:
        lane = "EVIDENCE_HOLD"
        reason = "missing_canonical_identity_or_evidence_reference"
    elif source_status != "FRESH":
        lane = "EVIDENCE_HOLD"
        reason = f"buyer_snapshot_{source_status.lower()}"
    elif (entity, prospect, action, state) not in canonical_signatures:
        lane = "EVIDENCE_HOLD"
        reason = "revenue_queue_does_not_match_canonical_nba_snapshot"
    elif policy is None:
        lane = "EVIDENCE_HOLD"
        reason = "action_not_in_review_policy"
    elif action == "hold" and waiting and authority == "observe":
        lane = "WAITING_EXTERNAL"
        reason = "waiting_for_real_external_evidence"
    elif action == "hold":
        lane = "EVIDENCE_HOLD"
        reason = "no_stronger_action_supported"
    elif founder_gate or authority == "founder_gate":
        lane = ("FOUNDER_DECISION" if founder_gate
                and authority == "founder_gate"
                and policy[1] == "FOUNDER_DECISION"
                else "EVIDENCE_HOLD")
        reason = ("founder_gate_required" if lane == "FOUNDER_DECISION"
                  else "inconsistent_founder_gate")
    elif internal_ready:
        lane = "INTERNAL_PREPARATION"
        reason = "internal_review_candidate_not_dispatch_authority"
    elif policy[1] in ("GOVERNED_EXTERNAL", "REVIEW_REQUIRED") and (
        authority == "governed_external" and not waiting
    ):
        lane = "GOVERNED_REVIEW"
        reason = "human_or_existing_governor_review_required"
    else:
        lane = "EVIDENCE_HOLD"
        reason = "authority_or_evidence_mismatch"

    # Triage weights are ordering aids, NOT calibrated probabilities or money.
    score = min(100, (policy[2] if policy else 10)
                + min(6, STAGE_DEPTH.get(state, 0) // 2))
    if lane == "WAITING_EXTERNAL":
        score = max(0, score - 25)
    if lane == "EVIDENCE_HOLD":
        score = max(0, score - 45)

    return {
        "task_id": "buyer-" + _key(entity, prospect, action),
        "source": "canonical_revenue_command_queue",
        "entity_id": entity or None,
        "prospect_id": prospect or None,
        "company_name": _clean(item.get("company_name"), 140) or None,
        "department": policy[0] if policy else "operations",
        "recommended_action": action or "hold",
        "current_commercial_state": state or "UNKNOWN",
        "lane": lane,
        "triage_rank": score,
        "triage_rank_is_revenue_forecast": False,
        "reason": _clean(item.get("reason"), 500) or reason,
        "hold_or_gate_reason": reason,
        "existing_blocker": _clean(item.get("blocker"), 180) or None,
        "evidence_refs": references,
        "source_freshness": source_status,
        "can_prepare_internal_work": internal_ready and lane == "INTERNAL_PREPARATION",
        "can_execute": False,
        "execution_authority": "none",
        "founder_gate_required": founder_gate,
        "waiting_external": waiting,
        "measured_revenue_impact_cents": None,
        "predicted_revenue_impact_cents": None,
    }


def _executive_tasks(executive: Mapping[str, Any]) -> list[dict[str, Any]]:
    if (executive.get("available") is not True
            or executive.get("schema_version") != "empire.founder.executive_roles_status.v1"
            or executive.get("mode") != "OBSERVE"
            or executive.get("execution_authority") != "none"):
        return []
    chief = executive.get("chief_of_staff", {})
    actions = chief.get("top_three_review_actions") if isinstance(chief, Mapping) else None
    signals: list[dict[str, Any]] = []
    coo = executive.get("coo")
    if isinstance(coo, Mapping):
        signals.extend(
            {"owner": "coo", "action": action,
             "external_action_authorized": False, "observed_signal": key}
            for key, expected, action in (
                ("department_cycle", "FAILED", "RESTORE_VERIFIED_DEPARTMENT_FINALISATION"),
                ("astra_dispatcher", "FAILED", "VERIFY_ASTRA_DISPATCHER"),
                ("opportunity_proof", "STALE", "RESTORE_FRESH_OPPORTUNITY_SOURCE_PROOF"),
                ("opportunity_proof", "MISSING", "RESTORE_FRESH_OPPORTUNITY_SOURCE_PROOF"),
                ("mailbox_observer", "ERROR", "RESTORE_FOUNDER_MAILBOX_READ_OBSERVABILITY"),
                ("mailbox_observer", "STALE", "RESTORE_FOUNDER_MAILBOX_READ_OBSERVABILITY"),
            )
            if coo.get(key) == expected
        )
    business = executive.get("business_development")
    if isinstance(business, Mapping):
        capacity = business.get("downstream_buyer_capacity")
        if (isinstance(capacity, Mapping)
                and capacity.get("status") == "NO_VERIFIED_COMMERCIAL_CAPACITY"
                and capacity.get("specific_buybox_verified") is False):
            signals.append({
                "owner": "business_development",
                "action": "VERIFY_DOWNSTREAM_BUYER_TERMS_CAPACITY",
                "external_action_authorized": False,
                "observed_signal": "NO_VERIFIED_COMMERCIAL_CAPACITY",
            })
    tasks: list[dict[str, Any]] = []
    rows = (actions if isinstance(actions, list) else [])[:3]
    for row in [*signals, *rows]:
        if not isinstance(row, Mapping):
            continue
        action = _clean(row.get("action"), 120)
        owner = _clean(row.get("owner"), 70)
        if (action not in EXECUTIVE_POLICY
                or owner not in ("coo", "business_development", "chief_of_staff")
                or row.get("external_action_authorized") is not False):
            continue
        department, score = EXECUTIVE_POLICY[action]
        partner = _clean(row.get("partner"), 120)
        tasks.append({
            "task_id": "executive-" + _key(owner, action, partner),
            "source": "validated_astra_executive_observer",
            "entity_id": None,
            "prospect_id": None,
            "company_name": partner or None,
            "department": department,
            "recommended_action": action,
            "current_commercial_state": "UNKNOWN",
            "lane": "INTERNAL_REVIEW",
            "triage_rank": score,
            "triage_rank_is_revenue_forecast": False,
            "reason": ("observed executive blocker: " + row["observed_signal"]
                       if row.get("observed_signal") else
                       "validated executive observer surfaced this review"),
            "hold_or_gate_reason": "review_only",
            "existing_blocker": None,
            "evidence_refs": ["astra:executive_latest"],
            "source_freshness": "FRESH",
            "can_prepare_internal_work": False,
            "can_execute": False,
            "execution_authority": "none",
            "founder_gate_required": False,
            "waiting_external": False,
            "measured_revenue_impact_cents": None,
            "predicted_revenue_impact_cents": None,
        })
    return tasks


def build_predictive_decision_control(
    *,
    queue: Mapping[str, Any],
    next_best: Mapping[str, Any],
    executive: Mapping[str, Any],
    revenue_pulse: Mapping[str, Any] | None = None,
    as_of: datetime | None = None,
    max_items: int = MAX_ITEMS,
) -> dict[str, Any]:
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    now = now.astimezone(timezone.utc)
    if type(max_items) is not int or max_items < 1 or max_items > MAX_ITEMS:
        raise ValueError("max_items outside bounded range")

    freshness = _snapshot_status(next_best, as_of=now)
    queue_trusted = _trusted_queue(queue)
    canonical_signatures = {
        (_clean(row.get("entity_id"), 128), _clean(row.get("prospect_id"), 128),
         _clean(row.get("recommended_action"), 100),
         _clean(row.get("current_factual_state"), 48))
        for row in next_best.get("actions", [])[:MAX_ITEMS * 4]
        if isinstance(row, Mapping)
    } if freshness == "FRESH" else set()
    items: list[dict[str, Any]] = []
    if queue_trusted:
        items = [
            _buyer_task(row, source_status=freshness,
                        canonical_signatures=canonical_signatures)
            for row in queue["items"][:MAX_ITEMS * 4]
            if isinstance(row, Mapping)
        ]
    items.extend(_executive_tasks(executive))
    # A single entity with contradictory next actions must never be assigned
    # competing live priorities. Hold both until canonical evidence reconciles.
    actions_by_identity: dict[str, set[str]] = {}
    for item in items:
        if item["source"] != "canonical_revenue_command_queue":
            continue
        ident = item["entity_id"] or item["prospect_id"]
        if ident:
            actions_by_identity.setdefault(ident, set()).add(item["recommended_action"])
    for item in items:
        ident = item["entity_id"] or item["prospect_id"]
        if (item["source"] == "canonical_revenue_command_queue"
                and ident and len(actions_by_identity.get(ident, ())) > 1):
            item.update(lane="EVIDENCE_HOLD", can_prepare_internal_work=False,
                        hold_or_gate_reason="conflicting_actions_for_entity",
                        triage_rank=0)

    unique: dict[str, dict[str, Any]] = {}
    for item in items:
        unique.setdefault(item["task_id"], item)
    ordered = sorted(
        unique.values(),
        key=lambda row: (-row["triage_rank"], row["lane"],
                         row["task_id"]),
    )
    count_before_cap = len(ordered)
    ordered = ordered[:max_items]

    lanes = Counter(item["lane"] for item in ordered)
    departments = Counter(item["department"] for item in ordered)
    executive_available = (executive.get("available") is True and
                           executive.get("schema_version") ==
                           "empire.founder.executive_roles_status.v1")
    pulse = revenue_pulse if isinstance(revenue_pulse, Mapping) else {}
    truth = pulse.get("recognized_revenue_truth")
    pulse_stamp = _stamp(pulse.get("generated_at"))
    pulse_contract = (
        pulse.get("schema_version") == "empire.revenue-pulse.v3"
        and pulse.get("mode") == "OBSERVE"
        and pulse.get("execution_authority") == "none"
        and pulse.get("execution_allowed") is False
        and pulse.get("payment_mutation") is False
        and pulse.get("revenue_mutation") is False
        and pulse.get("accounting_mutation") is False
        and isinstance(truth, Mapping)
        and truth.get("forecast_included_in_truth") is False
    )
    if pulse.get("available") is not True:
        pulse_status = "UNAVAILABLE"
    elif not pulse_contract or pulse_stamp is None:
        pulse_status = "UNTRUSTED"
    elif pulse_stamp > now:
        pulse_status = "FUTURE_HELD"
    elif now - pulse_stamp > REVENUE_PULSE_MAX_AGE:
        pulse_status = "STALE"
    else:
        pulse_status = "FRESH"
    pulse_trusted = pulse_status == "FRESH"
    sources = {
        "buyer_next_best_action": freshness,
        "revenue_command_queue": "TRUSTED" if queue_trusted else "UNTRUSTED",
        "revenue_pulse": pulse_status,
        "astra_executive_observer": (
            "FRESH" if executive_available and
            executive.get("execution_authority") == "none" else "UNAVAILABLE"
        ),
    }

    # The reported revenue amount is strictly canonical recognized revenue.
    # An absent value stays null; portfolio/pipeline forecasts are never used.
    recognized = (truth.get("recognized_revenue_cents") if pulse_trusted
                  and queue_trusted and isinstance(truth, Mapping)
                  and queue.get("recognized_revenue_cents") ==
                  truth.get("recognized_revenue_cents") else None)
    if type(recognized) is not int or recognized < 0:
        recognized = None
    realized_gp = (truth.get("realized_gp_cents") if pulse_trusted
                   and queue_trusted and isinstance(truth, Mapping)
                   and queue.get("realized_gp_cents") == truth.get("realized_gp_cents")
                   else None)
    if type(realized_gp) is not int:
        realized_gp = None
    status = ("REVIEW_READY" if any(
        row["lane"] != "EVIDENCE_HOLD" for row in ordered
    ) else "EVIDENCE_HOLD")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "status": status,
        "mode": "OBSERVE",
        "source_of_truth": "existing_canonical_empireos_projections",
        "sources": sources,
        "priority_count": len(ordered),
        "total_before_display_cap": count_before_cap,
        "truncated_count": max(0, count_before_cap - len(ordered)),
        "lane_counts": dict(sorted(lanes.items())),
        "department_counts": dict(sorted(departments.items())),
        "top_three": ordered[:3],
        "founder_decisions": [r for r in ordered if r["lane"] == "FOUNDER_DECISION"],
        "internal_preparation": [
            r for r in ordered if r["lane"] == "INTERNAL_PREPARATION"
        ],
        "items": ordered,
        "recognized_revenue_cents": recognized,
        "realized_gp_cents": realized_gp,
        "revenue_truth_status": pulse_status,
        "north_star": "verified_realized_gross_profit",
        "buyer_capacity_action_brief": build_buyer_capacity_action_brief(executive),
        "estimated_revenue_from_scores": None,
        "expected_revenue_claimed": False,
        "commercial_intent_inferred": False,
        "external_execution_authorized": False,
        "outbound_authorized": False,
        "payment_authorized": False,
        "database_mutation_authorized": False,
        "task_dispatch_performed": False,
        "execution_authority": "none",
        "next_integration": (
            "existing execution bus may consume INTERNAL_PREPARATION candidates "
            "only after its own independent scope, evidence and authority checks"
        ),
    }


def build_predictive_decision_control_runtime(
    repo_root: Path,
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    decision = build_predictive_decision_control(
        queue=build_revenue_command_queue_runtime(root),
        next_best=build_next_best_action_runtime(root),
        executive=read_executive_founder_status(
            root / "runtime/astra/executive_latest.json", as_of=as_of
        ),
        revenue_pulse=build_revenue_pulse_runtime(root),
        as_of=as_of,
    )
    # A read-only view over Astra's existing departmental queue: never queue
    # or claim work simply because a recommended action is ready to prepare.
    from empire_os.predictive_decision_handoff import build_predictive_decision_handoff
    decision["department_handoff"] = build_predictive_decision_handoff(
        decision, root, as_of=as_of,
    )
    # Existing Cloud/Revenue formula producer snapshots; no new forecast,
    # data refresh, provider call or additional commercial authority.
    from empire_os.predictive_formula_evidence_review import review_formula_evidence
    decision["formula_evidence"] = review_formula_evidence(root, as_of=as_of)
    # Mining routes over the existing acquisition/radar/Quant source streams.
    # This is a deterministic read-only report, not a queue dispatch.
    from empire_os.revenue_stream_mining import build_revenue_stream_mining
    decision["data_stream_mining"] = build_revenue_stream_mining(root, as_of=as_of)
    # Scientific reasoning pathways: exact join of existing Radar, Factory,
    # evidence-router and Quant snapshots, with unsupported outcome link held.
    from empire_os.revenue_evidence_pathways import review_evidence_pathways_runtime
    decision["evidence_pathways"] = review_evidence_pathways_runtime(root, as_of=as_of)
    from empire_os.revenue_buyer_evidence_handoff import review_one_commercial_evidence_request
    decision["commercial_evidence_request"] = review_one_commercial_evidence_request(
        root, as_of=as_of or datetime.now(timezone.utc),
    )
    from empire_os.flagship_quality_integrations import flagship_vendor_readiness
    decision["flagship_quality_integrations"] = flagship_vendor_readiness(
        as_of=as_of or datetime.now(timezone.utc),
    )
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only EmpireOS decision priorities")
    parser.add_argument("--repo-root", type=Path, default=Path("/srv/empire_os"))
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.top <= MAX_ITEMS:
        parser.error("--top must be 1 to 500")
    result = build_predictive_decision_control_runtime(args.repo_root)
    result["items"] = result["items"][:args.top]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
