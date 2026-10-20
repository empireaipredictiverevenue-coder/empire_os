"""Bounded preview surface only. Does not operate a phone line or book appointments."""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from empire_os.inbound_revenue_recovery import TenantReceptionProfile, plan_reception_response


class InboundReceptionPreview(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=100)
    business_name: str = Field(min_length=1, max_length=120)
    vertical: str = "general"
    intent: str = Field(min_length=1, max_length=80)
    booking_integration_verified: bool = False
    human_transfer_configured: bool = False
    callback_capture_allowed: bool = False


def create_inbound_recovery_router() -> APIRouter:
    router = APIRouter(prefix="/v1/inbound-recovery", tags=["inbound-recovery"])

    @router.post("/preview")
    def preview(payload: InboundReceptionPreview, x_empire_preview_token: str | None = Header(default=None)):
        enabled = os.getenv("EMPIRE_INBOUND_RECOVERY_PREVIEW_ENABLED", "").strip().lower() in {
            "1", "yes", "true", "on"
        }
        secret = os.getenv("EMPIRE_INBOUND_RECOVERY_PREVIEW_TOKEN", "").strip()
        if not enabled:
            raise HTTPException(status_code=404, detail="inbound_recovery_preview_disabled")
        if not secret or not x_empire_preview_token or not hmac.compare_digest(secret, x_empire_preview_token):
            raise HTTPException(status_code=401, detail="inbound_recovery_preview_unauthorized")
        if payload.vertical not in {"home_services", "hospitality", "professional_services", "general"}:
            raise HTTPException(status_code=422, detail="unsupported_vertical")
        profile = TenantReceptionProfile(
            tenant_id=payload.tenant_id,
            business_name=payload.business_name,
            vertical=payload.vertical,
            booking_integration_verified=payload.booking_integration_verified,
            human_transfer_configured=payload.human_transfer_configured,
            callback_capture_allowed=payload.callback_capture_allowed,
        )
        result = plan_reception_response(profile, payload.intent)
        return {
            "mode": "nonlive_preview_only",
            "tenant_id": profile.tenant_id,
            "action": result.action,
            "spoken_text": result.spoken_text,
            "reason": result.reason,
            "booking_confirmed": False,
            "outbound_authorized": False,
            "provider_connected": False,
            "database_writes": False,
        }

    return router
