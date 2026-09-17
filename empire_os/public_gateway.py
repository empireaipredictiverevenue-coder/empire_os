"""Empire AI public recovery gateway.

Read-only public surface used behind Cloudflare Tunnel. Deliberately does
not expose the legacy Hub, settlement, allocation, outreach, or closer APIs.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

GATEWAY_VERSION = "recovery-v1"
AEO_ROOT = Path(os.getenv("EMPIRE_PUBLIC_AEO_ROOT", "/srv/empire_os/runtime/aeo"))
AEO_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Empire AI Public Gateway",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.mount("/aeo", StaticFiles(directory=str(AEO_ROOT), html=True), name="aeo")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"
    return response


@app.get("/health")
def health():
    return {
        "status": "online",
        "service": "empire-ai-public-gateway",
        "version": GATEWAY_VERSION,
        "execution": "read-only-public-surface",
    }


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return "User-agent: *\nAllow: /\nAllow: /aeo/\n"


@app.get("/", response_class=HTMLResponse)
def home():
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Empire AI — Predictive Revenue</title><meta name="description" content="Empire AI predictive revenue infrastructure.">
</head><body><main><h1>Empire AI</h1><p>Predictive Revenue infrastructure.</p>
<p>Public services are being restored through the governed EmpireOS control plane.</p>
</main></body></html>"""
