"""Existing ASTRA website single-page post-release HTTP readback.

Never deploys or grants authorisation. Invoked only AFTER the original owner
has independently approved and staged the exact noindex Chicago release.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, HTTPRedirectHandler, build_opener

from empire_os.owned_campaign_release import released_html, released_paths
from empire_os.microsite_original_gateway_addendum_v12 import (
    CAMPAIGN_ID, original_owner_chicago_html,
)

ORIGIN = "https://empire-ai.co.uk"
Fetcher = Callable[[str, str], tuple[int, dict[str, str], bytes]]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _http_read(url: str, method: str) -> tuple[int, dict[str, str], bytes]:
    if not url.startswith(ORIGIN + "/research/"):
        raise ValueError("Only the canonical first-party research URL is accepted")
    if method not in ("GET", "HEAD"):
        raise ValueError("Only GET and HEAD are permitted")
    req = Request(url, method=method, headers={
        "Accept-Encoding": "identity",
        "User-Agent": "Empire-AI-original-owner-postrelease-verifier/1",
    })
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            # Never treat a redirect (even a canonical-looking one) as proof
            # the exact original first-party page was served.
            return None

    with build_opener(NoRedirect()).open(req, timeout=12) as resp:
        return (
            resp.status,
            {k.lower(): v for k, v in resp.headers.items()},
            resp.read(8500001),
        )


def verify_original_owner_site_readback(
    root: Path,
    *,
    fetcher: Fetcher = _http_read,
) -> dict[str, Any]:
    """Verify original 5 and one newly *actually served* page, no writes.

    An owner-issued release receipt and exact original local staged file
    must already exist; a draft PR alone cannot trigger remote HTTP calls.
    """
    root = Path(root)
    local = original_owner_chicago_html(CAMPAIGN_ID, root=root)
    if local is None:
        raise ValueError("No original-owner-approved staged Chicago export")
    five = released_paths(root)
    if not isinstance(five, list) or len(five) != 5 or len(set(five)) != 5:
        raise ValueError("Original five released paths have changed")
    paths = sorted(five)
    if f"/research/{CAMPAIGN_ID}" in paths:
        raise ValueError("Original five-release manifest was improperly modified")

    all_assets: list[tuple[str, bytes]] = []
    for path in paths:
        existing = released_html(path.rsplit("/", 1)[-1], root=root)
        if not isinstance(existing, str):
            raise ValueError("Existing original asset is unavailable")
        all_assets.append((path, existing.encode("utf-8")))
    all_assets.append((f"/research/{CAMPAIGN_ID}", local.encode("utf-8")))

    verified = []
    for path, expected in all_assets:
        url = ORIGIN + path
        status, headers, body = fetcher(url, "GET")
        if status != 200 or len(body) > 8500000 or body != expected:
            raise ValueError(f"Original published GET byte readback failed: {path}")
        if "no-store" not in headers.get("cache-control", "").lower():
            raise ValueError(f"Missing original no-store cache policy: {path}")
        head_status, head_headers, head_body = fetcher(url, "HEAD")
        if head_status != 200 or head_body:
            raise ValueError(f"Original published HEAD readback failed: {path}")
        if "no-store" not in head_headers.get("cache-control", "").lower():
            raise ValueError(f"Missing original HEAD no-store policy: {path}")
        if path.endswith(CAMPAIGN_ID):
            if (b'noindex,nofollow,noarchive' not in body
                or b'<form' in body.lower() or b'<script' in body.lower()):
                raise ValueError("Unexpected active/indexed Chicago page content")
        verified.append({
            "route": path,
            "status_get": status,
            "status_head": head_status,
            "body_sha256": _sha(body),
        })
    return {
        "schema_version": "empire.original_owner.chicago_postrelease_http_readback.v1",
        "status": "ORIGINAL_SIX_EXACT_GET_HEAD_READBACK_PASS",
        "original_campaigns": 5,
        "new_chicago_pages": 1,
        "verified": verified,
        "no_publication_performed_by_check": True,
        "recorded_revenue": None,
        "observer_only": True,
    }
