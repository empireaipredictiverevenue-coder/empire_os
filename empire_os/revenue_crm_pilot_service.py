"""Dedicated first-party CRM pilot HTTP service. No copy of the full Hub.

Default: refuses to start. Only an independently approved, private, complete
CRM pilot configuration can mount the existing first-party login and tenant
read routers. Server deployment binds loopback only; no public route added.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import Response

from empire_os.revenue_crm_pilot_activation import (
    ACTIVATION_MODE, create_crm_routers_for_hub,
)


def build_revenue_crm_pilot_service() -> FastAPI:
    if os.environ.get("EMPIRE_CRM_PILOT_MODE") != ACTIVATION_MODE:
        raise RuntimeError("crm_pilot_is_not_authorized")
    if not os.environ.get("EMPIRE_CRM_PILOT_CONFIG_FILE"):
        raise RuntimeError("crm_pilot_private_config_missing")
    routers = create_crm_routers_for_hub()
    if len(routers) != 2:
        raise RuntimeError("crm_pilot_authenticated_router_pair_required")

    service = FastAPI(
        title="Empire First-party CRM Pilot",
        docs_url=None, redoc_url=None, openapi_url=None,
    )
    for router in routers:
        for route in router.routes:
            path = str(getattr(route, "path", ""))
            if not path.startswith("/v1/revenue-crm/"):
                raise RuntimeError("crm_pilot_unexpected_route")
        service.include_router(router)

    @service.middleware("http")
    async def protect_http(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @service.get("/health")
    def health():
        return {
            "ok": True,
            "service": "empire-crm-first-party-pilot",
            "mode": ACTIVATION_MODE,
            "outbound_authority": "none",
            "payment_authority": "none",
            "database_provisioning": False,
        }

    return service
