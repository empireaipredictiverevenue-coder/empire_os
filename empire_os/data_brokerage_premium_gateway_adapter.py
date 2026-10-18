"""Reviewable first-party gateway adapter for two unpriced Data Brokerage enquiries.

No production code imports or mounts this router. A separate explicit
integration release must provide confirmed publisher approval, installed
private checkout route, owned gateway rate limiter and the fixed forwarder.
Never pass a DB credential or expose the internal RPC through the gateway.
"""
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from empire_os.data_brokerage_premium_enquiry import (
    DISCOVERY,ORIGIN,MAX_BODY_BYTES,SCHEMA,discovery_catalog,
)

PUBLIC_PATH="/v1/checkout/brokerage/premium-discovery"
PRIVATE_PATH="/v1/brokerage/premium-discovery"
PRIVATE_LOOPBACK_URL="http://127.0.0.1:8098"+PRIVATE_PATH
MAX_INTERNAL_RESPONSE_BYTES=4096
SCHEMA_GATEWAY="empire.data_brokerage.gateway_candidate.v1"
RECEIPT_RE=re.compile(r"^[a-f0-9]{20}$")
Forward = Callable[[bytes], Awaitable[tuple[int, dict[str,Any]]]]

def safe_public_discovery_catalog()->dict[str,Any]:
    """Two displayable discovery choices; never expose draft prices/SKUs."""
    original=discovery_catalog()
    assert original["status"]=="UNPRICED_DISCOVERY_ONLY_NOT_PUBLICLY_PUBLISHED"
    options=[]
    for o in original["offers"]:
        code=o["product_code"]
        if code not in DISCOVERY or o["approved_price_cents"] is not None:
            raise ValueError("UNAPPROVED_PUBLIC_DISCOVERY_CONTENT")
        options.append({
            "product_code":code,
            "title":o["title"],
            "buyer_problem":o["buyer_problem"],
            "price_state":"DISCUSS_CUSTOM_SCOPE",
            "public_approved_price_available":False,
            "request_type":"NONBINDING_FOUNDER_ENQUIRY",
            "checkout_enabled":False,
        })
    return {
        "schema_version":SCHEMA_GATEWAY,
        "status":"UNPRICED_DISCOVERY_CHOICES_NONBINDING",
        "count":len(options),
        "offers":options,
        "marketing_consent_included":False,
        "customer_delivery_enabled":False,
        "binding_terms_ready":False,
        "payment_authorized":False,
    }

async def forward_to_private_checkout(raw:bytes)->tuple[int,dict[str,Any]]:
    """Fixed loopback POST only; no cookies, arbitrary URLs or auth propagation.

    Intended for a separately approved mounted private route. Does not call
    checkout while the adapter remains unmounted.
    """
    if type(raw) is not bytes or len(raw)>MAX_BODY_BYTES:
        raise ValueError("INVALID_BOUNDED_PREMIUM_REQUEST")
    async with httpx.AsyncClient(
        timeout=10.0,follow_redirects=False,trust_env=False
    ) as client:
        result=await client.post(
            PRIVATE_LOOPBACK_URL,
            content=raw,
            headers={
                "Content-Type":"application/json",
                "Origin":ORIGIN,
                "Sec-Fetch-Site":"same-origin",
            },
        )
    if len(result.content)>MAX_INTERNAL_RESPONSE_BYTES:
        raise ValueError("PRIVATE_CHECKOUT_RESPONSE_OVERSIZED")
    if "application/json" not in result.headers.get("content-type","").lower():
        raise ValueError("PRIVATE_CHECKOUT_RESPONSE_NOT_JSON")
    payload=result.json()
    if type(payload) is not dict:
        raise ValueError("PRIVATE_CHECKOUT_RESPONSE_NOT_OBJECT")
    return result.status_code,payload

def _safe_confirmed_receipt(
    raw:Mapping[str,Any],expected_code:str,
)->dict[str,Any]|None:
    if (raw.get("schema_version")!=SCHEMA
        or raw.get("decision")!="commercial_enquiry_recorded"
        or raw.get("product_code")!=expected_code
        or type(raw.get("reference")) is not str
        or RECEIPT_RE.fullmatch(raw["reference"]) is None
        or raw.get("next_step")!="FOUNDER_PRIVATE_SCOPE_REVIEW"
        or raw.get("execution_authority")!="none"
        or raw.get("payment_or_revenue_verified") is not False
        or raw.get("subscription_created") is not False
        or raw.get("terms_binding") is not False
        or raw.get("automatic_followup_sent") is not False
        or raw.get("buyer_identity_qualified") is not False
        or raw.get("contact_permission_scope")!="THIS_ENQUIRY_ONLY"):
        return None
    return {
        "decision":"commercial_enquiry_recorded",
        "product_code":expected_code,
        "reference":raw["reference"],
        "next_step":"FOUNDER_PRIVATE_SCOPE_REVIEW",
        "binding_terms_ready":False,
        "payment_action":False,
        "revenue_recognized":False,
    }

def make_reviewed_public_premium_gateway_router(
    *,rate_limiter:Callable[[str,str],bool],
    forward:Forward,
    founder_release_approved:bool=False,
    existing_private_checkout_route_verified:bool=False,
    astra_frontend_review_complete:bool=False,
)->APIRouter:
    """Fail closed: **not called** by production gateway.

    All three release controls must be separately true to create a routable
    candidate. This is an adapter/integration-test interface, NOT a systemd
    or release-script activation capability.
    """
    if not (founder_release_approved is True
            and existing_private_checkout_route_verified is True
            and astra_frontend_review_complete is True
            and callable(rate_limiter)
            and callable(forward)):
        raise ValueError("PREMIUM_PUBLIC_ROUTE_RELEASE_AUTHORITY_HOLD")
    router=APIRouter()

    @router.get(PUBLIC_PATH)
    async def get_premium_discovery():
        return JSONResponse(
            safe_public_discovery_catalog(),
            headers={"Cache-Control":"no-store"},
        )

    @router.post(PUBLIC_PATH)
    async def post_premium_discovery(req:Request):
        h={"Cache-Control":"no-store"}
        if (req.headers.get("origin")!=ORIGIN
            or req.headers.get("sec-fetch-site","same-origin")
               not in {"same-origin","none"}):
            return JSONResponse({"error":"same_origin_required"},
                                status_code=403,headers=h)
        if req.headers.get("content-type","").split(";",1)[0].strip().lower()!="application/json":
            return JSONResponse({"error":"json_required"},
                                status_code=415,headers=h)
        length=req.headers.get("content-length")
        if length is not None:
            try: n=int(length)
            except ValueError: n=-1
            if n<0 or n>MAX_BODY_BYTES:
                return JSONResponse({"error":"request_too_large_or_invalid"},
                                    status_code=413,headers=h)
        peer=req.client.host if req.client else "unknown"
        if rate_limiter(peer,"enquiry") is not True:
            return JSONResponse({"error":"rate_limited"},
                                status_code=429,headers=h)
        raw=await req.body()
        if not raw or len(raw)>MAX_BODY_BYTES:
            return JSONResponse({"error":"invalid_or_oversized_request"},
                                status_code=413,headers=h)
        # Pre-validate only a bounded JSON payload before forwarding PII.
        try:
            request_data=json.loads(raw)
            if type(request_data) is not dict:
                raise ValueError("NOT_OBJECT")
            expected_code=request_data.get("product_code")
            if type(expected_code) is not str or expected_code not in DISCOVERY:
                return JSONResponse({"error":"unsupported_discovery_option"},
                                    status_code=422,headers=h)
            if type(request_data.get("contact_consent")) is not bool or request_data["contact_consent"] is not True:
                return JSONResponse({"error":"specific_response_consent_required"},
                                    status_code=422,headers=h)
            if request_data.get("website","") != "":
                return JSONResponse({"error":"invalid_submission"},
                                    status_code=422,headers=h)
            # Avoid PII disclosure to private service on injected client
            # financial authority fields. Pydantic at private service also
            # forbids extras and validates the complete request.
            allowed={
                "product_code","business_name","email","domain","industry",
                "geography","desired_outcome","contact_consent",
                "idempotency_key","website",
            }
            if set(request_data)-allowed:
                return JSONResponse({"error":"unsupported_enquiry_fields"},
                                    status_code=422,headers=h)
        except (ValueError,UnicodeDecodeError):
            return JSONResponse({"error":"invalid_json"},
                                status_code=422,headers=h)
        try:
            status,response=await forward(raw)
        except Exception:
            return JSONResponse({"error":"premium_discovery_unavailable"},
                                status_code=503,headers=h)
        if status==422:
            # Do not reflect internal SQL/debug strings, credentials or PII.
            return JSONResponse({"error":"invalid_discovery_request"},
                                status_code=422,headers=h)
        if status!=200 or type(response) is not dict:
            return JSONResponse({"error":"premium_discovery_unavailable"},
                                status_code=503,headers=h)
        receipt=_safe_confirmed_receipt(response,expected_code)
        if receipt is None:
            return JSONResponse({"error":"premium_discovery_confirmation_unavailable"},
                                status_code=503,headers=h)
        return JSONResponse(receipt,status_code=200,headers=h)
    return router
