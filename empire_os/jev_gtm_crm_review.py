"""GTM review of exactly scoped canonical Revenue CRM prospect projections.

Uses existing dedicated, read-only CRM repository and deterministic CRM review
contracts. Conversation/closer fields intentionally NULL in the current
canonical view. Never invents a buyer reply, payment or contact approval.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping
from uuid import UUID

from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
from empire_os.revenue_crm_api import derive_next_action
from empire_os.revenue_crm_reply_qualification import review_crm_reply_qualification

SCHEMA = "empire.jev.canonical_crm_review.v1"
MAX_PROSPECTS = 100


def _uuid(value: Any, name: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f"canonical {name} required") from None


def read_jev_crm_review(
    repository: PostgresRevenueCrmRepository, *,
    limit: int = 50,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Read bounded tenant-scoped CRM records for internal operator attention.

    The existing repository proves the session_user tenant, sets ROLE and
    enforces the static tenant-filtered view. This does NOT claim it proves
    original inbound provider events or linked conversation identity.
    """
    if not isinstance(repository, PostgresRevenueCrmRepository):
        raise ValueError("dedicated canonical CRM repository required")
    if type(limit) is not int or not 1 <= limit <= MAX_PROSPECTS:
        raise ValueError("bounded CRM review limit required")
    instant = as_of if as_of is not None else datetime.now(timezone.utc)
    if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("timezone-aware review timestamp required")
    tenant = _uuid(repository.tenant_id, "tenant_id")
    records = repository.prospects(limit=limit)
    if not isinstance(records, (list, tuple)) or len(records) > limit:
        raise ValueError("canonical CRM bounded read violated")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in records:
        if not isinstance(row, Mapping) or _uuid(row.get("tenant_id"), "row tenant") != tenant:
            raise ValueError("CRM tenant binding mismatch")
        prospect_id = _uuid(row.get("prospect_id"), "prospect_id")
        if prospect_id in seen:
            raise ValueError("duplicate canonical CRM prospect")
        seen.add(prospect_id)
        # Canonical 040 view has NULL conversation/closer/fulfilment data:
        # existing CRM decision and reply qualification owners must determine
        # review reasons, not another model or invented linkage.
        existing = derive_next_action(row)
        qualification = review_crm_reply_qualification(
            prospect=row, conversation=None, events=[],
            stage3_source_health=None, now=instant,
        )
        if (existing.execution_authority != "none" or
                existing.approval_required is not True or
                qualification["execution_authority"] != "none" or
                qualification["crm_operator_handoff_authorized"] is not False or
                qualification["buyer_intent_verified"] is not False):
            raise ValueError("canonical CRM review returned unsafe authority")
        inferred = (
            "REPLY_EVIDENCE_REVIEW"
            if row.get("conversation_id") is not None
            else "CANONICAL_IDENTITY_RESEARCH"
        )
        items.append({
            "prospect_id": prospect_id,
            "niche": str(row.get("niche") or "").strip()[:100] or None,
            "metro": str(row.get("metro") or "").strip()[:100] or None,
            "prospect_status": str(row.get("prospect_status") or "").strip()[:100] or None,
            "research_lane": inferred,
            "deterministic_crm_action_candidate": existing.action if existing.available else None,
            "deterministic_crm_reason": existing.reason,
            "conversation_original_proof_verified": False,
            "original_inbound_event_verified": False,
            "conversation_binding_proven": False,
            "qualification_blockers": qualification["blockers"],
            "suppression_clearance_verified": False,
            "buyer_identity_verified": False,
            "commercial_intent_verified": False,
            "review_only": True,
            "outbound_approved": False,
        })
    items.sort(key=lambda item: (
        0 if item["research_lane"] == "REPLY_EVIDENCE_REVIEW" else 1,
        item["prospect_id"],
    ))
    digest = sha256(json.dumps(items, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    counts = dict(sorted(Counter(item["research_lane"] for item in items).items()))
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "tenant_binding": "existing_authenticated_crm_session_user",
        "scanned_count": len(items),
        "scan_limit": limit,
        "more_rows_possible": len(items) >= limit,
        "complete_tenant_inventory_verified": False,
        "research_lanes": counts,
        "review_fingerprint": digest,
        "items": items,
        "original_provider_reply_count_verified": None,
        "commercial_buyer_count_verified": None,
        "recognized_revenue": None,
        "canonical_conversation_identity_verification": "NOT_PROVEN_BY_CURRENT_CRM_VIEW",
        "action_authority": "none",
        "automatic_followups": False,
        "outbound_sent": False,
        "contact_permission_granted": False,
        "database_write": False,
        "execution_authority": "none",
    }
