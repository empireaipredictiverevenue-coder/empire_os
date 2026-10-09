"""Read-only roofing ZIP guidance through the existing Empire public gateway.

Never interprets buyer coverage as live call authorization. The only possible
responses contain non-commercial ZIP guidance or a closed-state error.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from empire_os.lead_smart_homeowner_eligibility import (
    PreviewEvidenceError,
    buyer_hours_preview,
    generate_from_files,
)

COVERAGE_ROOT = Path("/srv/empire_os/runtime/revenue/lead_smart/coverage")
router = APIRouter()

NO_STORE = {
    "Cache-Control": "no-store, max-age=0",
    "X-Robots-Tag": "noindex, nofollow",
    "Referrer-Policy": "no-referrer",
}


class RoofingZipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    zip: str = Field(min_length=5, max_length=5, pattern=r"^[0-9]{5}$")


def check_roofing_zip(zip_code: str, *, root: Path | None = None) -> dict:
    """Look up only one ZIP; never return the 27k ZIP list or payout fields."""
    root = root if root is not None else COVERAGE_ROOT
    if not isinstance(zip_code, str) or not re.fullmatch(r"[0-9]{5}", zip_code):
        raise ValueError("exact five-digit US property ZIP required")
    manifest = generate_from_files(
        root / "latest.json",
        root / "activation/latest.json",
        root / "intelligence/latest.json",
    )
    in_coverage = zip_code in set(manifest["covered_zips"])
    hours = buyer_hours_preview()

    return {
        "schema_version": "empire.lead_smart.zip_check_response.v1",
        "status": "GUIDANCE_ONLY",
        "coverage_guidance": (
            "LISTED_IN_RECENT_COVERAGE" if in_coverage
            else "NOT_LISTED_IN_RECENT_COVERAGE"
        ),
        "source_expires_at": manifest["expires_at"],
        "within_reported_hours": hours["within_reported_window"],
        "time_zone_interpretation_verified":
            hours["timezone_interpretation_verified"],
        "buyer_route_verified": False,
        "call_authorized": False,
        "execution_authority": "NONE",
    }


@router.post("/roofing/coverage-check")
def roofing_coverage_check(request: RoofingZipRequest):
    try:
        payload = check_roofing_zip(request.zip)
    except (PreviewEvidenceError, OSError, ValueError, KeyError, TypeError):
        # Do not echo the user's ZIP, internal file names, or exception details.
        return JSONResponse(
            status_code=503,
            content={
                "schema_version": "empire.lead_smart.zip_check_response.v1",
                "status": "UNAVAILABLE",
                "call_authorized": False,
                "execution_authority": "NONE",
            },
            headers=NO_STORE,
        )
    return JSONResponse(content=payload, headers=NO_STORE)
