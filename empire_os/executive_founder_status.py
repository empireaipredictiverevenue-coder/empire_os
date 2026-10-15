"""Bounded Founder Console projection of the existing Astra executive review.

Read-only, local evidence only. This is an OBSERVE status, not a live agent,
commercial grant, provider mail access, service health repair, or revenue proof.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "empire.founder.executive_roles_status.v1"
ASTRA_SCHEMA = "empire.astra.executive.v2"
OVERLAY_SCHEMA = "empire.executive.commercial_observer.v1"
DEFAULT_EXECUTIVE = Path("/srv/empire_os/runtime/astra/executive_latest.json")
MAX_BYTES = 1_500_000
MAX_AGE = timedelta(minutes=20)
ROLE_ACTIONS = frozenset({
    "RESTORE_VERIFIED_DEPARTMENT_FINALISATION",
    "RESTORE_FRESH_OPPORTUNITY_SOURCE_PROOF",
    "RESTORE_FOUNDER_MAILBOX_READ_OBSERVABILITY",
    "DEDUPLICATE_AND_TRIAGE_FOUNDER_ATTENTION",
    "PREPARE_FOUNDER_PRIORITY_AND_BLOCKER_BRIEF",
    "VERIFY_FOUNDER_NOTIFICATION_EVIDENCE",
    "VERIFY_ASTRA_DISPATCHER",
    "REVALIDATE_CURRENT_PARTNER_EVIDENCE",
    "OBTAIN_HUMAN_BUYING_BRIEF",
    "RESOLVE_TERMS_SOURCE_CONSENT_AND_SANDBOX",
    "WAIT_AND_CLASSIFY_NEW_PROVIDER_REPLY",
    "RECONCILE_MAILBOX_AND_CRM_BEFORE_ANY_OUTREACH",
    "VERIFY_PRIOR_CONTACT_AND_PARTNER_FIT",
    "REVIEW_SUBSTANTIVE_REPLY_AND_PROPOSE_FOUNDER_ACTION",
    "QUALIFY_NO_UPFRONT_PERFORMANCE_PILOT",
})
ROLES = frozenset({"coo", "business_development", "chief_of_staff"})
REGISTRY_STATES = frozenset({
    "UNAVAILABLE", "INVALID_HELD", "STALE_HELD", "OBSERVE_REVIEW",
    "GMAIL_SNAPSHOT_HOLD",
})
PROOF_STATES = frozenset({"FRESH", "STALE", "MISSING", "UNTRUSTED", "UNKNOWN"})
SERVICE_STATES = frozenset({"SUCCEEDED", "FAILED", "UNKNOWN"})
MAILBOX_STATES = frozenset({"HEALTHY", "PROVIDER_ONLY", "ERROR", "MISSING", "STALE", "UNKNOWN"})


def _stamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return date.astimezone(timezone.utc) if date.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "available": False,
        "status": reason,
        "mode": "OBSERVE",
        "source": "EXISTING_ASTRA_EXECUTIVE_SNAPSHOT",
        "generated_at": None,
        "coo": {
            "department_cycle": "UNKNOWN",
            "astra_dispatcher": "UNKNOWN",
            "opportunity_proof": "UNKNOWN",
            "mailbox_observer": "UNKNOWN",
            "task_count": None,
        },
        "business_development": {
            "relationship_registry_status": "UNAVAILABLE",
            "existing_relationship_count": None,
            "suppression_review_count": None,
            "new_replies_verified": False,
            "mailbox_current": False,
        },
        "chief_of_staff": {
            "top_three_review_actions": [],
            "source": "UNAVAILABLE",
            "notifications_sent_by_this_endpoint": False,
        },
        "production_release_authorized": False,
        "emails_sent": False,
        "lead_delivery_authorized": False,
        "revenue_verified_by_this_status": False,
        "execution_authority": "none",
    }


def read_executive_founder_status(
    source: Path = DEFAULT_EXECUTIVE,
    *, as_of: datetime | None = None,
) -> dict[str, Any]:
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware as_of required")
    now = now.astimezone(timezone.utc)
    path = Path(source)
    try:
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
            return _base("SNAPSHOT_UNAVAILABLE")
        with path.open(encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, UnicodeError, ValueError, TypeError):
        return _base("SNAPSHOT_UNAVAILABLE")
    if not isinstance(data, dict) or data.get("schema_version") != ASTRA_SCHEMA or data.get("mode") != "OBSERVE":
        return _base("SNAPSHOT_UNTRUSTED")
    time = _stamp(data.get("generated_at"))
    if time is None or not timedelta(0) <= now - time <= MAX_AGE:
        return _base("SNAPSHOT_STALE")
    attachment = data.get("executive_commercial_roles")
    if not isinstance(attachment, dict):
        return _base("NOT_ACTIVATED")
    stamp = _stamp(attachment.get("as_of"))
    if (attachment.get("schema_version") != OVERLAY_SCHEMA
            or attachment.get("mode") != "OBSERVE"
            or attachment.get("execution_authority") != "none"
            or attachment.get("outbound_enabled") is not False
            or attachment.get("production_changes") is not False
            or stamp is None or not timedelta(0) <= now - stamp <= MAX_AGE
            or abs((stamp - time).total_seconds()) > 120):
        return _base("OVERLAY_UNTRUSTED")
    ops = attachment.get("observed_systemd")
    proof = attachment.get("opportunity_proof")
    mailbox = attachment.get("founder_mailbox_observer")
    reg = attachment.get("existing_relationship_registry")
    review = attachment.get("review")
    if not all(isinstance(x, dict) for x in (ops, proof, mailbox, reg)):
        return _base("OVERLAY_UNTRUSTED")
    cycle, dispatcher = ops.get("department_cycle"), ops.get("astra_dispatcher")
    proof_state, mailbox_state = proof.get("status"), mailbox.get("status")
    if (cycle not in SERVICE_STATES or dispatcher not in SERVICE_STATES
            or proof_state not in PROOF_STATES or mailbox_state not in MAILBOX_STATES
            or reg.get("status") not in REGISTRY_STATES):
        return _base("OVERLAY_UNTRUSTED")

    summary = _base("EVIDENCE_HOLD")
    summary["available"] = True
    summary["generated_at"] = stamp.isoformat()
    tasks = []
    chief_source = "REVIEW_NOT_AVAILABLE"
    if isinstance(review, dict):
        chief = review.get("chief_of_staff")
        if isinstance(chief, dict) and isinstance(chief.get("top_three_next_actions"), list):
            chief_source = "EVIDENCE_REVIEW"
            for item in chief["top_three_next_actions"][:3]:
                if not isinstance(item, dict):
                    return _base("OVERLAY_UNTRUSTED")
                role, action = item.get("owner"), item.get("action")
                if (role not in ROLES or action not in ROLE_ACTIONS
                        or item.get("external_action_authorized") is not False):
                    return _base("OVERLAY_UNTRUSTED")
                partner = item.get("partner")
                if partner is not None and (
                    not isinstance(partner, str) or len(partner) > 120
                ):
                    return _base("OVERLAY_UNTRUSTED")
                tasks.append({
                    "owner": role,
                    "action": action,
                    "partner": partner,
                    "external_action_authorized": False,
                })

    registry_size = reg.get("total_relationships")
    suppressed = reg.get("suppression_review_count")
    if (registry_size is not None and
        (type(registry_size) is not int or not 0 <= registry_size <= 1000)):
        return _base("OVERLAY_UNTRUSTED")
    if (suppressed is not None and
        (type(suppressed) is not int or not 0 <= suppressed <= 1000)):
        return _base("OVERLAY_UNTRUSTED")
    if registry_size is not None and suppressed is not None and suppressed > registry_size:
        return _base("OVERLAY_UNTRUSTED")

    summary["coo"] = {
        "department_cycle": cycle,
        "astra_dispatcher": dispatcher,
        "opportunity_proof": proof_state,
        "mailbox_observer": mailbox_state,
        "task_count": len(review["coo"]["tasks"])
            if isinstance(review, dict) and isinstance(review.get("coo"), dict)
            and isinstance(review["coo"].get("tasks"), list)
            and len(review["coo"]["tasks"]) <= 300
            else None,
    }
    summary["business_development"] = {
        "relationship_registry_status": reg["status"],
        "existing_relationship_count": registry_size,
        "suppression_review_count": suppressed,
        "new_replies_verified": False,
        "mailbox_current": bool(reg.get("mailbox_current") is True and mailbox_state == "HEALTHY"),
    }
    summary["chief_of_staff"] = {
        "top_three_review_actions": tasks,
        "source": chief_source,
        "notifications_sent_by_this_endpoint": False,
    }
    summary["status"] = (
        "REVIEW_ONLY_NO_RELEASE_AUTHORITY"
        if cycle == "SUCCEEDED" and dispatcher == "SUCCEEDED"
            and proof_state == "FRESH" and mailbox_state == "HEALTHY"
            and reg.get("status") == "OBSERVE_REVIEW"
        else "EVIDENCE_HOLD"
    )
    return summary
