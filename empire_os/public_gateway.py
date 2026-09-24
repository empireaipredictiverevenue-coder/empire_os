"""Empire AI public gateway behind Cloudflare Tunnel.

Public surface is discovery/read-only. It deliberately excludes legacy settlement,
allocation, outreach, buyer activation and closer mutation endpoints.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import uuid
from pathlib import Path

import httpx
from fastapi import Body, FastAPI, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from empire_os.agent_web import a2a_agent_card, capability_manifest, webmcp_manifest
from empire_os.a2a_discovery import commerce_discovery_manifest
from empire_os.agent_web_runtime import execute_public_capability

GATEWAY_VERSION = "agent-web-v1.1"
PUBLIC_BASE_URL = os.getenv("EMPIRE_PUBLIC_BASE_URL", "https://empire-ai.co.uk").rstrip("/")
AEO_ROOT = Path(os.getenv("EMPIRE_PUBLIC_AEO_ROOT", "/srv/empire_os/runtime/aeo"))
AEO_ROOT.mkdir(parents=True, exist_ok=True)
SITE_OUT = Path(os.getenv("EMPIRE_PUBLIC_SITE_OUT", "/srv/empire_os/apps/empire-public-site/out"))
TRUST_SNAPSHOT = Path("/srv/empire_os/runtime/trust/latest.json")
RESEND_INBOUND_URL = os.getenv(
    "EMPIRE_RESEND_INBOUND_URL",
    "http://127.0.0.1:8097/webhooks/resend-inbound",
).strip()
CHECKOUT_INTERNAL_URL = os.getenv(
    "EMPIRE_CHECKOUT_INTERNAL_URL",
    "http://127.0.0.1:8098",
).rstrip("/")

app = FastAPI(title="Empire AI Public Gateway", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/aeo", StaticFiles(directory=str(AEO_ROOT), html=True), name="aeo")
app.mount("/_next", StaticFiles(directory=str(SITE_OUT / "_next"), check_dir=False), name="next-static")


_INLINE_SCRIPT_RE = re.compile(
    r"<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)


def _inline_script_hashes(path: Path | None) -> tuple[str, ...]:
    if path is None or not path.is_file():
        return ()
    try:
        html = path.read_text(encoding="utf-8")
    except OSError:
        return ()

    hashes: list[str] = []
    for match in _INLINE_SCRIPT_RE.finditer(html):
        attrs = match.group("attrs") or ""
        if re.search(r"\bsrc\s*=", attrs, re.IGNORECASE):
            continue
        body = match.group("body")
        digest = hashlib.sha256(body.encode("utf-8")).digest()
        token = "'sha256-" + base64.b64encode(digest).decode("ascii") + "'"
        if token not in hashes:
            hashes.append(token)
    return tuple(hashes)


def _site_csp(route: str) -> str:
    page = _site_html_path(route)
    script_hashes = _inline_script_hashes(page)
    script_src = "script-src 'self'"
    if script_hashes:
        script_src += " " + " ".join(script_hashes)
    return (
        "default-src 'self'; "
        + script_src
        + "; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; "
        "worker-src 'self' blob:; frame-ancestors 'none'"
    )


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = _site_csp(request.url.path)
    return response


def _site_html_path(route: str, root: Path | None = None) -> Path | None:
    base = root or SITE_OUT
    clean = str(route or "").strip().strip("/")
    if not clean:
        candidate = base / "index.html"
    elif clean == "trust":
        candidate = base / "trust.html"
    elif clean == "industries":
        candidate = base / "industries.html"
    elif clean == "buy":
        candidate = base / "buy.html"
    elif clean.startswith("industries/"):
        slug = clean.split("/", 1)[1]
        if not slug or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in slug):
            return None
        candidate = base / "industries" / f"{slug}.html"
    else:
        return None
    return candidate if candidate.is_file() else None


def _public_site_urls(root: Path | None = None) -> list[str]:
    base = root or SITE_OUT
    urls: list[str] = []
    if (base / "trust.html").is_file():
        urls.append(f"{PUBLIC_BASE_URL}/trust")
    if (base / "industries.html").is_file():
        urls.append(f"{PUBLIC_BASE_URL}/industries")
    if (base / "buy.html").is_file():
        urls.append(f"{PUBLIC_BASE_URL}/buy")
    industries = base / "industries"
    if industries.is_dir():
        for path in sorted(industries.glob("*.html")):
            urls.append(f"{PUBLIC_BASE_URL}/industries/{path.stem}")
    return urls


def _public_trust_manifest(path: Path | None = None) -> dict:
    target = path or TRUST_SNAPSHOT
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "schema_version": "empire.public_trust_manifest.v1",
            "trust_center_ready": False,
            "verified_claims": [],
            "unknowns_hidden": False,
            "fabricated_social_proof": False,
            "available": False,
        }
    manifest = payload.get("public_manifest")
    if not isinstance(manifest, dict):
        return {
            "schema_version": "empire.public_trust_manifest.v1",
            "trust_center_ready": False,
            "verified_claims": [],
            "unknowns_hidden": False,
            "fabricated_social_proof": False,
            "available": False,
        }
    return {**manifest, "available": True}


def _aeo_page_urls(root: Path | None = None) -> list[str]:
    base = root or AEO_ROOT
    urls: list[str] = []
    for path in sorted(base.glob("*/*/index.html")):
        rel = path.relative_to(base)
        if len(rel.parts) != 3:
            continue
        niche, metro, filename = rel.parts
        if filename != "index.html":
            continue
        urls.append(f"{PUBLIC_BASE_URL}/aeo/{niche}/{metro}/")
    return urls


def _sitemap_xml(
    root: Path | None = None,
    site_root: Path | None = None,
) -> str:
    urls = (
        [f"{PUBLIC_BASE_URL}/"]
        + _public_site_urls(site_root)
        + _aeo_page_urls(root)
    )
    body = "".join(f"<url><loc>{url}</loc></url>" for url in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{body}</urlset>"
    )


@app.get("/v1/trust/manifest")
def public_trust_manifest():
    return _public_trust_manifest()


@app.get("/health")
def health():
    return {
        "status": "online",
        "service": "empire-ai-public-gateway",
        "version": GATEWAY_VERSION,
        "execution": "read-only-public-surface",
        "astra": "governed",
    }




@app.post("/webhooks/resend-inbound")
async def resend_inbound_proxy(request: Request):
    raw = await request.body()
    if len(raw) > 1_000_000:
        return JSONResponse({"ok": False}, status_code=413)

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() in {
            "content-type",
            "svix-id",
            "svix-timestamp",
            "svix-signature",
        }
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                RESEND_INBOUND_URL,
                content=raw,
                headers=headers,
            )
    except httpx.HTTPError:
        return JSONResponse(
            {"ok": False, "error": "resend_inbound_unavailable"},
            status_code=503,
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get(
            "content-type",
            "application/json",
        ),
    )


@app.get("/v1/checkout/catalog")
async def checkout_catalog_proxy():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{CHECKOUT_INTERNAL_URL}/v1/catalog"
            )
    except httpx.HTTPError:
        return JSONResponse(
            {"error": "checkout_unavailable"},
            status_code=503,
        )
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get(
            "content-type",
            "application/json",
        ),
    )


@app.post("/v1/checkout/orders")
async def checkout_order_proxy(request: Request):
    raw = await request.body()
    if len(raw) > 32_768:
        return JSONResponse(
            {"error": "checkout_payload_too_large"},
            status_code=413,
        )
    if "application/json" not in request.headers.get(
        "content-type",
        ""
    ).lower():
        return JSONResponse(
            {"error": "application_json_required"},
            status_code=415,
        )
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{CHECKOUT_INTERNAL_URL}/v1/orders",
                content=raw,
                headers={"Content-Type": "application/json"},
            )
    except httpx.HTTPError:
        return JSONResponse(
            {"error": "checkout_unavailable"},
            status_code=503,
        )
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get(
            "content-type",
            "application/json",
        ),
    )


@app.get("/v1/checkout/exchange/tiers")
async def checkout_exchange_tiers_proxy():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{CHECKOUT_INTERNAL_URL}/v1/exchange/tiers"
            )
    except httpx.HTTPError:
        return JSONResponse(
            {"error": "exchange_checkout_unavailable"},
            status_code=503,
        )
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get(
            "content-type",
            "application/json",
        ),
    )


@app.post("/v1/checkout/exchange/interests")
async def checkout_exchange_interest_proxy(request: Request):
    raw = await request.body()
    if len(raw) > 32_768:
        return JSONResponse(
            {"error": "checkout_payload_too_large"},
            status_code=413,
        )
    if "application/json" not in request.headers.get(
        "content-type",
        ""
    ).lower():
        return JSONResponse(
            {"error": "application_json_required"},
            status_code=415,
        )
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{CHECKOUT_INTERNAL_URL}/v1/exchange/interests",
                content=raw,
                headers={"Content-Type": "application/json"},
            )
    except httpx.HTTPError:
        return JSONResponse(
            {"error": "exchange_checkout_unavailable"},
            status_code=503,
        )
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get(
            "content-type",
            "application/json",
        ),
    )


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


@app.get("/a2a/v1/discovery")
def a2a_discovery():
    return commerce_discovery_manifest(
        public_base_url=PUBLIC_BASE_URL,
        public_capability_names=[
            item["name"] for item in capability_manifest("a2a")
        ],
    )


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


@app.post("/agent-web/tools/{tool_name:path}")
def run_public_tool(tool_name: str, arguments: dict = Body(default_factory=dict)):
    allowed = {item["name"] for item in capability_manifest()}
    if tool_name not in allowed:
        return JSONResponse({"error": "unknown_public_capability"}, status_code=404)
    return execute_public_capability(tool_name, arguments or {})


@app.get("/agent-web/webmcp-manifest.json")
def webmcp_manifest_route():
    return {"version": "2026-09-15-draft", "tools": webmcp_manifest()}


@app.get("/agent-web/webmcp.js")
def webmcp_bootstrap():
    script = r'''(async () => {
  const mc = document.modelContext;
  if (!mc || !mc.registerTool) return;
  const manifest = await fetch("/agent-web/webmcp-manifest.json").then(r => r.json());
  for (const tool of manifest.tools || []) {
    mc.registerTool({
      name: tool.name,
      title: tool.title,
      description: tool.description,
      inputSchema: tool.inputSchema,
      annotations: tool.annotations,
      execute: async (args, options) => {
        const response = await fetch(`/agent-web/tools/${encodeURIComponent(tool.name)}`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(args || {}),
          signal: options.signal
        });
        if (!response.ok) throw new Error(`Empire tool failed: ${response.status}`);
        return await response.json();
      }
    }).catch(() => {});
  }
})();'''
    return Response(content=script, media_type="application/javascript")


@app.get("/sitemap.xml")
def sitemap():
    return Response(
        content=_sitemap_xml(),
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Allow: /aeo/\n"
        "Allow: /.well-known/agent-card.json\n"
        f"Sitemap: {PUBLIC_BASE_URL}/sitemap.xml\n"
    )


_PUBLIC_BRAND_ASSETS = {
    "empire-mark.svg",
    "empire-mark-mono.svg",
    "empire-logo.svg",
}


@app.get("/brand/{asset_name}")
def brand_asset(asset_name: str):
    if asset_name not in _PUBLIC_BRAND_ASSETS:
        return JSONResponse({"error": "brand_asset_not_found"}, status_code=404)
    path = SITE_OUT / "brand" / asset_name
    if not path.is_file():
        return JSONResponse({"error": "brand_asset_unavailable"}, status_code=404)
    return FileResponse(
        path,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/icon.svg")
def site_icon():
    path = SITE_OUT / "icon.svg"
    if not path.is_file():
        return JSONResponse({"error": "site_icon_unavailable"}, status_code=404)
    return FileResponse(
        path,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/favicon.ico")
def favicon():
    path = SITE_OUT / "icon.svg"
    if not path.is_file():
        return JSONResponse({"error": "site_icon_unavailable"}, status_code=404)
    return FileResponse(
        path,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/trust")
def trust_page():
    path = _site_html_path("trust")
    if path is None:
        return JSONResponse({"error": "public_site_page_unavailable"}, status_code=404)
    return FileResponse(path, media_type="text/html")


@app.get("/buy")
def buy_page():
    path = _site_html_path("buy")
    if path is None:
        return JSONResponse(
            {"error": "public_site_page_unavailable"},
            status_code=404,
        )
    return FileResponse(path, media_type="text/html")


@app.get("/industries")
def industries_page():
    path = _site_html_path("industries")
    if path is None:
        return JSONResponse({"error": "public_site_page_unavailable"}, status_code=404)
    return FileResponse(path, media_type="text/html")


@app.get("/industries/{slug}")
def industry_page(slug: str):
    path = _site_html_path(f"industries/{slug}")
    if path is None:
        return JSONResponse({"error": "industry_page_not_found"}, status_code=404)
    return FileResponse(path, media_type="text/html")


@app.get("/", response_class=HTMLResponse)
def home():
    path = _site_html_path("")
    if path is not None:
        return FileResponse(path, media_type="text/html")
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Empire AI — Predictive Revenue</title>
<meta name="description" content="Empire AI predictive revenue and agent intelligence infrastructure.">
<script src="/agent-web/webmcp.js" defer></script>
</head><body><main><h1>Empire AI</h1><p>Predictive Revenue infrastructure.</p>
<p>Human-readable, crawler-readable and agent-readable intelligence through the governed EmpireOS control plane.</p>
<nav><a href="/agent-web/capabilities">Agent Web capabilities</a> · <a href="/.well-known/agent-card.json">A2A Agent Card</a></nav>
</main></body></html>"""
