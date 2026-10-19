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
from scripts.materialize_lead_smart_launch_readiness import compute_live_launch_readiness

BASE = Path("/srv/empire_os/runtime/revenue/lead_smart")
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
    # This checks the actual already-published Empire AI legal-page receipts.
    # The older reviewed_content_release.json belongs to an unrelated staged
    # guide system and is not the release of public /privacy and /terms.
    # Presence of these notices is NOT certification of recording compliance;
    # the independent recording/legal readiness gates remain mandatory.
    from empire_os.empire_ai_public_legal_release import checked_legal_path
    return all(checked_legal_path(route) is not None for route in ("privacy", "terms"))


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
            readiness=compute_live_launch_readiness(), eligible_zip=True,
        )
    except (HandoffHeld, OSError, ValueError, TypeError, KeyError, AttributeError, PreviewEvidenceError):
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
        fields = parse_qs(body.decode("ascii"), strict_parsing=True, keep_blank_values=True)
    except (ValueError, UnicodeError):
        fields = {}
    # The buyer requires call recording. The first ZIP submission must never
    # disclose a dial link or consume a handoff permit. A separate, affirmative
    # visitor choice is required BEFORE the site offers the phone link.
    acknowledgment = set(fields) == {"zip", "recording_consent"}
    if (set(fields) not in ({"zip"}, {"zip", "recording_consent"})
            or len(fields.get("zip", [])) != 1
            or (acknowledgment and fields.get("recording_consent") != ["yes"])):
        return JSONResponse({"status": "INVALID_REQUEST"}, status_code=422, headers=HEADERS)
    zip_code = fields["zip"][0]
    if not re.fullmatch(r"[0-9]{5}", zip_code):
        return JSONResponse({"status": "INVALID_REQUEST"}, status_code=422, headers=HEADERS)
    if not call_available(zip_code):
        return JSONResponse({"status": "UNAVAILABLE"}, status_code=503, headers=HEADERS)
    if not acknowledgment:
        # No cookies, accounts, saved consent receipts, dial attempts or ZIP
        # query parameters. The real stop and current buyer evidence are
        # checked again after consent, before a permit can be consumed.
        return HTMLResponse(
            "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='robots' content='noindex,nofollow'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Before your roofing call</title></head><body>"
            "<main><h1>Before your roofing call</h1>"
            "<p>Your call to a third-party roofing service is recorded by the "
            "call-routing provider and/or receiving service provider for "
            "quality assurance and training. The buyer reports that Ringba "
            "keeps call recordings indefinitely unless deletion is legally required. "
            "Your phone number and call details may be shared with the routing "
            "provider and the receiving roofing company.</p>"
            "<p>The call flow may also play a recorded-call announcement. "
            "If you do not agree to recording, do not place the call.</p>"
            "<form method='post' action='/roofing/pilot-handoff'>"
            f"<input type='hidden' name='zip' value='{zip_code}'>"
            "<label><input type='checkbox' name='recording_consent' value='yes' "
            "required> I understand the recording and sharing described above "
            "and agree to proceed with a recorded call.</label>"
            "<button type='submit'>Continue to optional call</button>"
            "</form><p><a href='/privacy'>Privacy</a> · "
            "<a href='/terms'>Terms</a></p></main></body></html>",
            headers=HEADERS,
        )
    try:
        # Consume one permit atomically; re-check all gates under lock.
        phone_uri = reserve_site_handoff(
            zip_code, config_path=CONFIG, ledger_path=LEDGER,
            readiness=compute_live_launch_readiness(), eligible_zip=_in_current_coverage(zip_code),
        )
    except (HandoffHeld, OSError, ValueError, KeyError, AttributeError, PreviewEvidenceError, TypeError):
        return JSONResponse({"status": "UNAVAILABLE"}, status_code=503, headers=HEADERS)
    # No auto-dial: the homeowner deliberately taps the final tel: link.
    return HTMLResponse(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='robots' content='noindex,nofollow'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Roofing call option</title></head><body>"
        "<main><h1>Roofing call option</h1><p>If you choose, call to discuss "
        "roof replacement or installation. Availability is not guaranteed.</p>"
        "<p><strong>Recording notice:</strong> Calls may be recorded for "
        "quality assurance and training purposes by call-routing providers "
        "and the receiving contractor. Any additional in-call notice and "
        "consent requirements still apply.</p>"
        f"<p><a href='{phone_uri}'>Tap to call the roofing service</a></p>"
        "<p>Independent contractors may receive your call. "
        "<a href='/privacy'>Privacy</a> · <a href='/terms'>Terms</a></p>"
        "</main></body></html>",
        headers=HEADERS,
    )
