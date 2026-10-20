"""Closed-by-default consumer newsletter API, distinct from B2B lead intake.

This module does not own email encryption, immutable EmpireDB custody,
double-opt-in sends, unsubscribe providers or buyer contact exports.
Without an independently enabled private backend ALL endpoints fail closed.
No public browser consent flag can enable server-side signup.
"""
from __future__ import annotations

import re
from typing import Callable, Protocol

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from empire_os.roofing_guide_optin_contract import NOTICE

PUBLIC_ORIGIN = "https://empire-ai.co.uk"
SLUG = "roofing-cost-guide"
PURPOSE = "EMPIRE_AI_OWN_BRAND_HOMEOWNER_UPDATES"
EMAIL = re.compile(r"^[^@\s\x00-\x1f]+@[^@\s\x00-\x1f]+\.[^@\s\x00-\x1f]+$")
TOKEN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


class PrivateSubscriptionBackend(Protocol):
    """Authenticated, privately deployed adapter—not the public gateway."""

    def independently_ready(self) -> bool: ...
    def request_verification(self, *, email: str, notice_version: str,
                             consent_receipt: dict[str, str]) -> bool: ...
    def withdraw_with_token(self, *, token: str) -> None: ...


def _response(body: dict, status: int) -> JSONResponse:
    return JSONResponse(body, status_code=status,
                        headers={"Cache-Control": "no-store",
                                 "X-Robots-Tag": "noindex, nofollow"})


def create_roofing_optin_router(
    *,
    backend: PrivateSubscriptionBackend | None = None,
    limiter: Callable[[str], bool] | None = None,
) -> APIRouter:
    router = APIRouter()

    def ready() -> bool:
        # Revalidated for every request. Browser state must never decide.
        if backend is None:
            return False
        try:
            return backend.independently_ready() is True
        except Exception:
            return False

    def same_origin(request: Request) -> bool:
        return (request.headers.get("origin") == PUBLIC_ORIGIN
                and request.headers.get("sec-fetch-site", "same-origin")
                    in ("same-origin", "none"))

    async def read_json(request: Request, *, limit: int) -> dict | None:
        if request.headers.get("content-type", "").split(";", 1)[0].lower().strip() != "application/json":
            return None
        raw = await request.body()
        if len(raw) > limit:
            return None
        import json
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return None
        return value if isinstance(value, dict) else None

    @router.get("/v1/consumer-optin/roofing/status")
    async def roofing_optin_status():
        if not ready():
            return _response({"status": "OPTIN_COLLECTION_HELD"}, 503)
        return _response({
            "status": "OPTIN_COLLECTION_ENABLED",
            "notice_version": NOTICE,
            "privacy_notice_url": "/privacy",
            "subscription_product": PURPOSE,
        }, 200)

    @router.post("/v1/consumer-optin/roofing")
    async def roofing_optin_subscription(request: Request):
        if not ready():
            return _response({"status": "OPTIN_COLLECTION_HELD"}, 503)
        if not same_origin(request):
            return _response({"error": "same_origin_required"}, 403)
        if limiter is None or limiter(request.client.host if request.client else "unknown") is not True:
            return _response({"error": "rate_limited_or_unavailable"}, 429)
        payload = await read_json(request, limit=2048)
        if payload is None:
            return _response({"error": "invalid_json_content"}, 422)
        allowed = {
            "offer_slug", "email", "optional_empire_email_updates",
            "optional_named_buyer_referral", "notice_version", "website",
        }
        if set(payload) != allowed:
            return _response({"error": "unexpected_optin_fields"}, 422)
        value = payload["email"]
        if (not isinstance(value, str) or len(value) > 254
            or value != value.strip()
            or EMAIL.fullmatch(value) is None
            or len(value) < 6):
            return _response({"error": "invalid_email"}, 422)
        if (payload["offer_slug"] != SLUG or payload["notice_version"] != NOTICE
            or payload["optional_empire_email_updates"] is not True
            or payload["optional_named_buyer_referral"] is not False
            or payload["website"] != ""):
            return _response({"error": "purpose_specific_consent_required"}, 422)

        # The backend, not a browser flag, must verify the original source,
        # privacy notice, secure storage, keyed dedupe, suppressions,
        # double-opt-in confirmation delivery and retention. No raw address
        # appears in any gateway response or logs.
        try:
            accepted = backend.request_verification(
                email=value.strip(),
                notice_version=NOTICE,
                consent_receipt={
                    "offer_slug": SLUG,
                    "source": "EMPIRE_OWNED_PUBLIC_ROOFING_GUIDE",
                    "notice_version": NOTICE,
                    "own_brand_updates": "explicit_true",
                    "third_party_buyer_sharing": "explicit_false",
                },
            )
        except Exception:
            return _response({"error": "signup_temporarily_unavailable"}, 503)
        if accepted is not True:
            return _response({"error": "signup_temporarily_unavailable"}, 503)
        return _response({"status": "OPTIN_RECORDED_PENDING_VERIFICATION"}, 202)

    @router.post("/v1/consumer-optin/roofing/unsubscribe")
    async def roofing_optin_unsubscribe(request: Request):
        # A confirmed owner must implement a purpose-scoped opaque verifier.
        # Do not ever accept an email or arbitrary subscriber ID here.
        if not ready():
            return _response({"status": "OPTIN_WITHDRAWAL_SERVICE_HELD"}, 503)
        if not same_origin(request):
            return _response({"error": "same_origin_required"}, 403)
        payload = await read_json(request, limit=1024)
        if (payload is None or set(payload) != {"unsubscribe_token"}
            or not isinstance(payload["unsubscribe_token"], str)
            or TOKEN.fullmatch(payload["unsubscribe_token"]) is None):
            return _response({"error": "invalid_withdrawal_request"}, 422)
        if limiter is None or limiter(request.client.host if request.client else "unknown") is not True:
            return _response({"error": "rate_limited_or_unavailable"}, 429)
        try:
            backend.withdraw_with_token(token=payload["unsubscribe_token"])
        except Exception:
            return _response({"status": "OPTIN_WITHDRAWAL_SERVICE_UNAVAILABLE"}, 503)
        # No subscriber-existence disclosure.
        return _response({"status": "REQUEST_RECEIVED_IF_TOKEN_VALID"}, 202)

    return router
