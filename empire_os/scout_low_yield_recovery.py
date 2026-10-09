"""Fail-closed canonical research supplement when public search yield collapses.

Selection does not verify a business, contact or buyer; first-party site
observation and the regular holding/review gates remain mandatory.
"""
from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlsplit
from uuid import UUID
import re

HOSTNAME = re.compile(r"[a-z0-9](?:[a-z0-9.-]{1,251})[a-z0-9]\Z")
SUPPORTED_ICP = frozenset({
    "high_ticket_home_service",
    "legal_mass_tort_plaintiff_firm",
    "legal_plaintiff_growth_firm",
    "insurance_distribution_growth",
    "predictive_revenue_home_services_platform",
    "predictive_revenue_franchise_network",
    "predictive_revenue_portfolio_value_creation",
})
EXCLUDED = frozenset({"search.google", "cybo.com"})


def safe_company_host(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 500:
        return ""
    try:
        url = urlsplit(value)
        if (
            url.scheme not in {"http", "https"} or url.username or url.password
            or url.query or url.fragment or url.port not in {None, 80, 443}
        ):
            return ""
        host = (url.hostname or "").lower().rstrip(".").removeprefix("www.")
        if (
            not HOSTNAME.fullmatch(host) or "." not in host or ".." in host
            or any(label.startswith("-") or label.endswith("-") for label in host.split("."))
            or host in EXCLUDED
        ):
            return ""
        return host
    except ValueError:
        return ""


def select_low_yield_canonical_domains(
    canonical_seed_records: list[Mapping[str, Any]] | None,
    *,
    search_domains: set[str],
    query_count: int,
    search_enabled: bool,
    limit: int,
    low_yield_ceiling: int = 2,
) -> tuple[str, ...]:
    """Reserve at most 3 canonical prospect websites for first-party research.

    Only runs in explicitly opted-in production Scout when 1..2 valid primary
    search domains survive. Empty-search fallback is handled by legacy Scout.
    """
    budget = max(0, min(int(limit), 3))
    if (
        not search_enabled or query_count <= 0 or not budget
        or not 0 < len(search_domains) <= min(low_yield_ceiling, 2)
    ):
        return ()
    candidates: list[str] = []
    seen: set[str] = set()
    for row in (canonical_seed_records or [])[:100]:
        if not isinstance(row, Mapping):
            continue
        if row.get("seed_opportunity_key") or row.get("seed_intent_signal_id"):
            continue  # Existing special-source rules are unchanged.
        host = safe_company_host(row.get("website"))
        if not host or host in search_domains or host in seen:
            continue
        if str(row.get("icp_profile_key") or "") not in SUPPORTED_ICP:
            continue
        name = " ".join(str(row.get("business_name") or "").split())
        if len(name) < 5 or name.casefold() in {
            "home", "contact", "services", "about us", "test",
        }:
            continue
        identifier = row.get("id")
        if not isinstance(identifier, str):
            continue
        try:
            if str(UUID(identifier)) != identifier.lower():
                continue
        except (ValueError, AttributeError):
            continue
        seen.add(host)
        candidates.append(host)
        if len(candidates) >= budget:
            break
    return tuple(candidates)
