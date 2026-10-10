"""Host-isolated, fail-closed affiliate ingress for the existing FastAPI gateway.

Affiliate link verification is prepared by empire_os.affiliate_tracking.
This module intentionally exposes NO referral forwarding, click ingestion,
registration, consumer data collection or commercial authority.
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from empire_os.affiliate_tracking import (
    AffiliateBinding,
    verify_tracking_token,
)

AFFILIATE_HOST = "partners.empire-ai.co.uk"
INGRESS_SCHEMA = "empire.affiliate_ingress_review.v1"
ALLOWLISTED_PREVIEW_PATHS = {
    "PUBLISHER_PPC": "/roofing",
    "PUBLISHER_PPL": "/roofing",
    "SAAS_REFERRAL": "/buy",
}
SAFE_RESPONSE_HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
    "X-Robots-Tag": "noindex, nofollow",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'none'; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'none'"
    ),
}


def raw_request_host(request: Request) -> str | None:
    """Reject duplicate Host fields and malformed authorities.

    Never trust X-Forwarded-Host, Forwarded or a query parameter to select
    publisher identity or an approval scope.
    """
    host_values = [
        value for name, value in request.scope.get("headers", ())
        if name.lower() == b"host"
    ]
    if len(host_values) != 1:
        return None
    try:
        authority = host_values[0].decode("ascii").lower()
    except UnicodeDecodeError:
        return None
    if not re.fullmatch(r"[a-z0-9.-]+(?::(?:80|443))?", authority):
        return None
    return authority.removesuffix(":443").removesuffix(":80")


def is_affiliate_host(request: Request) -> bool:
    return raw_request_host(request) == AFFILIATE_HOST


def reserved_affiliate_host(request: Request) -> bool:
    """Reserve this hostname even if duplicate Host fields are supplied."""
    for name, value in request.scope.get("headers", ()):
        if name.lower() != b"host":
            continue
        try:
            if value.decode("ascii").split(":", 1)[0].lower() == AFFILIATE_HOST:
                return True
        except UnicodeDecodeError:
            continue
    return False


def allowed_gateway_host(request: Request) -> bool:
    """Keep unrelated Host values away from the primary website and APIs."""
    return raw_request_host(request) in {
        AFFILIATE_HOST,
        "empire-ai.co.uk",
        "www.empire-ai.co.uk",
        "127.0.0.1",
        "localhost",
        "testserver",  # Starlette TestClient; not a tunnel hostname.
    }


def _unavailable() -> JSONResponse:
    # Identical outward answer for all tokens: no enumeration, no reflection.
    return JSONResponse(
        status_code=404,
        content={"detail": "Not Found"},
        headers=SAFE_RESPONSE_HEADERS,
    )


def review_affiliate_ingress(
    *,
    binding: AffiliateBinding,
    token: str,
    signing_key: bytes,
    now: Any,
    host: str,
    durable_writer_verified: bool = False,
    source_reader_verified: bool = False,
) -> dict[str, Any]:
    """Pure trusted-backend readiness assessment. Does not allow redirects.

    Even a valid cryptographic signature and all in-memory approval flags
    cannot replace the canonical tenant/source lookup and globally durable
    click writer.
    """
    if host != AFFILIATE_HOST:
        raise ValueError("affiliate host mismatch")
    verified = verify_tracking_token(
        token, binding, hmac_key=signing_key, now=now
    )
    if type(durable_writer_verified) is not bool:
        raise ValueError("durable_writer_verified must be boolean")
    if type(source_reader_verified) is not bool:
        raise ValueError("source_reader_verified must be boolean")
    blockers = set(binding.blockers())
    if not source_reader_verified:
        blockers.add("trusted_canonical_source_lookup_missing")
    if not durable_writer_verified:
        blockers.add("idempotent_canonical_click_writer_missing")
    # A pure review is deliberately not the approval source for live links.
    blockers.add("live_affiliate_dispatch_not_authorized")
    return {
        "schema_version": INGRESS_SCHEMA,
        "mode": "OBSERVE",
        "source_ref": verified["source_ref"],
        "tenant_ref": verified["tenant_ref"],
        "programme_ref": verified["programme_ref"],
        "offer_format": verified["offer_format"],
        "candidate_same_origin_path": ALLOWLISTED_PREVIEW_PATHS[
            verified["offer_format"]
        ],
        "signed_tracking_token_verified": True,
        "blockers": sorted(blockers),
        "approved_destination_resolved": False,
        "redirect_allowed": False,
        "click_saved": False,
        "consumer_data_collected": False,
        "commission_payable": False,
        "execution_authority": "none",
    }


def create_affiliate_ingress_router() -> APIRouter:
    """For an existing app; no new public endpoint process or timer."""
    router = APIRouter(tags=["affiliate-tracking"])

    @router.api_route("/v1/affiliate/status", methods=["GET", "HEAD"])
    def affiliate_status(request: Request):
        if not is_affiliate_host(request):
            return _unavailable()
        return JSONResponse(
            status_code=200,
            content={
                "schema_version": INGRESS_SCHEMA,
                "status": "PREACTIVATION",
                "tracking_enabled": False,
                "publisher_registration_enabled": False,
                "live_referrals_enabled": False,
                "click_storage_enabled": False,
                "conversion_postback_enabled": False,
                "payout_enabled": False,
                "execution_authority": "none",
            },
            headers=SAFE_RESPONSE_HEADERS,
        )

    @router.api_route("/r/{tracking_token}", methods=["GET", "HEAD"])
    def tracked_referral(request: Request, tracking_token: str):
        # Do not consume, log, decode or echo the presented token. Until an
        # approved per-tenant EmpireDB resolver and durable event writer
        # exist, *all* referral attempts return the identical 404.
        return _unavailable()

    return router
