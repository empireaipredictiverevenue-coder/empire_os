"""Consumer-initiated Direct roofing handoff; never call unless current gates pass."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from empire_os.lead_smart_site_handoff import (
    CONFIG, LEDGER, HandoffHeld, _json, reserve_site_handoff,
    site_handoff_available,
)
from empire_os.lead_smart_homeowner_eligibility import generate_from_files, PreviewEvidenceError

BASE = Path("/srv/empire_os/runtime/revenue/lead_smart")
READINESS = BASE / "launch_readiness/latest.json"
ROUTE = "/roofing/pilot-handoff"
HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "X-Robots-Tag": "noindex, nofollow",
    "Referrer-Policy": "no-referrer",
}
router = APIRouter()


def _in_current_coverage(zip_code: str) -> bool:
    # Reuse the exact hash/freshness checked first-party ZIP preview.
    manifest = generate_from_files(
        BASE / "coverage/latest.json",
        BASE / "coverage/activation/latest.json",
        BASE / "coverage/intelligence/latest.json",
    )
    return zip_code in set(manifest["covered_zips"])


def _released_privacy_terms() -> bool:
    # No circular import at app startup: invoked on actual request only.
    from empire_os.public_gateway import _approved_static_content_path
    return all(_approved_static_content_path(r) is not None for r in ("privacy", "terms"))


def call_available(zip_code: str) -> bool:
    try:
        if not isinstance(zip_code, str) or re.fullmatch(r"[0-9]{5}", zip_code) is None:
            return False
        if not _released_privacy_terms():
            return False
        if not _in_current_coverage(zip_code):
            return False
        return site_handoff_available(
            zip_code, config_path=CONFIG, ledger_path=LEDGER,
            readiness=_json(READINESS), eligible_zip=True,
        )
    except (HandoffHeld, OSError, ValueError, TypeError, PreviewEvidenceError):
        return False


@router.post(ROUTE)
async def public_roofing_pilot_handoff(request: Request):
    # No ZIP in URL; no cookies, ANI, IP address or lead identity stored.
    origin = request.headers.get("origin")
    if origin != "https://empire-ai.co.uk":
        return JSONResponse({"status": "UNAVAILABLE"}, status_code=403, headers=HEADERS)
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/x-www-form-urlencoded":
        return JSONResponse({"status": "INVALID_REQUEST"}, status_code=415, headers=HEADERS)
    body = await request.body()
    if len(body) > 96:
        return JSONResponse({"status": "INVALID_REQUEST"}, status_code=422, headers=HEADERS)
    try:
        fields = parse_qs(body.decode("ascii"), strict_parsing=True)
    except (ValueError, UnicodeError):
        fields = {}
    if set(fields) != {"zip"} or len(fields.get("zip", [])) != 1:
        return JSONResponse({"status": "INVALID_REQUEST"}, status_code=422, headers=HEADERS)
    zip_code = fields["zip"][0]
    if not call_available(zip_code):
        return JSONResponse({"status": "UNAVAILABLE"}, status_code=503, headers=HEADERS)
    try:
        # Consume one permit atomically; re-check all gates under lock.
        phone_uri = reserve_site_handoff(
            zip_code, config_path=CONFIG, ledger_path=LEDGER,
            readiness=_json(READINESS), eligible_zip=_in_current_coverage(zip_code),
        )
    except (HandoffHeld, OSError, ValueError, PreviewEvidenceError, TypeError):
        return JSONResponse({"status": "UNAVAILABLE"}, status_code=503, headers=HEADERS)
    # No auto-dial: the homeowner deliberately taps the final tel: link.
    return HTMLResponse(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='robots' content='noindex,nofollow'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Roofing call option</title></head><body>"
        "<main><h1>Roofing call option</h1><p>If you choose, call to discuss "
        "roof replacement or installation. Availability is not guaranteed.</p>"
        f"<p><a href='{phone_uri}'>Tap to call the roofing service</a></p>"
        "<p>Independent contractors may receive your call. "
        "<a href='/privacy'>Privacy</a> · <a href='/terms'>Terms</a></p>"
        "</main></body></html>",
        headers=HEADERS,
    )
