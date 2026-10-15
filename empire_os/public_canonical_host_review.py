"""Pure canonical-host 308 redirect *candidate*, never an enabled gateway hook.

The live public gateway is concurrently maintained. This conservative helper
lets its owner review safe HTML paths before a separately approved release.
Do not route requests through this module without tests and founder release.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode
from typing import Any

SCHEMA = "empire.public.canonical_host_candidate.v1"
ORIGIN = "https://empire-ai.co.uk"
WWW_HOST = "www.empire-ai.co.uk"

PUBLISHED_PAGES = frozenset({
    "/", "/trust", "/industries", "/commercial", "/predictive-revenue",
    "/privacy", "/terms",
})
SAFE_QUERY_KEYS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
})


def _approved_public_html_path(path: str) -> bool:
    if path in PUBLISHED_PAGES:
        return True
    if re.fullmatch(r"/industries/[a-z][a-z0-9-]{0,70}/?", path):
        return True
    # An AEO path can be *reviewed* for host canonicalization without
    # asserting that the page was ever published, indexed, or high quality.
    if re.fullmatch(r"/aeo/[a-z][a-z0-9_]{0,60}/[A-Za-z0-9]{2,6}/?", path):
        return True
    return False


def _safe_query(raw_query: str) -> str | None:
    if raw_query == "":
        return ""
    if len(raw_query) > 300 or any(ord(x) < 33 or ord(x) > 126 for x in raw_query):
        return None
    try:
        pairs = parse_qsl(raw_query, keep_blank_values=True, strict_parsing=True,
                          max_num_fields=5, encoding="utf-8", errors="strict")
    except (ValueError, UnicodeDecodeError):
        return None
    if not pairs or len(pairs) > 5:
        return None
    names=set()
    for key,val in pairs:
        if key not in SAFE_QUERY_KEYS or key in names:
            return None
        if len(val) > 120 or not re.fullmatch(r"[a-zA-Z0-9 _.,+-]*", val):
            return None
        names.add(key)
    return urlencode(pairs)


def review_canonical_host_redirect(*, method: str, raw_host: str,
                                  raw_path: str, raw_query: str = "") -> dict[str, Any]:
    """Produce owner-review evidence; cannot redirect, mutate or activate.

    Caller must obtain the raw, single authoritative Host header itself.
    Never use X-Forwarded-Host or untrusted URL scheme for this decision.
    """
    plan = {
        "schema_version": SCHEMA,
        "state": "REVIEW_ONLY",
        "eligible_for_site_owner_review": False,
        "ineligible_reason": "protected_or_unverified_request",
        "proposed_http_status": None,
        "proposed_location": None,
        "gateway_owner_approval_required": True,
        "founder_release_approval_required": True,
        "redirect_executed": False,
        "gateway_modified": False,
        "public_site_published": False,
        "consumer_data_transferred": False,
        "authentication_route_modified": False,
        "execution_authority": "none",
    }
    if not isinstance(method,str) or method not in {"GET", "HEAD"}:
        return plan
    if not isinstance(raw_host,str) or raw_host != WWW_HOST:
        return plan
    if not isinstance(raw_path,str) or len(raw_path)>190 or not raw_path.startswith("/"):
        return plan
    if raw_path.startswith("//") or "\\" in raw_path or "%" in raw_path or ".." in raw_path:
        return plan
    if any(ord(c)<32 or ord(c)>126 for c in raw_path):
        return plan
    if not _approved_public_html_path(raw_path):
        return plan
    if not isinstance(raw_query,str):
        return plan
    preserved = _safe_query(raw_query)
    if preserved is None:
        return plan
    plan.update({
        "eligible_for_site_owner_review": True,
        "ineligible_reason": None,
        "proposed_http_status": 308,
        "proposed_location": ORIGIN + raw_path + ("?"+preserved if preserved else ""),
    })
    return plan
