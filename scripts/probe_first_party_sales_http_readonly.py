#!/usr/bin/env python3
"""EmpireOS live enquiry surface canary: GET ONLY. Never fabricate a customer.

Checks the actual served HTML, its same-origin compiled JavaScript and the two
public product catalogues. Intentionally does NOT call POST, sign in, inspect
customer records or claim that a buyer->EmpireDB->Founder CRM transfer worked.
"""
from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

ORIGIN = "http://127.0.0.1"
PUBLIC_HOST = "empire-ai.co.uk"
MAX_HTML_BYTES = 400_000
MAX_JS_BYTES = 1_100_000
MAX_JSON_BYTES = 250_000
MAX_SCRIPTS_PER_PAGE = 24

PAGES = (
    ("/commercial", "/v1/checkout/commercial/interests"),
    ("/predictive-revenue", "/v1/checkout/predictive-revenue/interests"),
)
CATALOGS = (
    "/v1/checkout/commercial/offers",
    "/v1/checkout/predictive-revenue/products",
)


class CanaryHeld(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.srcs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "script":
            return
        src = dict(attrs).get("src", "")
        # Do not fetch third-party scripts, query-bearing routes or traversal.
        if (re.fullmatch(r"/_next/static/[a-zA-Z0-9._/\-]+\.js", src)
                and ".." not in src):
            self.srcs.append(src)


def fetch_local_get(path: str, max_bytes: int) -> tuple[int, str, bytes]:
    if (not isinstance(path, str) or not path.startswith("/")
            or path.startswith("//") or ".." in path
            or any(x in path for x in ("?", "#", "\\"))
            or max_bytes > MAX_JS_BYTES or max_bytes < 1):
        raise CanaryHeld("UNSAFE_LOCAL_GET_PATH")
    request = Request(
        ORIGIN + path,
        headers={"Host": PUBLIC_HOST, "User-Agent": "EmpireOS-GET-only-revenue-intake-canary/1"},
        method="GET",
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=6) as response:
            status = response.status
            ctype = response.headers.get("Content-Type", "")
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise CanaryHeld("SOURCE_RESPONSE_OVERSIZED")
            return status, ctype, data
    except CanaryHeld:
        raise
    except (HTTPError, URLError, TimeoutError, OSError):
        raise CanaryHeld("LOCAL_READONLY_ENDPOINT_UNAVAILABLE") from None


def inspect(fetch: Callable[[str, int], tuple[int, str, bytes]] = fetch_local_get) -> dict:
    report = {
        "schema_version": "empire.founder.live_sales_page_readonly_canary.v1",
        "mode": "READ_ONLY",
        "status": "HELD",
        "public_page_count": 0,
        "compiled_intake_routes_verified": 0,
        "commercial_offer_count": None,
        "predictive_revenue_product_count": None,
        "canonical_sales_acquisitions_checked": False,
        "founder_crm_delivery_verified": False,
        "genuine_test_buyer_submitted": False,
        "checkout_or_payment_executed": False,
        "outbound_sent": False,
        "database_writes": False,
        "execution_authority": "none",
    }
    try:
        for page, endpoint in PAGES:
            status, ctype, body = fetch(page, MAX_HTML_BYTES)
            if status != 200 or "text/html" not in ctype.lower() or b"<html" not in body.lower():
                raise CanaryHeld("PAGE_HTTP_OR_HTML_CONTRACT_FAILED")
            parser = ScriptParser()
            parser.feed(body.decode("utf-8", errors="replace"))
            sources = list(dict.fromkeys(parser.srcs))
            if not sources or len(sources) > MAX_SCRIPTS_PER_PAGE:
                raise CanaryHeld("PAGE_SCRIPT_MANIFEST_MISSING_OR_OVERSIZED")
            endpoint_bytes = endpoint.encode("ascii")
            found = False
            for script in sources:
                js_status, js_ctype, js = fetch(script, MAX_JS_BYTES)
                if js_status != 200 or not any(
                    marker in js_ctype.lower()
                    for marker in ("javascript", "text/plain", "application/octet-stream")
                ):
                    raise CanaryHeld("DEPLOYED_APP_SCRIPT_UNAVAILABLE")
                found = found or endpoint_bytes in js
            if not found:
                raise CanaryHeld("DEPLOYED_ENQUIRY_FORM_ACTION_NOT_FOUND")
            report["public_page_count"] += 1
            report["compiled_intake_routes_verified"] += 1

        values = []
        for path in CATALOGS:
            status, ctype, payload = fetch(path, MAX_JSON_BYTES)
            if status != 200 or "application/json" not in ctype.lower():
                raise CanaryHeld("CATALOG_HTTP_OR_CONTENT_TYPE_FAILED")
            try:
                data = json.loads(payload)
            except (ValueError, UnicodeDecodeError):
                raise CanaryHeld("CATALOG_JSON_NOT_TRUSTED") from None
            if not isinstance(data, dict):
                raise CanaryHeld("CATALOG_DATA_NOT_OBJECT")
            values.append(data)
        commercial, predictive = values
        offers, products = commercial.get("offers"), predictive.get("products")
        if (commercial.get("status") != "FOUNDER_LED_ENQUIRY_AVAILABLE"
                or commercial.get("scope") != "BUYER_INITIATED_CONTACT_ONLY"
                or commercial.get("outbound_authority") != "none"
                or commercial.get("payment_authority") != "none"
                or commercial.get("checkout_authorized") is not False
                or commercial.get("actual_revenue") is not False
                or not isinstance(offers, list)
                or not 1 <= len(offers) <= 100
                or commercial.get("count") != len(offers)):
            raise CanaryHeld("COMMERCIAL_CATALOG_AUTHORITY_OR_COUNT_DRIFT")
        if (predictive.get("execution_authority") != "none"
                or predictive.get("actual_revenue") is not False
                or not isinstance(products, list)
                or not 1 <= len(products) <= 100
                or predictive.get("product_count") != len(products)):
            raise CanaryHeld("PREDICTIVE_CATALOG_AUTHORITY_OR_COUNT_DRIFT")
        report["commercial_offer_count"] = len(offers)
        report["predictive_revenue_product_count"] = len(products)
        report["status"] = "PUBLIC_ENQUIRY_SURFACE_VERIFIED_CRM_DELIVERY_UNPROVEN"
    except CanaryHeld as e:
        report["reason_code"] = str(e)
    except Exception:
        report["reason_code"] = "UNEXPECTED_READONLY_CANARY_FAILURE"
    return report


# These paths are the canonical existing private CRM pilot, not the public
# website and not the founder's personal account. No authentication attempted.
PRIVATE_CRM_ORIGIN = "http://127.0.0.1:8783"
PRIVATE_CRM_PATHS = (
    "/health", "/v1/revenue-crm/prospects", "/v1/revenue-crm/buyers",
)


def fetch_private_crm_get(path: str) -> tuple[int, str, dict, bytes]:
    if path not in PRIVATE_CRM_PATHS:
        raise CanaryHeld("UNAPPROVED_PRIVATE_CRM_PATH")
    request = Request(
        PRIVATE_CRM_ORIGIN + path,
        headers={"User-Agent": "EmpireOS-private-CRM-auth-boundary-canary/1"},
        method="GET",
    )
    opener = build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=5) as response:
            data = response.read(4097)
            if len(data) > 4096:
                raise CanaryHeld("PRIVATE_CRM_OVERSIZED_RESPONSE")
            return response.status, response.headers.get("Content-Type", ""), {
                "Cache-Control": response.headers.get("Cache-Control", ""),
                "X-Frame-Options": response.headers.get("X-Frame-Options", ""),
                "X-Content-Type-Options": response.headers.get("X-Content-Type-Options", ""),
            }, data
    except HTTPError as error:
        # Anonymous access MUST be rejected, and neither a CRM row nor the
        # exception's private error payload is ever fetched or printed.
        if error.code in (401, 403):
            return error.code, "", {
                "Cache-Control": error.headers.get("Cache-Control", ""),
                "X-Frame-Options": error.headers.get("X-Frame-Options", ""),
                "X-Content-Type-Options": error.headers.get("X-Content-Type-Options", ""),
            }, b""
        raise CanaryHeld("PRIVATE_CRM_AUTH_BOUNDARY_UNAVAILABLE") from None
    except (URLError, TimeoutError, OSError):
        raise CanaryHeld("PRIVATE_CRM_AUTH_BOUNDARY_UNAVAILABLE") from None


def inspect_private_crm_auth(
    fetch: Callable[[str], tuple[int, str, dict, bytes]] = fetch_private_crm_get,
) -> dict:
    """Verify the no-credential CRM boundary, NEVER an actual sales receipt."""
    result = {
        "private_crm_auth_boundary_checked": True,
        "private_crm_auth_boundary_verified": False,
        "private_crm_healthy": False,
        "anonymous_prospect_access_denied": False,
        "anonymous_buyer_access_denied": False,
        "private_crm_customer_rows_read": False,
        "founder_login_authenticated": False,
        "founder_crm_delivery_verified": False,
    }
    try:
        status, ctype, headers, body = fetch("/health")
        if status != 200 or "application/json" not in ctype.lower() or len(body) > 4096:
            raise CanaryHeld("PRIVATE_CRM_HEALTH_UNVERIFIED")
        try:
            health = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            raise CanaryHeld("PRIVATE_CRM_HEALTH_UNVERIFIED") from None
        if (not isinstance(health, dict)
                or health.get("ok") is not True
                or health.get("service") != "empire-crm-first-party-pilot"
                or health.get("mode") != "APPROVED_READ_ONLY_PILOT"
                or health.get("outbound_authority") != "none"
                or health.get("payment_authority") != "none"
                or health.get("database_provisioning") is not False):
            raise CanaryHeld("PRIVATE_CRM_HEALTH_UNVERIFIED")
        result["private_crm_healthy"] = True
        for route, field in (
            ("/v1/revenue-crm/prospects", "anonymous_prospect_access_denied"),
            ("/v1/revenue-crm/buyers", "anonymous_buyer_access_denied"),
        ):
            code, _ctype, protection, payload = fetch(route)
            if (code not in (401, 403) or payload
                    or protection.get("Cache-Control") != "no-store"
                    or protection.get("X-Frame-Options") != "DENY"
                    or protection.get("X-Content-Type-Options") != "nosniff"):
                raise CanaryHeld("PRIVATE_CRM_ANONYMOUS_ACCESS_NOT_VERIFIED")
            result[field] = True
        result["private_crm_auth_boundary_verified"] = True
    except CanaryHeld as exc:
        result["private_crm_reason_code"] = str(exc)
    except Exception:
        result["private_crm_reason_code"] = "PRIVATE_CRM_AUTH_BOUNDARY_UNEXPECTED_FAILURE"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-private-inbox", action="store_true",
        help="Verify ONLY loopback private CRM health and anonymous access denial; never read inbox rows",
    )
    args = parser.parse_args(argv)
    result = inspect()
    if args.check_private_inbox:
        result.update(inspect_private_crm_auth())
        if result["status"] == "PUBLIC_ENQUIRY_SURFACE_VERIFIED_CRM_DELIVERY_UNPROVEN":
            result["status"] = (
                "PRIVATE_CRM_AUTH_GATE_READY_NO_RECEIPT_READ"
                if result["private_crm_auth_boundary_verified"]
                else "HELD_PRIVATE_CRM_AUTH_BOUNDARY_UNVERIFIED"
            )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in {
        "PUBLIC_ENQUIRY_SURFACE_VERIFIED_CRM_DELIVERY_UNPROVEN",
        "PRIVATE_CRM_AUTH_GATE_READY_NO_RECEIPT_READ",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
