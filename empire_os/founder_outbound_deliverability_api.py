"""Read-only Founder API for outbound deliverability health."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from empire_os.outbound_deliverability_provider import ResendMetricsProvider
from empire_os.outbound_deliverability_service import build_rolling_health
from empire_os.outbound_founder_alerts import build_founder_alert


def create_founder_outbound_deliverability_router(
    provider=None,
) -> APIRouter:
    source = provider or ResendMetricsProvider()
    router = APIRouter(
        prefix="/v1/founder-outbound-deliverability",
        tags=["founder-outbound-deliverability"],
    )

    @router.get("")
    def snapshot():
        try:
            health = build_rolling_health(source)
            return {
                **health,
                "founder_alert": build_founder_alert(health),
            }
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"deliverability_provider_unavailable:{type(exc).__name__}",
            ) from exc

    return router
