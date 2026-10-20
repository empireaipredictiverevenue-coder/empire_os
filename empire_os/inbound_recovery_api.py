"""Bounded preview surface only. Never operates a phone or books appointments."""
from __future__ import annotations

from datetime import datetime
import hmac
import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from empire_os.inbound_business_hours import (
    BusinessHoursPolicy,
    StaffedWindow,
    plan_hours_aware_reception_response,
    staffed_hours_status,
)
from empire_os.inbound_revenue_recovery import (
    TenantReceptionProfile, plan_reception_response,
)


class PreviewStaffedWindow(BaseModel):
    weekday: int
    opens: str
    closes: str


class PreviewStaffedHours(BaseModel):
    timezone_name: str = Field(min_length=1, max_length=100)
    when_iso: str = Field(min_length=1, max_length=50)
    windows: list[PreviewStaffedWindow] = Field(default_factory=list, max_length=28)
    closed_dates: list[str] = Field(default_factory=list, max_length=366)
    simulated_verified: bool = False


class InboundReceptionPreview(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=100)
    business_name: str = Field(min_length=1, max_length=120)
    vertical: str = "general"
    intent: str = Field(min_length=1, max_length=80)
    booking_integration_verified: bool = False
    human_transfer_configured: bool = False
    callback_capture_allowed: bool = False
    staffed_hours: PreviewStaffedHours | None = None


def create_inbound_recovery_router() -> APIRouter:
    router = APIRouter(prefix="/v1/inbound-recovery", tags=["inbound-recovery"])

    @router.post("/preview")
    def preview(
        payload: InboundReceptionPreview,
        x_empire_preview_token: str | None = Header(default=None),
    ):
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
        hours_preview = None
        if payload.staffed_hours is None:
            decision = plan_reception_response(profile, payload.intent)
        else:
            params = payload.staffed_hours
            try:
                policy = BusinessHoursPolicy(
                    tenant_id=payload.tenant_id,
                    timezone_name=params.timezone_name,
                    windows=tuple(
                        StaffedWindow(w.weekday, w.opens, w.closes)
                        for w in params.windows
                    ),
                    closed_dates=tuple(params.closed_dates),
                    verified=params.simulated_verified,
                )
                when = datetime.fromisoformat(params.when_iso.replace("Z", "+00:00"))
                decision = plan_hours_aware_reception_response(
                    profile, policy, when, payload.intent
                )
                status = staffed_hours_status(policy, when)
            except (ValueError, TypeError, OverflowError) as exc:
                raise HTTPException(status_code=422, detail="invalid_staffed_hours_preview") from exc
            hours_preview = {
                "origin": "operator_supplied_simulation_only",
                "hours_simulated_as_verified": status.verified,
                "open_now": status.open_now,
                "next_open_at": status.next_open_at,
                "reason": status.reason,
            }
        return {
            "mode": "nonlive_preview_only",
            "tenant_id": profile.tenant_id,
            "action": decision.action,
            "spoken_text": decision.spoken_text,
            "reason": decision.reason,
            "staffed_hours": hours_preview,
            "booking_confirmed": False,
            "outbound_authorized": False,
            "provider_connected": False,
            "database_writes": False,
        }

    return router
