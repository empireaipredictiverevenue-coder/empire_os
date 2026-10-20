#!/usr/bin/env python3
"""One Brave web-search request, key-safe validation of the actual API error.

Run only through the existing root-protected systemd EnvironmentFile. This
makes ONE provider request; no retries, raw bodies, tokens, Search Fabric cache,
CRM writes, outbound sends or campaign launches.
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlparse

import requests

QUERY = "roofing contractors Tampa Florida"
ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
KNOWN_ERROR_CODES = frozenset({
    "SUBSCRIPTION_TOKEN_INVALID", "SUBSCRIPTION_TOKEN_MISSING",
    "SUBSCRIPTION_NOT_FOUND", "SUBSCRIPTION_INACTIVE", "SUBSCRIPTION_NOT_ACTIVE",
    "OPTION_NOT_IN_PLAN", "VALIDATION", "VALIDATION_ERROR",
    "INVALID_ARGUMENT", "INVALID_REQUEST", "BAD_REQUEST",
    "UNPROCESSABLE_ENTITY", "RATE_LIMITED", "QUOTA_LIMITED",
    "INTERNAL", "NOT_FOUND", "UNKNOWN",
})
KNOWN_COMPONENTS = frozenset({
    "authentication", "validation", "subscription", "authorization",
    "query", "rate_limit", "billing",
})


def assess_http_response(status: int, payload: object) -> dict:
    """Explicit, allowlisted provider errors only; never display error.detail."""
    data = payload if isinstance(payload, dict) else {}
    raw = data.get("error")
    error = raw if isinstance(raw, dict) else {}
    code = error.get("code")
    code = (code if isinstance(code, str)
            and CODE_PATTERN.fullmatch(code) and code in KNOWN_ERROR_CODES
            else "OTHER_OR_UNSPECIFIED_ERROR")
    meta = error.get("meta")
    component = (meta.get("component") if isinstance(meta, dict) else None)
    component = (component if isinstance(component, str) and component in KNOWN_COMPONENTS
                 else "not_specified")

    result = {
        "provider": "brave",
        "http_status": status,
        "brave_error_code": code if status != 200 else None,
        "brave_error_component": component if status != 200 else None,
        "provider_query_count_max": 1,
        "api_key_value_logged": False,
        "buyer_scout_or_crm_modified": False,
        "messages_sent": 0,
        "verified_buyers": 0,
        "fresh_public_domains": [],
        "result_count": 0,
    }
    if status == 200:
        from empire_os.search_fabric.search import _parse_brave, _quality_filter
        raw_results = _parse_brave(data)
        results = _quality_filter(raw_results, QUERY, 3)
        domains = []
        for row in results[:3]:
            url = row.get("link", "")
            host = urlparse(url).hostname if isinstance(url, str) else None
            if host and host not in domains:
                domains.append(host.lower())
        result.update({
            "result_count": len(results),
            "fresh_public_domains": domains,
            "state": ("BRAVE_SEARCH_RETURNED_SOURCE_RESULTS"
                      if domains else "BRAVE_RESPONSE_NO_RELEVANT_RESULTS"),
        })
    elif status == 422 and code == "SUBSCRIPTION_TOKEN_INVALID":
        result["state"] = "BRAVE_SUBSCRIPTION_TOKEN_INVALID"
        result["next_action"] = "CHECK_WEB_SEARCH_PLAN_KEY_AND_REGENERATE_IN_BRAVE_DASHBOARD"
    elif status == 422 and code in {"VALIDATION", "VALIDATION_ERROR", "INVALID_ARGUMENT",
                                    "INVALID_REQUEST", "BAD_REQUEST", "UNPROCESSABLE_ENTITY"}:
        result["state"] = "BRAVE_REQUEST_VALIDATION_ERROR"
        result["next_action"] = "REVIEW_WEB_SEARCH_REQUEST_PARAMETERS"
    elif status == 422 and code in {"OPTION_NOT_IN_PLAN", "SUBSCRIPTION_NOT_FOUND",
                                    "SUBSCRIPTION_INACTIVE", "SUBSCRIPTION_NOT_ACTIVE"}:
        result["state"] = "BRAVE_SUBSCRIPTION_PLAN_OR_ENTITLEMENT_FAILURE"
        result["next_action"] = "CHECK_BRAVE_WEB_SEARCH_SUBSCRIPTION_STATUS"
    elif status in (401, 403):
        result["state"] = "BRAVE_AUTHENTICATION_OR_ENTITLEMENT_REJECTED"
        result["next_action"] = "CHECK_BRAVE_WEB_SEARCH_KEY_AND_PLAN"
    elif status == 429:
        result["state"] = "BRAVE_QUOTA_OR_RATE_LIMITED"
        result["next_action"] = "CHECK_SUBSCRIPTION_QUOTA"
    else:
        result["state"] = "BRAVE_PROVIDER_HTTP_FAILURE_NOT_YET_CLASSIFIED"
        result["next_action"] = "REVIEW_BRAVE_DASHBOARD_WITHOUT_DISCLOSING_SECRET"
    return result


def main() -> int:
    key = os.environ.get("BRAVE_API_KEY", "").strip()
    if (not key or len(key) < 12 or key == "YOUR_ACTUAL_BRAVE_KEY"
            or any(c.isspace() for c in key)):
        print(json.dumps({
            "provider": "brave",
            "state": "KEY_UNAVAILABLE_OR_INVALID_SERVICE_ENV_FORMAT",
            "provider_requests": 0,
            "api_key_value_logged": False,
            "verified_buyers": 0,
        }))
        return 2

    try:
        # Official Brave Web Search API GET and the same valid parameters as
        # the existing Search Fabric's Brave adapter. No automatic retries.
        response = requests.get(
            ENDPOINT,
            params={"q": QUERY, "count": 3},
            headers={"X-Subscription-Token": key,
                     "Accept": "application/json",
                     "Accept-Encoding": "gzip",
                     "User-Agent": "EmpireOS-Brave-Search-Preflight/1.0"},
            allow_redirects=False,
            timeout=10,
        )
        status = response.status_code
        if len(response.content) > 250_000:
            raise ValueError("BOUNDED_PROVIDER_RESPONSE_TOO_LARGE")
        try:
            payload = response.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            payload = {}
        result = assess_http_response(status, payload)
    except (requests.exceptions.RequestException, ValueError) as exc:
        result = {
            "provider": "brave",
            "state": "NETWORK_OR_PROVIDER_RESPONSE_ERROR",
            "exception_type_only": type(exc).__name__,
            "provider_query_count_max": 1,
            "api_key_value_logged": False,
            "verified_buyers": 0,
        }

    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "BRAVE_SEARCH_RETURNED_SOURCE_RESULTS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
