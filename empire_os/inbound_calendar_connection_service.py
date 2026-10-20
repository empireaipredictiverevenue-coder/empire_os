"""Private, default-disabled Calendar Connection service for staging.

Deployment ONLY to loopback. No Google credentials or outbound network
operations. Mounts the disabled routes to let operators prove safe defaults.
Active customer OAuth requires separately reviewed identity/session/vault
configuration and a different explicitly approved release.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import Response

from empire_os.inbound_calendar_connection_api import (
    create_calendar_connection_router,
)

app = FastAPI(
    title="Empire Revenue Recovery Calendar Connection — dark loopback staging",
    docs_url=None, redoc_url=None, openapi_url=None,
)
app.include_router(create_calendar_connection_router())


@app.middleware("http")
async def secure_http(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.get("/health")
def health():
    return {
        "service": "empire-inbound-recovery-calendar-connection",
        "status": "dark-staging",
        "loopback_only_required": True,
        "google_calendar_connected": False,
        "oauth_callbacks_enabled": False,
        "openmanus_worker_verified": False,
        "commercial_actions_authorized": False,
    }
