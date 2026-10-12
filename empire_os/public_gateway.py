"""Empire AI public gateway behind Cloudflare Tunnel.

Public surface is discovery/read-mostly with narrow allowlisted commerce-intake
proxies for self-serve orders, Lead Exchange interest and Predictive Revenue
deployment interest. It deliberately
excludes settlement execution, allocation, outreach execution, buyer activation
and closer mutation endpoints.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import uuid
from pathlib import Path

import httpx
from fastapi import Body, FastAPI, Query, Request, WebSocket
from websockets.asyncio.client import connect as presence_ws_connect
from websockets.exceptions import ConnectionClosed
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from empire_os.agent_web import a2a_agent_card, capability_manifest, webmcp_manifest
from empire_os.lead_smart_public_coverage_api import router as roofing_coverage_router
from empire_os.lead_smart_pilot_call_api import router as roofing_pilot_handoff_router
from empire_os.affiliate_ingress import (
    SAFE_RESPONSE_HEADERS as AFFILIATE_SAFE_HEADERS,
    allowed_gateway_host,
    create_affiliate_ingress_router,
    reserved_affiliate_host,
)
from empire_os.a2a_discovery import commerce_discovery_manifest
from empire_os.a2a_runtime import load_a2a_runtime
from empire_os.aeo_release import released_file as released_aeo_file, released_paths as released_aeo_paths
from empire_os.a2a_identity_api import create_a2a_identity_router
from empire_os.a2a_commerce_api import create_a2a_commerce_router
from empire_os.agent_web_runtime import execute_public_capability
from empire_os.owned_campaign_http import LIMITER as FIRST_PARTY_INTAKE_LIMITER

GATEWAY_VERSION = "agent-web-v1.1"
PUBLIC_BASE_URL = os.getenv("EMPIRE_PUBLIC_BASE_URL", "https://empire-ai.co.uk").rstrip("/")
A2A_RUNTIME = load_a2a_runtime(os.environ)
AEO_ROOT = Path(os.getenv("EMPIRE_PUBLIC_AEO_ROOT", "/srv/empire_os/runtime/aeo"))
AEO_ROOT.mkdir(parents=True, exist_ok=True)
SITE_OUT = Path(os.getenv("EMPIRE_PUBLIC_SITE_OUT", "/srv/empire_os/apps/empire-public-site/out"))
TRUST_SNAPSHOT = Path("/srv/empire_os/runtime/trust/latest.json")
RESEND_INBOUND_URL = os.getenv(
    "EMPIRE_RESEND_INBOUND_URL",
    "http://127.0.0.1:8097/webhooks/resend-inbound",
).strip()
RECALL_REALTIME_URL = os.getenv(
    "EMPIRE_RECALL_REALTIME_URL",
    "http://127.0.0.1:8099/v1/providers/recall/realtime",
).strip()
RECALL_STATUS_URL = os.getenv(
    "EMPIRE_RECALL_STATUS_URL",
    "http://127.0.0.1:8099/v1/providers/recall/status",
).strip()
RECALL_LIFECYCLE_URL = os.getenv(
    "EMPIRE_RECALL_LIFECYCLE_URL",
    "http://127.0.0.1:8099/v1/providers/recall/lifecycle",
).strip()
PRESENCE_INTERNAL_URL = os.getenv(
    "EMPIRE_AVATAR_PRESENCE_INTERNAL_URL",
    "http://127.0.0.1:8100",
).rstrip("/")
PRESENCE_WS_URL = os.getenv(
    "EMPIRE_AVATAR_PRESENCE_WS_URL",
    "ws://127.0.0.1:8100/avatar/presence/ws",
).strip()
CHECKOUT_INTERNAL_URL = os.getenv(
    "EMPIRE_CHECKOUT_INTERNAL_URL",
    "http://127.0.0.1:8098",
).rstrip("/")

app = FastAPI(title="Empire AI Public Gateway", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(roofing_coverage_router)
app.include_router(roofing_pilot_handoff_router)
app.include_router(create_affiliate_ingress_router())
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
    # A separate affiliate Host may use this same FastAPI process only for
    # explicitly reserved, noncommercial paths. Never expose main-site
    # checkout, research, A2A, cookie-bearing pages or dynamic APIs there.
    if (not allowed_gateway_host(request)
            or reserved_affiliate_host(request)
            and request.url.path != "/v1/affiliate/status"
            and not request.url.path.startswith("/r/")):
        response = JSONResponse(
            status_code=404,
            content={"detail": "Not Found"},
            headers=AFFILIATE_SAFE_HEADERS,
        )
    else:
        response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/avatar/presence"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self' wss://empire-ai.co.uk "
            "wss://meeting-data.bot.recall.ai; "
            "img-src 'self' data:; media-src 'self' blob:; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
    elif (not allowed_gateway_host(request)
          or reserved_affiliate_host(request)
          or request.url.path == "/v1/affiliate/status"
          or request.url.path.startswith("/r/")):
        for name, value in AFFILIATE_SAFE_HEADERS.items():
            response.headers[name] = value
    else:
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = _site_csp(
            request.url.path
        )
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
    elif clean == "commercial":
        candidate = base / "commercial.html"
    elif clean == "predictive-revenue":
        candidate = base / "predictive-revenue.html"
    elif clean == "roofing":
        candidate = base / "roofing.html"
    elif clean.startswith("industries/"):
        slug = clean.split("/", 1)[1]
        if not slug or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in slug):
            return None
        candidate = base / "industries" / f"{slug}.html"
    else:
        return None
    return candidate if candidate.is_file() else None


_STATIC_REVIEWED_ROUTES = {
    "privacy": "privacy.html",
    "terms": "terms.html",
    "roofing/replacement-vs-repair": "roofing/replacement-vs-repair.html",
    "roofing/installation-checklist": "roofing/installation-checklist.html",
}
# This existing gateway is the only publishing surface. Absent an explicitly
# approved, exact-content release record, staged assets must return 404.
_STATIC_RELEASE_RECEIPT = Path(
    "/srv/empire_os/runtime/public_website/reviewed_content_release.json"
)
_DRAFT_COPY_MARKERS = (
    "Founder/legal review draft",
    "not an approved or effective policy",
    "Research draft",
    "This is a working draft",
    # The 12 October final-review packet has different explicit status
    # markers; exact SHA receipts must never promote a proposed notice.
    "Status: PROPOSED",
    "NOT EFFECTIVE OR PUBLISHED",
    "final review copy",
)


def _approved_static_content_path(
    route: str,
    *,
    site_root: Path | None = None,
    receipt_path: Path | None = None,
) -> Path | None:
    """Fail-closed admission for legal pages and homeowner educational guides.

    A manifest is a deployment receipt, NOT a way to generate an approval.
    No receipt is created by this code. It must be issued after founder
    sign-off, final legal/editorial review, and exact exported page inspection.
    """
    filename = _STATIC_REVIEWED_ROUTES.get(route)
    if not filename:
        return None
    page = (site_root or SITE_OUT) / filename
    try:
        receipt = json.loads(
            (receipt_path or _STATIC_RELEASE_RECEIPT).read_text(encoding="utf-8")
        )
        if (
            not isinstance(receipt, dict)
            or receipt.get("schema_version") != "empire.public-reviewed-content.v1"
            or receipt.get("founder_publication_authorized") is not True
            or receipt.get("founder_approval_ref") in (None, "")
            or receipt.get("legal_review_complete") is not True
            or receipt.get("legal_review_ref") in (None, "")
            or receipt.get("privacy_request_handling_verified") is not True
            or receipt.get("source_lane") != "OWNED_FIRST_PARTY_US_HOMEOWNER"
            or receipt.get("indexation_enabled") is not False
            or receipt.get("live_call_enabled") is not False
            or receipt.get("execution_authority") != "none"
        ):
            return None
        digests = receipt.get("approved_page_sha256")
        if not isinstance(digests, dict) or route not in digests:
            return None
        if route.startswith("roofing/"):
            if (
                not receipt.get("buyer_landing_page_approved") is True
                or not receipt.get("buyer_approval_ref")
                or receipt.get("content_quality_review_complete") is not True
                or not receipt.get("content_quality_review_ref")
                or not all(p in digests for p in ("privacy", "terms"))
            ):
                return None
        for review_route in ("privacy", "terms") if route.startswith("roofing/") else (route,):
            if review_route not in digests:
                return None
            policy_path = (site_root or SITE_OUT) / _STATIC_REVIEWED_ROUTES[review_route]
            policy_html = policy_path.read_text(encoding="utf-8")
            if (
                any(marker in policy_html for marker in _DRAFT_COPY_MARKERS)
                or hashlib.sha256(policy_html.encode("utf-8")).hexdigest()
                != digests[review_route]
            ):
                return None
        html = page.read_text(encoding="utf-8")
        expected = digests[route]
        if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            return None
        if (
            any(marker in html for marker in _DRAFT_COPY_MARKERS)
            or hashlib.sha256(html.encode("utf-8")).hexdigest() != expected
        ):
            return None
        return page
    except (OSError, UnicodeDecodeError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _public_site_urls(root: Path | None = None) -> list[str]:
    base = root or SITE_OUT
    urls: list[str] = []
    if (base / "trust.html").is_file():
        urls.append(f"{PUBLIC_BASE_URL}/trust")
    if (base / "industries.html").is_file():
        urls.append(f"{PUBLIC_BASE_URL}/industries")
    if (base / "buy.html").is_file():
        urls.append(f"{PUBLIC_BASE_URL}/buy")
    if (base / "commercial.html").is_file():
        urls.append(f"{PUBLIC_BASE_URL}/commercial")
    if (base / "predictive-revenue.html").is_file():
        urls.append(f"{PUBLIC_BASE_URL}/predictive-revenue")
    from empire_os.owned_campaign_release import released_paths
    if root is None:
        urls.extend(f"{PUBLIC_BASE_URL}{path}" for path in released_paths())
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
    if root is not None:
        urls: list[str] = []
        for path in sorted(root.glob("*/*/index.html")):
            rel = path.relative_to(root)
            if len(rel.parts) != 3 or rel.parts[2] != "index.html":
                continue
            urls.append(f"{PUBLIC_BASE_URL}/aeo/{rel.parts[0]}/{rel.parts[1]}/")
        return urls
    return [f"{PUBLIC_BASE_URL}{path}" for path in released_aeo_paths()]


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
        "execution": "read-mostly-with-narrow-commerce-intake",
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


@app.post("/v1/providers/recall/realtime")
async def recall_realtime_proxy(request: Request):
    raw = await request.body()
    if len(raw) > 512_000:
        return JSONResponse({"ok": False}, status_code=413)

    allowed_headers = {
        "content-type",
        "webhook-id",
        "webhook-timestamp",
        "webhook-signature",
        "svix-id",
        "svix-timestamp",
        "svix-signature",
    }
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() in allowed_headers
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                RECALL_REALTIME_URL,
                content=raw,
                headers=headers,
            )
    except httpx.HTTPError:
        return JSONResponse(
            {"ok": False, "error": "recall_realtime_unavailable"},
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


@app.post("/v1/providers/recall/status")
async def recall_status_proxy(request: Request):
    raw = await request.body()
    if len(raw) > 512_000:
        return JSONResponse({"ok": False}, status_code=413)

    allowed_headers = {
        "content-type",
        "webhook-id",
        "webhook-timestamp",
        "webhook-signature",
        "svix-id",
        "svix-timestamp",
        "svix-signature",
    }
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() in allowed_headers
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                RECALL_STATUS_URL,
                content=raw,
                headers=headers,
            )
    except httpx.HTTPError:
        return JSONResponse(
            {"ok": False, "error": "recall_status_unavailable"},
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


@app.post("/v1/providers/recall/lifecycle")
async def recall_lifecycle_proxy(request: Request):
    raw = await request.body()
    if len(raw) > 512_000:
        return JSONResponse({"ok": False}, status_code=413)

    allowed_headers = {
        "content-type",
        "webhook-id",
        "webhook-timestamp",
        "webhook-signature",
        "svix-id",
        "svix-timestamp",
        "svix-signature",
    }
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() in allowed_headers
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                RECALL_LIFECYCLE_URL,
                content=raw,
                headers=headers,
            )
    except httpx.HTTPError:
        return JSONResponse(
            {"ok": False, "error": "recall_lifecycle_unavailable"},
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


@app.get("/v1/checkout/commercial/offers")
async def checkout_commercial_offers_proxy():
    # Public metadata only: no checkout/payment/activation authority.
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"{CHECKOUT_INTERNAL_URL}/v1/commercial/offers"
            )
    except httpx.HTTPError:
        return JSONResponse({"error": "commercial_offers_unavailable"},
                            status_code=503)
    return Response(
        response.content, status_code=response.status_code,
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/v1/checkout/commercial/interests")
async def checkout_commercial_interest_proxy(request: Request):
    # Reuse existing first-party rate-limiting and same-origin rules.
    # IP-derived state is ephemeral abuse protection, never a buyer identity.
    deny = {"Cache-Control": "no-store"}
    if (request.headers.get("origin") != PUBLIC_BASE_URL
            or request.headers.get("sec-fetch-site", "same-origin")
            not in {"same-origin", "none"}):
        return JSONResponse({"error": "same_origin_required"},
                            status_code=403, headers=deny)
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        return JSONResponse({"error": "json_required"},
                            status_code=415, headers=deny)
    peer = request.client.host if request.client else "unknown"
    if not FIRST_PARTY_INTAKE_LIMITER.allow(peer, "enquiry"):
        return JSONResponse({"error": "rate_limited"},
                            status_code=429, headers=deny)
    raw = await request.body()
    if len(raw) > 12_000:
        return JSONResponse({"error": "commercial_enquiry_too_large"},
                            status_code=413, headers=deny)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{CHECKOUT_INTERNAL_URL}/v1/commercial/interests",
                content=raw, headers={"Content-Type": "application/json"},
            )
    except httpx.HTTPError:
        return JSONResponse({"error": "commercial_enquiry_unavailable"},
                            status_code=503, headers=deny)
    return Response(
        response.content, status_code=response.status_code,
        media_type="application/json",
        headers=deny,
    )


@app.get("/v1/checkout/predictive-revenue/products")
async def checkout_predictive_revenue_products_proxy():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{CHECKOUT_INTERNAL_URL}/v1/predictive-revenue/products"
            )
    except httpx.HTTPError:
        return JSONResponse(
            {"error": "predictive_revenue_checkout_unavailable"},
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


@app.post("/v1/checkout/predictive-revenue/interests")
async def checkout_predictive_revenue_interest_proxy(request: Request):
    raw = await request.body()
    if len(raw) > 65_536:
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
                f"{CHECKOUT_INTERNAL_URL}/v1/predictive-revenue/interests",
                content=raw,
                headers={"Content-Type": "application/json"},
            )
    except httpx.HTTPError:
        return JSONResponse(
            {"error": "predictive_revenue_checkout_unavailable"},
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


app.include_router(
    create_a2a_identity_router(
        verifier=A2A_RUNTIME.verifier,
        trusted_key_ids=A2A_RUNTIME.trusted_key_ids,
        nonce_registry=A2A_RUNTIME.nonce_registry,
    )
)
app.include_router(
    create_a2a_commerce_router(
        verifier=A2A_RUNTIME.verifier,
        trusted_key_ids=A2A_RUNTIME.trusted_key_ids,
        repository=A2A_RUNTIME.repository,
        nonce_registry=A2A_RUNTIME.nonce_registry,
    )
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
        authentication_status=A2A_RUNTIME.authentication_status,
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



@app.get("/aeo/{niche}/{metro}/")
@app.get("/aeo/{niche}/{metro}")
def released_aeo_page(niche: str, metro: str):
    path = released_aeo_file(niche, metro)
    if path is None:
        return JSONResponse(
            {"error": "aeo_page_unpublished"},
            status_code=404,
            headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
        )
    return FileResponse(
        path,
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=900", "X-Robots-Tag": "index, follow"},
    )

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


@app.get("/roofing")
def roofing_page():
    path = _site_html_path("roofing")
    if path is None:
        return JSONResponse({"error": "roofing_page_unavailable"}, status_code=404)
    return FileResponse(path, media_type="text/html", headers={"X-Robots-Tag": "noindex, nofollow", "Cache-Control": "no-store"})

@app.get("/privacy")
def public_privacy_policy():
    path = _approved_static_content_path("privacy")
    if path is None:
        return JSONResponse(
            {"error": "policy_not_released"}, status_code=404,
            headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
        )
    return FileResponse(path, media_type="text/html", headers={
        "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow",
    })


@app.get("/terms")
def public_website_terms():
    path = _approved_static_content_path("terms")
    if path is None:
        return JSONResponse(
            {"error": "terms_not_released"}, status_code=404,
            headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
        )
    return FileResponse(path, media_type="text/html", headers={
        "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow",
    })


@app.get("/roofing/{guide_slug}")
def public_roofing_guide(guide_slug: str):
    # Explicit finite allowlist; no user-controlled filesystem path.
    if guide_slug not in {"replacement-vs-repair", "installation-checklist"}:
        return JSONResponse(
            {"error": "roofing_guide_not_released"}, status_code=404,
            headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
        )
    path = _approved_static_content_path("roofing/" + guide_slug)
    if path is None:
        return JSONResponse(
            {"error": "roofing_guide_not_released"}, status_code=404,
            headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
        )
    return FileResponse(path, media_type="text/html", headers={
        "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow",
    })


@app.get("/roofing-hero.webp")
def roofing_hero():
    path = SITE_OUT / "roofing-hero.webp"
    if not path.is_file():
        return JSONResponse({"error": "roofing_image_unavailable"}, status_code=404)
    return FileResponse(path, media_type="image/webp")


@app.get("/trust")
def trust_page():
    path = _site_html_path("trust")
    if path is None:
        return JSONResponse({"error": "public_site_page_unavailable"}, status_code=404)
    return FileResponse(path, media_type="text/html")


@app.get("/predictive-revenue")
def predictive_revenue_page():
    path = _site_html_path("predictive-revenue")
    if path is None:
        return JSONResponse(
            {"error": "public_site_page_unavailable"},
            status_code=404,
        )
    return FileResponse(path, media_type="text/html")


@app.get("/contact")
@app.get("/consultancy")
@app.get("/digital-avatar")
@app.get("/sales")
def founder_led_sales_redirect():
    # Known legacy/navigational commercial paths now resolve to a single
    # safe first-party consent-bound enquiry journey.
    return RedirectResponse("/commercial", status_code=308)


@app.get("/commercial")
def commercial_page():
    path = _site_html_path("commercial")
    if path is None:
        return JSONResponse({"error": "commercial_page_unavailable"},
                            status_code=404)
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


# Existing gateway owns these routes; no second service or autonomous publisher.
@app.get('/research/{campaign_id}')
def research_page(campaign_id: str):
    from empire_os.owned_campaign_release import released_html
    html = released_html(campaign_id)
    if html is None:
        return JSONResponse({'error': 'research_page_unpublished'}, status_code=404,
                            headers={'Cache-Control': 'no-store'})
    return HTMLResponse(html, headers={'Cache-Control': 'no-store'})


@app.get('/research-runtime.js')
def research_runtime_script():
    from empire_os.owned_campaign_release import load_release, ROOT, SCRIPT
    if load_release() is None:
        return JSONResponse({'error': 'research_runtime_unpublished'}, status_code=404)
    return Response((ROOT / SCRIPT).read_bytes(), media_type='application/javascript',
                    headers={'Cache-Control': 'no-store'})


@app.post('/api/research/enquiry')
async def research_enquiry(request: Request):
    from empire_os.owned_campaign_http import handle_intake
    return await handle_intake(request, 'enquiry', origin=PUBLIC_BASE_URL)


@app.post('/api/research/event')
async def research_event(request: Request):
    from empire_os.owned_campaign_http import handle_intake
    return await handle_intake(request, 'event', origin=PUBLIC_BASE_URL)


# NOTE: Presence routes are intentionally exact allowlisted paths. They proxy to
# the loopback Digital Avatar Presence service and grant no execution authority.
async def _avatar_presence_http_proxy(
    request: Request,
    *,
    internal_path: str,
) -> Response:
    headers = {}
    cookie = request.headers.get("cookie")
    if cookie:
        headers["cookie"] = cookie
    accept = request.headers.get("accept")
    if accept:
        headers["accept"] = accept
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            upstream = await client.get(
                f"{PRESENCE_INTERNAL_URL}{internal_path}",
                params=list(request.query_params.multi_items()),
                headers=headers,
            )
    except httpx.HTTPError:
        return JSONResponse(
            {"ok": False, "error": "avatar_presence_unavailable"},
            status_code=503,
        )

    forwarded = {}
    for name in (
        "content-type",
        "set-cookie",
        "cache-control",
        "pragma",
        "referrer-policy",
    ):
        value = upstream.headers.get(name)
        if value:
            forwarded[name] = value
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=forwarded,
    )


@app.get("/avatar/presence")
async def avatar_presence_page_proxy(request: Request):
    return await _avatar_presence_http_proxy(
        request,
        internal_path="/avatar/presence",
    )


@app.get("/avatar/presence/runtime.js")
async def avatar_presence_runtime_js_proxy(request: Request):
    return await _avatar_presence_http_proxy(
        request,
        internal_path="/avatar/presence/runtime.js",
    )


@app.get("/avatar/presence/runtime.css")
async def avatar_presence_runtime_css_proxy(request: Request):
    return await _avatar_presence_http_proxy(
        request,
        internal_path="/avatar/presence/runtime.css",
    )


@app.websocket("/avatar/presence/ws")
async def avatar_presence_ws_proxy(websocket: WebSocket):
    # Affiliate Host never inherits our private avatar WebSocket proxy.
    if not allowed_gateway_host(websocket) or reserved_affiliate_host(websocket):
        await websocket.close(code=4404)
        return
    cookie = str(websocket.headers.get("cookie") or "").strip()
    if not cookie or "empire_avatar_presence=" not in cookie:
        await websocket.close(
            code=4401,
            reason="presence_cookie_required",
        )
        return

    accepted = False
    try:
        async with presence_ws_connect(
            PRESENCE_WS_URL,
            additional_headers={"cookie": cookie},
            proxy=None,
            open_timeout=5.0,
            close_timeout=2.0,
            max_size=262_144,
            max_queue=16,
        ) as upstream:
            await websocket.accept()
            accepted = True

            async def client_to_presence():
                while True:
                    message = await websocket.receive()
                    message_type = message.get("type")
                    if message_type == "websocket.disconnect":
                        return
                    text_value = message.get("text")
                    if text_value is None:
                        # Browser Presence protocol is JSON text only.
                        await websocket.close(
                            code=4400,
                            reason="presence_text_frames_required",
                        )
                        return
                    if len(text_value.encode("utf-8")) > 262_144:
                        await websocket.close(
                            code=4409,
                            reason="presence_frame_too_large",
                        )
                        return
                    await upstream.send(text_value)

            async def presence_to_client():
                try:
                    async for message in upstream:
                        if isinstance(message, bytes):
                            # Loopback Presence protocol must remain JSON text.
                            await websocket.close(
                                code=1011,
                                reason="presence_upstream_protocol_invalid",
                            )
                            return
                        if len(message.encode("utf-8")) > 262_144:
                            await websocket.close(
                                code=1011,
                                reason="presence_upstream_frame_too_large",
                            )
                            return
                        await websocket.send_text(message)
                except ConnectionClosed:
                    return

            client_task = asyncio.create_task(client_to_presence())
            upstream_task = asyncio.create_task(presence_to_client())
            done, pending = await asyncio.wait(
                {client_task, upstream_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(
                    *pending,
                    return_exceptions=True,
                )
            for task in done:
                exception = task.exception()
                if exception is not None:
                    raise exception
    except Exception:
        try:
            await websocket.close(
                code=1011,
                reason="presence_upstream_unavailable",
            )
        except RuntimeError:
            pass
        return

    if accepted:
        try:
            await websocket.close(code=1000)
        except RuntimeError:
            pass
