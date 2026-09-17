"""Empire AI public gateway behind Cloudflare Tunnel.

Public surface is discovery/read-only. It deliberately excludes legacy settlement,
allocation, outreach, buyer activation and closer mutation endpoints.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import Body, FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from empire_os.agent_web import a2a_agent_card, capability_manifest, webmcp_manifest

GATEWAY_VERSION = "agent-web-v1"
PUBLIC_BASE_URL = os.getenv("EMPIRE_PUBLIC_BASE_URL", "https://empire-ai.co.uk").rstrip("/")
AEO_ROOT = Path(os.getenv("EMPIRE_PUBLIC_AEO_ROOT", "/srv/empire_os/runtime/aeo"))
AEO_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Empire AI Public Gateway", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/aeo", StaticFiles(directory=str(AEO_ROOT), html=True), name="aeo")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    )
    return response


@app.get("/health")
def health():
    return {
        "status": "online",
        "service": "empire-ai-public-gateway",
        "version": GATEWAY_VERSION,
        "execution": "read-only-public-surface",
        "astra": "governed",
    }


@app.get("/agent-web/capabilities")
def capabilities(surface: str | None = Query(default=None, pattern="^(webmcp|mcp|a2a)$")):
    return {
        "version": "agent-web-v1",
        "surface": surface or "all",
        "capabilities": capability_manifest(surface),
        "privilegedActionsExposed": False,
    }


@app.get("/.well-known/agent-card.json")
def agent_card():
    return JSONResponse(a2a_agent_card(PUBLIC_BASE_URL), media_type="application/json")


@app.post("/a2a/v1/message:send")
def a2a_message_send(payload: dict = Body(...)):
    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, dict):
        return JSONResponse({"error": {"code": "INVALID_ARGUMENT", "message": "message is required"}}, status_code=400)
    parts = message.get("parts") or []
    request_text = " ".join(
        str(part.get("text", "")) for part in parts if isinstance(part, dict) and part.get("text")
    )[:500]
    context_id = message.get("contextId") or str(uuid.uuid4())
    result = {
        "mode": "public_read_discovery",
        "request": request_text,
        "capabilities": capability_manifest("a2a"),
        "governance": "Astra approval required for consequential or commercial actions",
    }
    reply = {
        "messageId": str(uuid.uuid4()),
        "contextId": context_id,
        "role": "ROLE_AGENT",
        "parts": [{"data": result, "mediaType": "application/json"}],
        "metadata": {"privilegedActionsExposed": False},
    }
    return JSONResponse({"message": reply}, media_type="application/a2a+json")


@app.get("/agent-web/webmcp-manifest.json")
def webmcp_manifest_route():
    return {"version": "2026-09-15-draft", "tools": webmcp_manifest()}


@app.get("/agent-web/webmcp.js")
def webmcp_bootstrap():
    script = r'''(() => {
  const mc = document.modelContext;
  if (!mc || !mc.registerTool) return;
  mc.registerTool({
    name: "empire_discover_intelligence",
    title: "Discover Empire Intelligence",
    description: "Discover Empire's public read-only market, opportunity, SEO, AEO, GEO and citation capabilities.",
    inputSchema: {
      type: "object",
      properties: { surface: { type: "string", enum: ["webmcp", "mcp", "a2a"] } },
      additionalProperties: false
    },
    annotations: { readOnlyHint: true, untrustedContentHint: false, consequentialHint: false },
    execute: async (args, options) => {
      const qs = args && args.surface ? `?surface=${encodeURIComponent(args.surface)}` : "";
      const response = await fetch(`/agent-web/capabilities${qs}`, { signal: options.signal });
      if (!response.ok) throw new Error(`Empire capability discovery failed: ${response.status}`);
      return await response.json();
    }
  }).catch(() => {});
})();'''
    return Response(content=script, media_type="application/javascript")


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return "User-agent: *\nAllow: /\nAllow: /aeo/\nAllow: /.well-known/agent-card.json\n"


@app.get("/", response_class=HTMLResponse)
def home():
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Empire AI — Predictive Revenue</title>
<meta name="description" content="Empire AI predictive revenue and agent intelligence infrastructure.">
<script src="/agent-web/webmcp.js" defer></script>
</head><body><main><h1>Empire AI</h1><p>Predictive Revenue infrastructure.</p>
<p>Human-readable, crawler-readable and agent-readable intelligence through the governed EmpireOS control plane.</p>
<nav><a href="/agent-web/capabilities">Agent Web capabilities</a> · <a href="/.well-known/agent-card.json">A2A Agent Card</a></nav>
</main></body></html>"""
