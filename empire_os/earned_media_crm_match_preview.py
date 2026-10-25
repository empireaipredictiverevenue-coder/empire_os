"""Strict preview-only canonical CRM match semantics for earned media packets.

An authenticated owner will need to supply verified canonical joins. No database
client, tenant lookup, contact inference, outreach or mutation exists here.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

SCHEMA = "empire.earned_media_crm_matching.review.v1"


def _uuid(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(UUID(value))
    except (ValueError, AttributeError, TypeError):
        return None


def preview_crm_links(
    packet: Mapping[str, Any],
    canonical_join_evidence: Sequence[Mapping[str, Any]],
    *,
    authenticated_tenant_id: str | None,
) -> dict[str, Any]:
    """Fail closed and never bind/unbind CRM IDs from outside approved CRM writers."""
    items = packet.get("items")
    if (packet.get("schema_version") != "empire.earned_media_advisory.review.v1"
            or packet.get("mode") != "OBSERVE"
            or packet.get("execution_authority") != "none"
            or not isinstance(items, list)):
        raise ValueError("INVALID_REVIEW_PACKET")
    if len(canonical_join_evidence) > 200:
        raise ValueError("CANONICAL_JOIN_EVIDENCE_OVER_LIMIT")
    tenant = _uuid(authenticated_tenant_id)
    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("item_id"), str):
            raise ValueError("INVALID_REVIEW_ITEM")
        thread = item.get("source_provider_thread")
        status = "NO_MATCH_ELIGIBLE_EVIDENCE"
        candidates: list[dict[str, str]] = []
        if (tenant is not None and item.get("lane") == "pr"
                and item.get("state") == "SENT_PROVIDER_RECEIPT_REPLY_UNVERIFIED"
                and isinstance(thread, str) and thread):
            for candidate in canonical_join_evidence:
                if not isinstance(candidate, Mapping):
                    continue
                if (candidate.get("evidence_type") != "confirmed_conversation_join_v1"
                        or candidate.get("source_provider_thread") != thread
                        or _uuid(candidate.get("tenant_id")) != tenant
                        or candidate.get("tenant_membership_verified") is not True
                        or candidate.get("company_identity_verified") is not True
                        or candidate.get("provider_thread_reconciled") is not True):
                    continue
                company = _uuid(candidate.get("canonical_company_id"))
                prospect = _uuid(candidate.get("canonical_prospect_id"))
                opportunity = _uuid(candidate.get("canonical_opportunity_id"))
                if company and prospect and opportunity:
                    candidates.append({
                        "canonical_company_id": company,
                        "canonical_prospect_id": prospect,
                        "canonical_opportunity_id": opportunity,
                    })
            distinct = {tuple(sorted(x.items())) for x in candidates}
            if len(distinct) == 1:
                status = "MATCH_CANDIDATE_OWNER_REVIEW_REQUIRED"
            elif len(distinct) > 1:
                status = "HOLD_AMBIGUOUS_CANONICAL_MATCH"
            else:
                status = "UNBOUND_NO_PROVEN_CANONICAL_JOIN"
        elif tenant is None:
            status = "HOLD_AUTHENTICATED_TENANT_ID_MISSING"
        # No candidate IDs exposed or promoted without an exact owner action.
        result.append({
            "item_id": item["item_id"],
            "lane": item.get("lane"),
            "match_state": status,
            "canonical_join_candidate_count": min(len({
                tuple(sorted(x.items())) for x in candidates
            }), 200),
            "crm_write_authorized": False,
            "automatic_binding_authorized": False,
        })
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "authenticated_tenant_source": (
            "CALLER_ASSERTED_NOT_AUTHENTICATED_BY_MATCHER" if tenant else "UNAVAILABLE"),
        "items": result,
        "crm_reads_performed": False,
        "crm_writes_performed": False,
        "automatic_crm_binding_authorized": False,
        "status": "OWNER_REVIEW_ONLY" if tenant else "HELD_TENANT_AUTHORITY_UNAVAILABLE",
    }
