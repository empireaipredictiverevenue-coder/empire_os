"""Prepared secure buyer status HTTP route; NEVER mounted by default.

The public gateway must separately approve and include this router after
dedicated reader login, origin, abuse, HTTPS and settlement gates are proven.
Raw tokens are accepted only in POST JSON bodies, never URLs or logs.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from empire_os.direct_bsc_buyer_status import BuyerAccessDenied, TOKEN_RE
from empire_os.direct_bsc_buyer_status_private_reader import (
    project_private_buyer_status,
)

HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}
MAX_BODY=160


def _decode_pairs(pairs: list[tuple[str,Any]]) -> dict:
    obj={}
    for key,value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON member")
        obj[key]=value
    return obj


def create_private_buyer_status_router(
    *,
    origin: str,
    authorized: Callable[[], bool],
    allow_request: Callable[[str], bool],
    hmac_key: bytes,
    read_by_fingerprint: Callable[[str], Mapping[str,Any]|None],
    approved_treasury: str,
    now: Callable[[], datetime]|None=None,
) -> APIRouter:
    """Dependencies explicit, no live credentials imported or read."""
    router=APIRouter()
    clock = now or (lambda: datetime.now(timezone.utc))

    @router.post("/v1/checkout/payment-status")
    async def buyer_status(request: Request):
        try:
            enabled = authorized() is True
        except Exception:
            enabled = False
        if not enabled:
            return JSONResponse({"error":"buyer_status_unavailable"},
                                status_code=503,headers=HEADERS)
        if request.headers.get("content-type","").split(";",1)[0].strip().lower()!="application/json":
            return JSONResponse({"error":"application_json_required"},
                                status_code=415,headers=HEADERS)
        if (request.headers.get("origin") != origin or
            request.headers.get("sec-fetch-site","same-origin")
            not in {"same-origin","none"}):
            return JSONResponse({"error":"same_origin_required"},
                                status_code=403,headers=HEADERS)
        peer=request.client.host if request.client else "unknown"
        try:
            admitted=allow_request(peer)
        except Exception:
            admitted=False
        if not admitted:
            return JSONResponse({"error":"buyer_status_unavailable"},
                                status_code=429,headers=HEADERS)
        body=bytearray()
        async for part in request.stream():
            if len(part)>MAX_BODY-len(body):
                return JSONResponse({"error":"buyer_status_unavailable"},
                                    status_code=413,headers=HEADERS)
            body.extend(part)
        try:
            payload=json.loads(bytes(body),object_pairs_hook=_decode_pairs)
            if (type(payload) is not dict or set(payload)!={"token"}
                or type(payload["token"]) is not str or
                TOKEN_RE.fullmatch(payload["token"]) is None):
                raise ValueError("invalid")
            result=project_private_buyer_status(
                bearer_token=payload["token"],
                hmac_key=hmac_key,
                read_by_fingerprint=read_by_fingerprint,
                approved_treasury=approved_treasury,now=clock(),
            )
            return JSONResponse(result,status_code=200,headers=HEADERS)
        except Exception:
            # Identical denial irrespective of token validity, buyer,
            # database row existence or internal failure.
            return JSONResponse({"error":"payment_status_unavailable"},
                                status_code=404,headers=HEADERS)
    return router
