"""Read-only COO, Business Development and Chief-of-Staff operating review.

Uses the existing EmpireOS company operating model, department registry and
evidence references. Never writes queues, sends email, activates provider
traffic, changes terms, or treats acceptance as earned revenue.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import re
from typing import Any, Mapping, Sequence

from empire_os.company_operating_system import build_founder_brief

SCHEMA_VERSION = "empire.executive.commercial_roles.v1"
MAX_PARTNERS = 250
DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{2,250}[a-z0-9]$")
STATES = frozenset({
    "RESEARCH_ONLY", "CONTACTED", "APPLICATION_ACKNOWLEDGED",
    "PARTNER_ACCEPTED", "HUMAN_REPLY", "PILOT_DISCUSSION", "SUPPRESSED", "HARD_BOUNCE",
})
MARKETS = frozenset({"UK", "USA", "UK_USA", "OTHER"})
NEXT_ACTIONS = {
    "RESEARCH_ONLY": "VERIFY_PRIOR_CONTACT_AND_PARTNER_FIT",
    "CONTACTED": "WAIT_AND_CLASSIFY_NEW_PROVIDER_REPLY",
    "APPLICATION_ACKNOWLEDGED": "OBTAIN_HUMAN_BUYING_BRIEF",
    "PARTNER_ACCEPTED": "RESOLVE_TERMS_SOURCE_CONSENT_AND_SANDBOX",
    "HUMAN_REPLY": "REVIEW_SUBSTANTIVE_REPLY_AND_PROPOSE_FOUNDER_ACTION",
    "PILOT_DISCUSSION": "QUALIFY_NO_UPFRONT_PERFORMANCE_PILOT",
    "SUPPRESSED": "NO_CONTACT",
    "HARD_BOUNCE": "NO_CONTACT",
}


def _required_text(value: Any, label: str, *, limit: int = 250) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f"invalid {label}")
    return value.strip()


def _stamp(value: Any) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("as_of must be timezone aware")
    return value.astimezone(timezone.utc)


def _partner_review(raw: Mapping[str, Any], *, now: datetime) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("partner must be an object")
    domain = _required_text(raw.get("domain"), "domain").lower().removeprefix("www.")
    if (not DOMAIN_RE.fullmatch(domain) or ".." in domain
            or "." not in domain or any(char in domain for char in ("@", "/", ":", " "))) :
        raise ValueError("invalid partner domain")
    name = _required_text(raw.get("name"), "name", limit=160)
    state = raw.get("state")
    market = raw.get("market")
    if state not in STATES or market not in MARKETS:
        raise ValueError("invalid partner state or market")
    refs = raw.get("evidence_refs")
    if (not isinstance(refs, list) or not 1 <= len(refs) <= 12
            or any(not isinstance(ref, str) or not ref.strip() or len(ref) > 300
                   for ref in refs)):
        raise ValueError("partner evidence required")
    for boolean_field in (
        "contact_history_verified", "suppressed", "paid_revenue_verified"
    ):
        if type(raw.get(boolean_field)) is not bool:
            raise ValueError(f"{boolean_field} must be explicit boolean")
    stamp_raw = raw.get("last_touch_at")
    stamp = None
    if stamp_raw is not None:
        if not isinstance(stamp_raw, str):
            raise ValueError("invalid last touch")
        try:
            stamp = datetime.fromisoformat(stamp_raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid last touch") from exc
        if stamp.tzinfo is None or stamp.utcoffset() is None or stamp.astimezone(timezone.utc) > now:
            raise ValueError("future or naive last touch")
    date_raw = raw.get("last_touch_date")
    touched_date = None
    if date_raw is not None:
        if not isinstance(date_raw, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date_raw):
            raise ValueError("invalid last touch date")
        try:
            touched_date = date.fromisoformat(date_raw)
        except ValueError as exc:
            raise ValueError("invalid last touch date") from exc
        if touched_date > now.date():
            raise ValueError("future last touch date")
    if stamp and touched_date and stamp.date() != touched_date:
        raise ValueError("conflicting last touch times")
    if state in {"CONTACTED", "APPLICATION_ACKNOWLEDGED", "PARTNER_ACCEPTED", "HUMAN_REPLY", "PILOT_DISCUSSION"} and not (stamp or touched_date):
        raise ValueError("contact state requires dated evidence")
    if state in {"SUPPRESSED", "HARD_BOUNCE"} and not raw["suppressed"]:
        raise ValueError("suppression state must be enforced")
    if raw["paid_revenue_verified"] and state in {"RESEARCH_ONLY", "CONTACTED", "APPLICATION_ACKNOWLEDGED"}:
        raise ValueError("unsubstantiated financial state")
    suppressed = raw["suppressed"] or state in {"SUPPRESSED", "HARD_BOUNCE"}
    action = "NO_CONTACT" if suppressed else NEXT_ACTIONS[state]
    if not suppressed and not raw["contact_history_verified"]:
        # A new research candidate is NOT fresh until cross-mailbox review.
        action = "RECONCILE_MAILBOX_AND_CRM_BEFORE_ANY_OUTREACH"
    return {
        "partner": name,
        "domain": domain,
        "market": market,
        "relationship_state": state,
        "contact_history_verified": raw["contact_history_verified"],
        "last_touch_at": stamp.astimezone(timezone.utc).isoformat() if stamp else None,
        "last_touch_date": touched_date.isoformat() if touched_date else (
            stamp.astimezone(timezone.utc).date().isoformat() if stamp else None
        ),
        "evidence_refs": list(refs),
        "owner": "business_development",
        "next_action": action,
        "founder_outreach_approval_required": action != "NO_CONTACT",
        "contact_allowed": False,
        "status": "SUPPRESSED" if suppressed else (
            "RESEARCH_HOLD" if not raw["contact_history_verified"] else "REVIEW_ONLY"
        ),
        "partner_acceptance_not_revenue": True,
        # Financial claims require independent canonical revenue evidence,
        # which this planning-only agent deliberately cannot admit.
        "paid_revenue_claim": "NOT_ASSESSED_IN_THIS_LANE",
    }


def review_executive_commercial_roles(
    partners: Sequence[Mapping[str, Any]],
    operations: Mapping[str, Any],
    *, as_of: datetime,
) -> dict[str, Any]:
    """Generate accountable role-specific internal review tasks, not executions."""
    now = _stamp(as_of)
    if not isinstance(partners, (list, tuple)) or len(partners) > MAX_PARTNERS:
        raise ValueError("unbounded partner portfolio")
    if not isinstance(operations, Mapping):
        raise ValueError("operations evidence required")
    health = operations.get("department_cycle_status")
    if health not in {"SUCCEEDED", "FAILED", "UNKNOWN"}:
        raise ValueError("department_cycle_status must be independently observed")
    astra = operations.get("astra_dispatcher_status")
    if astra not in {"SUCCEEDED", "FAILED", "UNKNOWN"}:
        raise ValueError("astra_dispatcher_status must be independently observed")
    attention = operations.get("founder_attention_items")
    if isinstance(attention, bool) or not isinstance(attention, int) or attention < 0:
        raise ValueError("invalid attention count")
    if type(operations.get("founder_notifications_sent")) is not bool:
        raise ValueError("explicit founder notification evidence required")
    notification_evidence = operations.get("founder_notification_evidence", "VERIFIED")
    if notification_evidence not in {"VERIFIED", "UNKNOWN"}:
        raise ValueError("invalid founder notification evidence state")
    failure = operations.get("department_cycle_failure_reason")
    if health == "FAILED":
        failure = _required_text(failure, "department cycle failure reason", limit=500)
    elif failure:
        raise ValueError("inconsistent healthy department cycle evidence")
    proof_state = operations.get("opportunities_source_proof_state", "UNKNOWN")
    if proof_state not in {"FRESH", "STALE", "MISSING", "UNTRUSTED", "UNKNOWN"}:
        raise ValueError("invalid opportunities source proof state")
    mailbox_state = operations.get("mailbox_observer_state", "UNKNOWN")
    if mailbox_state not in {"HEALTHY", "PROVIDER_ONLY", "ERROR", "STALE", "MISSING", "UNKNOWN"}:
        raise ValueError("invalid mailbox observer state")
    snapshot_state = operations.get("partner_snapshot_state", "HISTORICAL_ONLY")
    if snapshot_state not in {"CURRENT_REVIEW", "HISTORICAL_ONLY", "STALE_REVIEW", "MISSING"}:
        raise ValueError("invalid partner snapshot state")
    health_refs = operations.get("evidence_refs")
    if not isinstance(health_refs, list) or not health_refs or any(
        not isinstance(ref, str) or not ref.strip() for ref in health_refs
    ):
        raise ValueError("operations evidence references required")

    cases = [_partner_review(row, now=now) for row in partners]
    seen: set[str] = set()
    for case in cases:
        if case["domain"] in seen:
            raise ValueError("duplicate domain across partner portfolio")
        seen.add(case["domain"])
    cases.sort(key=lambda row: (row["market"], row["domain"]))

    ops_actions = []
    chief_actions = []
    if proof_state in {"STALE", "MISSING", "UNTRUSTED"}:
        ops_actions.append({
            "owner": "coo",
            "delegated_to": "engineering",
            "priority": "P0_SOURCE_PROOF_REVIEW",
            "action": "RESTORE_FRESH_OPPORTUNITY_SOURCE_PROOF",
            "reason": f"opportunities_source_proof_state={proof_state}",
            "evidence_refs": list(health_refs),
            "required_proof": "FRESH_SAME_LANE_OPPORTUNITY_SOURCE_PLUS_SUCCESSFUL_FINALISER",
            "bypass_guard_allowed": False,
            "production_activation_allowed": False,
        })
    if mailbox_state in {"ERROR", "STALE", "MISSING"}:
        ops_actions.append({
            "owner": "coo",
            "delegated_to": "engineering",
            "priority": "P1_MAILBOX_EVIDENCE_RESTORATION",
            "action": "RESTORE_FOUNDER_MAILBOX_READ_OBSERVABILITY",
            "reason": f"mailbox_observer_state={mailbox_state}",
            "evidence_refs": list(health_refs),
            "required_proof": "VALID_NEW_READ_SNAPSHOT_FROM_APPROVED_PROVIDER",
            "unauthorized_mail_read_or_send_allowed": False,
            "production_activation_allowed": False,
        })
    if mailbox_state == "PROVIDER_ONLY":
        ops_actions.append({
            "owner": "coo",
            "delegated_to": "engineering",
            "priority": "P1_CANONICAL_REPLY_IDENTITY_REVIEW",
            "action": "VERIFY_CANONICAL_REPLY_IDENTITY_AND_SUPPRESSION",
            "reason": "Founder mailbox provider read works; complete original-message-to-person proof absent",
            "evidence_refs": list(health_refs),
            "required_proof": "ORIGINAL_PROVIDER_MESSAGE_PLUS_PERSON_THREAD_AND_SUPPRESSION_EVIDENCE",
            "unauthorized_mail_read_or_send_allowed": False,
            "production_activation_allowed": False,
        })
    if health == "FAILED":
        ops_actions.append({
            "owner": "coo",
            "delegated_to": "engineering",
            "priority": "P0_RUNTIME_REPAIR_REVIEW",
            "action": "RESTORE_VERIFIED_DEPARTMENT_FINALISATION",
            "reason": failure,
            "evidence_refs": list(health_refs),
            "required_proof": "FRESH_SAME_LANE_OPPORTUNITY_SOURCE_PLUS_SUCCESSFUL_FINALISER",
            "bypass_guard_allowed": False,
            "production_activation_allowed": False,
        })
    if astra != "SUCCEEDED":
        ops_actions.append({
            "owner": "coo", "delegated_to": "engineering",
            "priority": "P1_RUNTIME_VERIFY",
            "action": "VERIFY_ASTRA_DISPATCHER",
            "reason": "Current Astra health not proven",
            "evidence_refs": list(health_refs),
            "production_activation_allowed": False,
        })
    if attention:
        ops_actions.append({
            "owner": "coo",
            "delegated_to": "chief_of_staff",
            "priority": "P1_BACKLOG_TRIAGE",
            "action": "DEDUPLICATE_AND_TRIAGE_FOUNDER_ATTENTION",
            "unresolved_attention_rows": attention,
            "unique_business_blocker_count": None,
            "reason": "Attention rows are not necessarily unique business blockers",
            "evidence_refs": list(health_refs),
            "production_activation_allowed": False,
        })
    if notification_evidence == "VERIFIED" and not operations["founder_notifications_sent"]:
        chief_actions.append({
            "owner": "chief_of_staff",
            "priority": "P1_BRIEF_COVERAGE",
            "action": "PREPARE_FOUNDER_PRIORITY_AND_BLOCKER_BRIEF",
            "reason": "Completion task monitor reports no notifications (not all channels)",
            "evidence_refs": list(health_refs),
            "notification_scope": "completion_task_monitor_only",
            "notifications_sent": False,
        })
    elif notification_evidence == "UNKNOWN":
        chief_actions.append({
            "owner": "chief_of_staff",
            "priority": "P1_BRIEF_COVERAGE_REVIEW",
            "action": "VERIFY_FOUNDER_NOTIFICATION_EVIDENCE",
            "reason": "Notification coverage not established from current source",
            "evidence_refs": list(health_refs),
        })

    decision_risks = []
    if health == "FAILED":
        decision_risks.append({
            "risk_id": "department_finalisation_failed",
            "severity": "high",
            "summary": failure,
            "evidence_refs": list(health_refs),
        })
    manual_partner_review = sum(
        case["next_action"] not in {"NO_CONTACT", "WAIT_AND_CLASSIFY_NEW_PROVIDER_REPLY"}
        for case in cases
    )
    founder_brief = build_founder_brief(
        date=now.date().isoformat(),
        verified_outcomes=[],
        initiatives=[],
        decisions_needed=[],
        risks=decision_risks,
    )
    # Deterministic *review order*, not a fabricated commercial ROI score.
    # Never convert this ordering into an instruction to send or spend.
    founder_next_actions: list[dict[str, Any]] = []
    if health == "FAILED" or proof_state in {"STALE", "MISSING", "UNTRUSTED"}:
        founder_next_actions.append({
            "owner": "coo",
            "action": "RESTORE_VERIFIED_DEPARTMENT_FINALISATION",
            "reason": "Observed department cycle finalization failure",
            "evidence_refs": list(health_refs),
            "external_action_authorized": False,
        })
    if snapshot_state in {"MISSING", "STALE_REVIEW"}:
        founder_next_actions.append({
            "owner": "business_development",
            "action": "REVALIDATE_CURRENT_PARTNER_EVIDENCE",
            "reason": f"partner_snapshot_state={snapshot_state}",
            "evidence_refs": list(health_refs),
            "external_action_authorized": False,
        })
    ordering = {
        "PILOT_DISCUSSION": 0,
        "HUMAN_REPLY": 1,
        "PARTNER_ACCEPTED": 2,
        "APPLICATION_ACKNOWLEDGED": 3,
        "CONTACTED": 4,
        "RESEARCH_ONLY": 5,
    }
    for case in sorted(cases, key=lambda c: (
        ordering.get(c["relationship_state"], 99), c["domain"]
    )):
        # Historical portfolios are retained for deduplication and audit,
        # but expired evidence cannot generate current founder priorities.
        if snapshot_state in {"STALE_REVIEW", "MISSING"}:
            break
        if case["next_action"] == "NO_CONTACT":
            continue
        founder_next_actions.append({
            "owner": "business_development",
            "partner": case["partner"],
            "action": case["next_action"],
            "reason": "Evidence-backed partner relationship state",
            "evidence_refs": list(case["evidence_refs"]),
            "external_action_authorized": False,
        })
    if attention and len(founder_next_actions) < 3:
        founder_next_actions.append({
            "owner": "coo",
            "action": "DEDUPLICATE_AND_TRIAGE_FOUNDER_ATTENTION",
            "reason": "Attention records are not unique issues",
            "evidence_refs": list(health_refs),
            "external_action_authorized": False,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "mode": "OBSERVE",
        "execution_authority": "none",
        "chief_of_staff": {
            "role": "chief_of_staff", "department": "strategy",
            "founder_brief": founder_brief,
            "coordination_mandate": [
                "Protect founder focus: top three commercial and operational issues",
                "Check COO incident proof and Business Development partner progress",
                "Escalate approvals once with evidence; do not duplicate requests",
            ],
            "operation_has_unresolved_incident": health == "FAILED",
            "partner_items_needing_review": manual_partner_review,
            "tasks": chief_actions,
            "top_three_next_actions": founder_next_actions[:3],
            "prioritization_method": "fixed_evidence_review_order_not_roi_prediction",
        },
        "coo": {
            "role": "coo", "department": "strategy",
            "tasks": ops_actions,
            "department_cycle_status": health,
            "astra_dispatcher_status": astra,
            "opportunities_source_proof_state": proof_state,
            "mailbox_observer_state": mailbox_state,
            "partner_snapshot_state": snapshot_state,
            "founder_notification_evidence": notification_evidence,
            "operational_claim": "PARTIAL_OR_BLOCKED" if (health != "SUCCEEDED" or astra != "SUCCEEDED")
                                 else "REVIEWED_HEALTH_EVIDENCE",
        },
        "business_development": {
            "role": "business_development", "department": "sales_revenue",
            "partner_cases": cases,
            "source_evidence_status": snapshot_state,
            "live_mailbox_evidence_status": mailbox_state,
            "no_new_reply_claim_authorized": False,
            "source_tasks": ([{
                "owner": "business_development",
                "action": "REVALIDATE_CURRENT_PARTNER_EVIDENCE",
                "reason": f"partner_snapshot_state={snapshot_state}",
                "evidence_refs": list(health_refs),
                "external_action_authorized": False,
            }] if snapshot_state in {"MISSING", "STALE_REVIEW"} else []),
            "fresh_verified_uncontacted_count": sum(
                case["relationship_state"] == "RESEARCH_ONLY"
                and case["contact_history_verified"]
                and case["status"] != "SUPPRESSED"
                for case in cases
            ),
            "emails_sent": 0,
            "contacts_created": 0,
            "buyer_approval_implied": False,
            "commercial_revenue_implied": False,
        },
        "db_writes": False,
        "outbound_enabled": False,
        "email_sent": False,
        "commercial_terms_accepted": False,
        "funds_moved": False,
        "production_changed": False,
    }
