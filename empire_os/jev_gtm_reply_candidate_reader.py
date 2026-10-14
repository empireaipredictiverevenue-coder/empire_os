"""Bounded JEV reply-candidate metadata using the EXISTING authenticated CRM role.

Requires PREPARED-ONLY EmpireDB 051 to be independently approved/applied.
Does not use the global Conversation OS SELECT-true reader, touch email bodies,
claim original provider authenticity or perform any outbound action.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping
from uuid import UUID

from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository

RPC_SQL = (
    "SELECT tenant_id,prospect_id,reply_id,outbound_intent_id,"
    "received_at,reply_classification,intent_status,"
    "provider_reference_present,matching_conversation_count,"
    "original_provider_authenticated,contact_binding_verified "
    "FROM public.empire_read_crm_reply_candidates(%s::uuid,%s::integer)"
)
MAX_ROWS = 100
SUPPORTED_CLASSES = {
    "unclassified", "positive", "negative", "question",
    "objection", "later", "unsubscribe", "bounce", "other",
}


def _uuid(value: Any) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("canonical reply/intent identity required") from None


def review_jev_reply_candidates(
    repository: PostgresRevenueCrmRepository, *,
    prospect_id: str,
    limit: int = 25,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Review source records as *unverified reply candidates*, never messages."""
    if not isinstance(repository, PostgresRevenueCrmRepository):
        raise ValueError("canonical authenticated CRM repository required")
    if type(limit) is not int or not 1 <= limit <= MAX_ROWS:
        raise ValueError("bounded reply candidate limit required")
    now = as_of if as_of is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware review timestamp required")
    target = _uuid(prospect_id)
    tenant = _uuid(repository.tenant_id)
    # This existing reader enforces READ ONLY, static scoped SQL and exact
    # database session_user tenant resolution; no separate credentials.
    rows = repository._fetch_all(RPC_SQL, (target, limit))
    if not isinstance(rows, list) or len(rows) > limit:
        raise ValueError("unbounded canonical reply source")
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping) or _uuid(row.get("tenant_id")) != tenant:
            raise ValueError("canonical reply tenant scope mismatch")
        if _uuid(row.get("prospect_id")) != target:
            raise ValueError("cross-prospect reply result")
        reply_id = _uuid(row.get("reply_id"))
        intent_id = _uuid(row.get("outbound_intent_id"))
        if reply_id in seen:
            raise ValueError("duplicated canonical reply evidence")
        seen.add(reply_id)
        classification = row.get("reply_classification")
        if classification not in SUPPORTED_CLASSES:
            raise ValueError("invalid source reply classification")
        stamp = row.get("received_at")
        if isinstance(stamp, str):
            try:
                stamp = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError("invalid original reply timestamp") from None
        if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("offset-aware received timestamp required")
        age_s = (now.astimezone(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
        if age_s < 0:
            raise ValueError("future reply candidate")
        match_count = row.get("matching_conversation_count")
        if type(match_count) is not int or match_count < 0:
            raise ValueError("canonical conversation cardinality invalid")
        # Even exact cardinality is only structural: provider authenticity,
        # contact binding, and consent need independent evidence and ownership.
        if row.get("original_provider_authenticated") is not False:
            raise ValueError("reply source cannot grant provider authentication")
        if row.get("contact_binding_verified") is not False:
            raise ValueError("reply source cannot attest contact binding")
        provider_ref = row.get("provider_reference_present")
        if type(provider_ref) is not bool:
            raise ValueError("provider reference shape invalid")
        if match_count != 1:
            reason = "CONVERSATION_CARDINALITY_UNPROVEN"
        elif not provider_ref:
            reason = "ORIGINAL_PROVIDER_MESSAGE_REFERENCE_MISSING"
        else:
            reason = "ORIGINAL_PROVIDER_AND_CONTACT_PROOF_PENDING"
        results.append({
            "reply_ref": reply_id, "intent_ref": intent_id,
            "classification_unverified": classification,
            "received_at": stamp.astimezone(timezone.utc).isoformat(),
            "conversation_match_count": match_count,
            "provider_reference_present": provider_ref,
            "provenance_status": "REVIEW_ONLY_UNAUTHENTICATED",
            "blocker": reason,
            "positive_buyer_reply_verified": False,
            "outbound_authorized": False,
        })
    results.sort(key=lambda item: (item["received_at"], item["reply_ref"]), reverse=True)
    counts = {key: sum(r["classification_unverified"] == key for r in results)
              for key in sorted(SUPPORTED_CLASSES)}
    fingerprint = sha256(
        json.dumps(results, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return {
        "schema_version": "empire.jev.reply_candidate_review.v1",
        "mode": "OBSERVE",
        "prospect_id": target,
        "candidate_count": len(results),
        "candidate_counts_by_unverified_class": counts,
        "review_fingerprint": fingerprint,
        "items": results,
        "full_tenant_inbox_verified": False,
        "original_provider_authenticated_count": None,
        "genuine_buying_conversations_verified": None,
        "contact_binding_verified_count": None,
        "provider_receipts_independently_verified": False,
        "new_database_authority": False,
        "send_authorized": False,
        "recognized_revenue": None,
        "execution_authority": "none",
    }
