"""HTTP response boundary for the existing read-only enterprise report router.

No caller-controlled status can bypass the prior enterprise source/claim
validator. Inconsistent internal reports never reach a JSON/HTML/Markdown
response body. Do not infer customer consent or verified revenue.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from fastapi import HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from empire_os.enterprise_report_claim_guard import (
    guarded_enterprise_report_render,
    validate_enterprise_report_before_render,
)

EVIDENCE_HOLD_DETAIL = {
    "status": "HOLD_ENTERPRISE_REPORT_EVIDENCE",
    "customer_delivery_authorized": False,
    "verified_client_findings": 0,
    "execution_authority": "none",
}
NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
}


def guarded_enterprise_http_response(
    report: Any,
    *,
    format: Literal["json", "html", "markdown"],
) -> Response:
    """Return only verified-as-*internal-unverified* draft; else HTTP 409.

    The response is constructed from the same validated deep copy.
    Unknown output formats are denied.  Runtime service process must reload
    this code; a disk-only patch is not evidence of live protection.
    """
    if format not in {"json", "html", "markdown"}:
        raise HTTPException(status_code=409, detail=EVIDENCE_HOLD_DETAIL)
    try:
        snapshot = deepcopy(report)
        # The signed-off API boundary is a *validator*, not a verified
        # client-data source or a grant for outbound/customer delivery.
        evidence = validate_enterprise_report_before_render(snapshot)
        if (evidence.get("status") != "INTERNAL_UNVERIFIED_DRAFT_STRUCTURE_VALIDATED"
                or evidence.get("customer_delivery_authorized") is not False
                or evidence.get("verified_finding_count") != 0):
            raise ValueError("EVIDENCE_NOT_VALIDATED")
        if format == "json":
            return JSONResponse(content=snapshot, headers=NO_STORE_HEADERS)
        rendered = guarded_enterprise_report_render(snapshot, format=format)
        response_cls = HTMLResponse if format == "html" else PlainTextResponse
        return response_cls(content=rendered, headers=NO_STORE_HEADERS)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        # Do not reflect untrusted report content or source paths to clients.
        raise HTTPException(status_code=409, detail=EVIDENCE_HOLD_DETAIL) from None
