"""Fail-closed JEV status surface for the existing loopback Founder Read API.

No source configured by default. Entity research routes are registered
only when the host supplies BOTH a trusted reader and an independent
founder-authorization check. No newly public endpoint or new auth system.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from empire_os.jev_gtm_economic_transport import JevEconomicResearchReadUnavailable
from empire_os.jev_gtm_crm_review import read_jev_crm_review
from empire_os.jev_gtm_reply_candidate_reader import review_jev_reply_candidates
from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository


REPLY_RESULT_FIELDS = frozenset({
    "schema_version", "mode", "prospect_id", "candidate_count",
    "candidate_counts_by_unverified_class", "review_fingerprint", "items",
    "full_tenant_inbox_verified", "original_provider_authenticated_count",
    "genuine_buying_conversations_verified", "contact_binding_verified_count",
    "provider_receipts_independently_verified", "new_database_authority",
    "send_authorized", "recognized_revenue", "execution_authority",
})
REPLY_ITEM_FIELDS = frozenset({
    "reply_ref", "intent_ref", "classification_unverified", "received_at",
    "conversation_match_count", "provider_reference_present",
    "provenance_status", "blocker", "positive_buyer_reply_verified",
    "outbound_authorized",
})


def _safe_reply_review_contract(packet: Any) -> bool:
    if not isinstance(packet, dict) or set(packet) != REPLY_RESULT_FIELDS:
        return False
    if (packet.get("schema_version") != "empire.jev.reply_candidate_review.v1"
            or packet.get("mode") != "OBSERVE"
            or packet.get("execution_authority") != "none"
            or packet.get("full_tenant_inbox_verified") is not False
            or packet.get("original_provider_authenticated_count") is not None
            or packet.get("genuine_buying_conversations_verified") is not None
            or packet.get("contact_binding_verified_count") is not None
            or packet.get("provider_receipts_independently_verified") is not False
            or packet.get("new_database_authority") is not False
            or packet.get("send_authorized") is not False
            or packet.get("recognized_revenue") is not None):
        return False
    items = packet.get("items")
    if not isinstance(items, list) or len(items) > 100 or packet.get("candidate_count") != len(items):
        return False
    return all(
        isinstance(item, dict) and set(item) == REPLY_ITEM_FIELDS
        and item.get("positive_buyer_reply_verified") is False
        and item.get("outbound_authorized") is False
        and item.get("provenance_status") == "REVIEW_ONLY_UNAUTHENTICATED"
        for item in items
    )


CRM_RESULT_FIELDS = frozenset({
    "schema_version", "mode", "tenant_binding", "scanned_count",
    "scan_limit", "more_rows_possible", "complete_tenant_inventory_verified",
    "research_lanes", "review_fingerprint", "items",
    "original_provider_reply_count_verified", "commercial_buyer_count_verified",
    "recognized_revenue", "canonical_conversation_identity_verification",
    "action_authority", "automatic_followups", "outbound_sent",
    "contact_permission_granted", "database_write", "execution_authority",
})
CRM_ITEM_FIELDS = frozenset({
    "prospect_id", "niche", "metro", "prospect_status", "research_lane",
    "deterministic_crm_action_candidate", "deterministic_crm_reason",
    "conversation_original_proof_verified", "original_inbound_event_verified",
    "conversation_binding_proven", "qualification_blockers",
    "suppression_clearance_verified", "buyer_identity_verified",
    "commercial_intent_verified", "review_only", "outbound_approved",
})


def _safe_crm_review_contract(packet: Any) -> bool:
    if not isinstance(packet, dict) or set(packet) != CRM_RESULT_FIELDS:
        return False
    if (packet.get("schema_version") != "empire.jev.canonical_crm_review.v1"
            or packet.get("mode") != "OBSERVE"
            or packet.get("tenant_binding") != "existing_authenticated_crm_session_user"
            or packet.get("execution_authority") != "none"
            or packet.get("action_authority") != "none"
            or packet.get("contact_permission_granted") is not False
            or packet.get("automatic_followups") is not False
            or packet.get("outbound_sent") is not False
            or packet.get("database_write") is not False
            or packet.get("original_provider_reply_count_verified") is not None
            or packet.get("commercial_buyer_count_verified") is not None
            or packet.get("recognized_revenue") is not None
            or packet.get("complete_tenant_inventory_verified") is not False):
        return False
    items = packet.get("items")
    if not isinstance(items, list) or len(items) > 100 or packet.get("scanned_count") != len(items):
        return False
    return all(
        isinstance(item, dict) and set(item) == CRM_ITEM_FIELDS
        and item.get("outbound_approved") is False
        and item.get("buyer_identity_verified") is False
        and item.get("original_inbound_event_verified") is False
        and item.get("commercial_intent_verified") is False
        and item.get("suppression_clearance_verified") is False
        and item.get("review_only") is True
        for item in items
    )


def create_founder_jev_router(
    *,
    reader: Any | None = None,
    authorizer: Callable[[Request], bool] | None = None,
    resolve_authenticated_crm: Callable[[Request], AuthenticatedRevenueCrmRead | None] | None = None,
) -> APIRouter:
    if (authorizer is None and (reader is not None or resolve_authenticated_crm is not None)
            or authorizer is not None and reader is None and resolve_authenticated_crm is None):
        raise ValueError("JEV research reader and founder authorization must be paired")
    router = APIRouter(prefix="/v1/founder-jev", tags=["founder-jev"])

    @router.get("/status")
    def status():
        return {
            "schema_version": "empire.founder_jev_status.v1",
            "mode": "OBSERVE",
            "decision_contract_version": "empire.jev.gtm_decision.v2",
            "native_model_primitives": ["choice", "score", "noul"],
            "native_compatibility_tested": True,
            "commercial_model_calibrated": False,
            "shared_vane_openmanus_research_core_integrated": True,
            "jev_evidence_gap_plan_available": True,
            "jev_public_research_execution_activated": False,
            "jev_research_source_validation_completed_live": False,
            "jev_research_spend_gbp": 0,
            "economic_reader_configured": reader is not None,
            "crm_reader_configured": resolve_authenticated_crm is not None,
            "crm_prospect_review_available": resolve_authenticated_crm is not None and authorizer is not None,
            "reply_candidate_reader_prepared": True,
            "reply_candidate_migration_051_applied": None,
            "verified_original_reply_count": None,
            "independent_founder_authorizer_configured": authorizer is not None,
            "real_canonical_rows_verified": None,
            "buyers_identified": None,
            "verified_revenue": None,
            "founder_review_only": True,
            "send_authorized": False,
            "live_commercial_routing": False,
            "production_activated": False,
            "execution_authority": "none",
        }

    if reader is not None and authorizer is not None:
        @router.get("/research/{entity_id}")
        def research(entity_id: str, request: Request):
            try:
                approved = authorizer(request) is True
            except Exception:
                approved = False
            if not approved:
                raise HTTPException(403, detail="founder_research_forbidden")
            try:
                entity = str(UUID(entity_id))
            except (ValueError, TypeError, AttributeError):
                raise HTTPException(400, detail="canonical_entity_required") from None
            try:
                result = reader.read(
                    entity_id=entity, as_of=datetime.now(timezone.utc),
                )
            except JevEconomicResearchReadUnavailable:
                raise HTTPException(503, detail="canonical_economic_reader_unavailable") from None
            except Exception:
                raise HTTPException(503, detail="canonical_economic_reader_unavailable") from None
            required = {
                "schema_version", "mode", "signal_count", "signals_by_type",
                "evidence_fingerprint", "entity_binding_from_observed_signal",
                "source_reader", "status", "buyer_conversations_verified",
                "verified_revenue", "contact_clearance_available",
                "buying_probability_available", "next_action",
                "independent_buyer_identity_verified",
                "source_authorised_commercial_action", "founder_review_only",
                "contains_contact_data", "outbound_sent", "payment_action",
                "execution_authority",
            }
            if (not isinstance(result, dict) or set(result) != required
                    or result.get("schema_version") != "empire.jev.founder_economic_review.v1"
                    or result.get("mode") != "OBSERVE"
                    or result.get("execution_authority") != "none"
                    or result.get("contains_contact_data") is not False
                    or result.get("outbound_sent") is not False
                    or result.get("payment_action") is not False
                    or result.get("source_authorised_commercial_action") is not False
                    or result.get("founder_review_only") is not True
                    or result.get("contact_clearance_available") is not False
                    or result.get("buyer_conversations_verified") is not False
                    or result.get("verified_revenue") is not None):
                raise HTTPException(503, detail="founder_economic_review_contract_invalid")
            return result

    if resolve_authenticated_crm is not None and authorizer is not None:
        @router.get("/crm-prospects/review")
        def crm_prospects_review(
            request: Request, limit: int = Query(default=25, ge=1, le=100)
        ):
            try:
                approved = authorizer(request) is True
            except Exception:
                approved = False
            if not approved:
                raise HTTPException(403, detail="founder_crm_review_forbidden")
            try:
                scope = resolve_authenticated_crm(request)
            except Exception:
                raise HTTPException(503, detail="authenticated_crm_review_unavailable") from None
            if scope is None:
                raise HTTPException(401, detail="authenticated_crm_scope_required")
            if (not isinstance(scope, AuthenticatedRevenueCrmRead)
                    or not isinstance(scope.repository, PostgresRevenueCrmRepository)
                    or scope.tenant_id != scope.repository.tenant_id):
                raise HTTPException(503, detail="authenticated_crm_review_unavailable")
            try:
                packet = read_jev_crm_review(
                    scope.repository, limit=limit, as_of=datetime.now(timezone.utc),
                )
            except Exception:
                raise HTTPException(503, detail="authenticated_crm_review_unavailable") from None
            if not _safe_crm_review_contract(packet):
                raise HTTPException(503, detail="canonical_crm_review_contract_invalid")
            return packet

    if resolve_authenticated_crm is not None and authorizer is not None:
        @router.get("/crm-prospects/{prospect_id}/reply-candidates")
        def crm_reply_candidates(
            prospect_id: str, request: Request,
            limit: int = Query(default=25, ge=1, le=100),
        ):
            try:
                approved = authorizer(request) is True
            except Exception:
                approved = False
            if not approved:
                raise HTTPException(403, detail="founder_reply_review_forbidden")
            try:
                scope = resolve_authenticated_crm(request)
            except Exception:
                raise HTTPException(503, detail="authenticated_reply_review_unavailable") from None
            if scope is None:
                raise HTTPException(401, detail="authenticated_crm_scope_required")
            if (not isinstance(scope, AuthenticatedRevenueCrmRead)
                    or not isinstance(scope.repository, PostgresRevenueCrmRepository)
                    or scope.tenant_id != scope.repository.tenant_id):
                raise HTTPException(503, detail="authenticated_reply_review_unavailable")
            try:
                reply_packet = review_jev_reply_candidates(
                    scope.repository, prospect_id=prospect_id,
                    limit=limit, as_of=datetime.now(timezone.utc),
                )
            except ValueError:
                raise HTTPException(400, detail="canonical_reply_review_input_invalid") from None
            except Exception:
                raise HTTPException(503, detail="authenticated_reply_review_unavailable") from None
            if not _safe_reply_review_contract(reply_packet):
                raise HTTPException(503, detail="canonical_reply_review_contract_invalid")
            return reply_packet

    return router
