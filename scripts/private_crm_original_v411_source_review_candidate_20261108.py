"""Staged additive route for original private CRM -> original V4.11 HELD reader.

No standalone service, new data/identity model, customer API, forecasting,
source admission or source-rights grants. The already-active CRM issuer remains
sole authority. Never logs or reflects JWT, tenant UUID, DSN or credentials.

PRODUCTION HELD: requires separate owner-controlled LoadCredential and CRM
restart approval. Importing this module by itself does not change production.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.routing import Route

from empire_os.predictive_cloud_v410_rights_reader import EmpireDbHeldSourceRightsReader
from empire_os.predictive_revenue_v411_source_gate import (
    PredictiveRevenueSourceHold, review_revenue_source_candidate_held,
)
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier, _object
from empire_os.predictive_cloud_founder_session import DataCloudFounderAuthority

SOURCE_DIGEST = "31787934624aac98439d48603641951d910e6df96880de9dafe4e35cb2614b5d"
SOURCE_PATH = "/v1/predictive-cloud/source-rights/verify"
HTML_PATH = "/v1/revenue-crm/journeys/entry"
JS_PATH = "/v1/revenue-crm/journeys/entry.js"
DATA_BUTTON = '<button id="verify-data-cloud" type="button" disabled>'
DATA_BIND = '  byId("verify-data-cloud").addEventListener("click", verifyDataCloudExchange);'
DATA_CLEAR = '    byId("verify-data-cloud").disabled = true;'
DATA_LOGIN = '      byId("verify-data-cloud").disabled = false;'
PINNED_LIVE_HTML_SHA = "1d86ce33e8f7b4edb63a52a14ccf76f0f7dfc617a2763173eceaa845ab849282"
PINNED_LIVE_JS_SHA = "7f50fa36289a7539a33e7b058038c4373b9d64e556f2f5c751fb3932c707be6f"

HTML_INSERT = (
    '<div class="inline-buttons"><button id="verify-predictive-source" '
    'type="button" disabled>Verify Predictive Source</button></div>'
    '<p id="predictive-source-verify-status" role="status" aria-live="polite">'
    'Sign in to check the existing private source-rights receipt.</p>'
)

JS_VERIFY = r"""
  async function verifyPredictiveSource() {
    const button = byId("verify-predictive-source");
    const output = byId("predictive-source-verify-status");
    if (!sessionBearer || Date.now() >= sessionUntil) {
      output.textContent = "Sign in to verify the private source review.";
      return;
    }
    const generation = sessionGeneration;
    button.disabled = true;
    output.textContent = "Checking the original signed CRM source review…";
    try {
      // The REAL signed CRM bearer remains inside this existing tab closure.
      const response = await fetch("/v1/predictive-cloud/source-rights/verify", {
        method: "POST", cache: "no-store", credentials: "omit",
        redirect: "error",
        headers: { "Authorization": "Bearer " + sessionBearer }
      });
      if (generation !== sessionGeneration ||
          !sessionBearer || Date.now() >= sessionUntil)
        throw new Error("CRM session expired");
      if (!response.ok) throw new Error("Source review not available");
      const result = await response.json();
      if (result.schema_version !== "empire.private_crm.v411.source_review.v1" ||
          result.mode !== "OBSERVE" ||
          result.customer_delivery_authorized !== false ||
          result.customer_forecast_verified !== false ||
          result.source_rights_verified !== false ||
          !["PENDING_HELD", "CANDIDATE_REVIEW_HELD", "REVOKED_HELD",
            "EXPIRED_HELD", "FUTURE_EVIDENCE_HELD",
            "NO_SOURCE_RIGHTS_HELD"].includes(result.rights_decision))
        throw new Error("Invalid source review");
      output.textContent =
        "Verified against your signed CRM session: " +
        result.rights_decision + ". Internal research only; " +
        "no customer predictions or source redistribution enabled.";
    } catch (_) {
      if (generation === sessionGeneration)
        output.textContent =
          "Predictive source receipt not verified. No authority was changed.";
    } finally {
      if (generation === sessionGeneration &&
          sessionBearer && Date.now() < sessionUntil)
        button.disabled = false;
    }
  }
  byId("verify-predictive-source").addEventListener(
    "click", verifyPredictiveSource);
"""


def one(original: str, marker: str, replacement: str) -> str:
    if original.count(marker) != 1:
        raise RuntimeError("original_verified_crm_overlay_contract_changed")
    return original.replace(marker, replacement, 1)


def patch_html(source: str) -> str:
    return one(source, DATA_BUTTON, HTML_INSERT + DATA_BUTTON)


def patch_js(source: str) -> str:
    result = one(source, DATA_CLEAR,
        DATA_CLEAR + '\n    byId("verify-predictive-source").disabled = true;'
        + '\n    byId("predictive-source-verify-status").textContent = '
          '"Sign in to check the existing private source-rights receipt.";')
    result = one(result, DATA_LOGIN,
        DATA_LOGIN + '\n      byId("verify-predictive-source").disabled = false;'
        + '\n      byId("predictive-source-verify-status").textContent = '
          '"Ready: check your signed CRM source review.";')
    return one(result, DATA_BIND, JS_VERIFY + '\n' + DATA_BIND)


def attach_private_source_review(
    app: FastAPI,
    crm_verifier: SignedCrmTenantVerifier,
    founder_authority: DataCloudFounderAuthority,
    reader: EmpireDbHeldSourceRightsReader,
    *,
    expected_html_sha: str = PINNED_LIVE_HTML_SHA,
    expected_js_sha: str = PINNED_LIVE_JS_SHA,
) -> None:
    if (type(crm_verifier) is not SignedCrmTenantVerifier
        or type(founder_authority) is not DataCloudFounderAuthority
        or type(reader) is not EmpireDbHeldSourceRightsReader
        or founder_authority.crm is not crm_verifier):
        raise RuntimeError("original_crm_issuer_or_original_rights_reader_required")
    if any(getattr(r, "path", "") == SOURCE_PATH for r in app.router.routes):
        raise RuntimeError("existing_source_review_route_collision")

    # Only the two existing private CRM visual routes are shadowed; the
    # original frozen HTML/JS, CRM sign-in and Data Cloud exchange are intact.
    originals: dict[str, Response] = {}
    for path in (HTML_PATH, JS_PATH):
        matches = [r for r in app.router.routes
                   if getattr(r, "path", None) == path
                   and "GET" in getattr(r, "methods", set())
                   and getattr(r, "methods", set()).issubset({"GET","HEAD"})]
        if len(matches) != 1:
            raise RuntimeError("current_private_crm_response_not_unique")
        response = matches[0].endpoint(None)
        if response.status_code != 200 or response.headers.get("cache-control") != "no-store":
            raise RuntimeError("current_private_crm_security_contract_changed")
        originals[path] = response

    # Pin the EXACT currently served protected founder CRM overlay. A
    # concurrent owner changing either page blocks this release rather
    # than silently shadowing their design or security headers.
    if (hashlib.sha256(originals[HTML_PATH].body).hexdigest() != expected_html_sha
        or hashlib.sha256(originals[JS_PATH].body).hexdigest() != expected_js_sha):
        raise RuntimeError("currently_served_original_crm_overlay_sha_changed")

    for path, original, content, mime in (
        (HTML_PATH, originals[HTML_PATH],
         patch_html(originals[HTML_PATH].body.decode("utf-8")), "text/html"),
        (JS_PATH, originals[JS_PATH],
         patch_js(originals[JS_PATH].body.decode("utf-8")), "text/javascript"),
    ):
        headers = {key: val for key, val in original.headers.items()
                   if key.lower() not in ("content-length", "content-type")}
        def owner_overlay(request: Request, *, body=content, h=headers, media=mime):
            return Response(content=body,media_type=media,headers=h)
        app.router.routes.insert(0,Route(path, endpoint=owner_overlay, methods=["GET"]))

    async def verify(request: Request) -> JSONResponse:
        headers = request.headers.getlist("authorization")
        no_cache = {"Cache-Control": "no-store", "Pragma": "no-cache",
                    "X-Content-Type-Options": "nosniff"}
        if (len(headers) != 1 or not headers[0].startswith("Bearer ")
            or not headers[0][7:] or headers[0][7:] != headers[0][7:].strip()
            or len(headers[0]) > 4103):
            return JSONResponse({"detail":"original_crm_session_required"},
                                status_code=401,headers=no_cache)
        if request.url.query or request.headers.get("content-length", "0") != "0":
            return JSONResponse({"detail":"no_request_parameters_accepted"},
                                status_code=400,headers=no_cache)
        token = headers[0][7:]
        try:
            # Founder entitlement is separate from being an arbitrary
            # authenticated CRM member at the same tenant.
            tenant = crm_verifier.authenticate(token)
            claims = _object(token.split(".")[1],1536)
            if claims.get("tenant_id") != tenant:
                raise ValueError("original_tenant_binding_failed")
            founder_authority.check(claims["sub"],tenant)
        except PermissionError:
            return JSONResponse({"detail":"founder_only_source_review"},
                                status_code=403,headers=no_cache)
        except Exception:
            return JSONResponse({"detail":"invalid_crm_session"},
                                status_code=401,headers=no_cache)
        try:
            result = review_revenue_source_candidate_held(
                crm_bearer=token,crm_verifier=crm_verifier,
                source_rights_reader=reader,source_evidence_digest=SOURCE_DIGEST)
        except PredictiveRevenueSourceHold:
            return JSONResponse({"detail":"source_review_held"},
                                status_code=403,headers=no_cache)
        if (result.get("rights_decision") == "SOURCE_RIGHTS_READER_UNAVAILABLE_HELD"
            or result.get("restricted_empiredb_rights_reader_checked") is not True):
            return JSONResponse({"detail":"restricted_reader_unavailable_held"},
                                status_code=503,headers=no_cache)
        return JSONResponse({
            "schema_version":"empire.private_crm.v411.source_review.v1",
            "mode":"OBSERVE",
            "rights_decision":result["rights_decision"],
            "source_rights_verified":False,
            "customer_delivery_authorized":False,
            "customer_forecast_verified":False,
            "execution_authority":"none",
        },headers=no_cache)
    app.add_api_route(SOURCE_PATH,verify,methods=["POST"],include_in_schema=False)
