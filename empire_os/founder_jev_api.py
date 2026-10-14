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

from fastapi import APIRouter, HTTPException, Request

from empire_os.jev_gtm_economic_transport import JevEconomicResearchReadUnavailable


def create_founder_jev_router(
    *,
    reader: Any | None = None,
    authorizer: Callable[[Request], bool] | None = None,
) -> APIRouter:
    if (reader is None) != (authorizer is None):
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
            "economic_reader_configured": reader is not None,
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

    return router
