"""Existing Search Fabric: bounded first-party source recovery.

Read only the original Agent Reach first-party evidence handoff. This is a
searchable source corpus, NOT a substitute for fresh general-web search.
No paid queries, invented buyer seats, PII expansion or commercial promotions.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import ipaddress
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

REPO = Path("/srv/empire_os")
SOURCE_PATH = Path(
    "runtime/execution_plane/results/agent_reach/first_party_market_review.json"
)
SOURCE_SCHEMA = "empire.agent-reach-buyer-handoff.v1"
TOPICS = frozenset((
    "roofing", "hvac", "solar", "plumbing", "legal", "insurance",
    "data", "mass_tort", "personal_injury",
    "lead", "call", "publisher", "buyer",
))
VERTICAL_ALIASES = {
    "roofing": {"roof", "roofing", "roofer", "roofers"},
    "hvac": {"hvac", "heating", "cooling", "airconditioning"},
    "solar": {"solar", "photovoltaic"},
    "plumbing": {"plumbing", "plumber", "plumbers"},
    "legal": {"legal", "lawyer", "lawyers", "attorney", "attorneys", "tort"},
    "insurance": {"insurance", "insurer"},
    "data": {"data", "dataset", "datasets", "firmographics", "brokerage"},
}
INTENT_ALIASES = {
    "lead": {"lead", "leads", "leadgen"},
    "call": {"call", "calls", "inbound", "transfer", "transfers"},
    "publisher": {"publisher", "publishers", "affiliate", "affiliates"},
    "buyer": {"buyer", "buyers", "buy", "purchase", "sell", "selling"},
}
MARKETS = {
    "USA": {"usa", "american", "america", "unitedstates"},
    "UK": {"uk", "britain", "british", "unitedkingdom"},
    "AU": {"au", "australia", "australian"},
    "CA": {"ca", "canada", "canadian"},
}
MAX_BYTES = 1_000_000


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def _hostname(url: Any) -> str:
    try:
        candidate = urlsplit(str(url or ""))
        host = (candidate.hostname or "").lower().removeprefix("www.")
        port = candidate.port
    except (ValueError, TypeError):
        return ""
    if (candidate.scheme != "https" or candidate.username or candidate.password
            or port not in (None, 443) or "." not in host):
        return ""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    return ""


def _query_scope(query: str) -> tuple[set[str], set[str], str | None, str | None]:
    tokens = _tokens(query)
    verticals = {
        k for k, variants in VERTICAL_ALIASES.items() if tokens & variants
    }
    intents = {k for k, variants in INTENT_ALIASES.items() if tokens & variants}
    scopes = {
        k for k, variants in MARKETS.items() if tokens & variants
    }
    sites = re.findall(r"(?i)\bsite:([a-z0-9.-]+)", query)
    host = sites[0].lower().removeprefix("www.") if len(sites) == 1 else None
    market = next(iter(scopes)) if len(scopes) == 1 else None
    # A conflicting or unsupported market query is not a licence to ignore it.
    if len(scopes) > 1 or len(sites) > 1:
        return set(), set(), None, "__INVALID__"
    return verticals, intents, market, host


def search_sources(
    query: str,
    *,
    num: int = 10,
    root: Path = REPO,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return separately labelled prior first-party source evidence only."""
    moment = now or datetime.now(timezone.utc)
    response: dict[str, Any] = {
        "organic": [],
        "searchParameters": {
            "q": query, "num": num, "engine": "first_party_source_recovery",
            "search_state": "NO_ELIGIBLE_FIRST_PARTY_EVIDENCE",
            "source_scope": "FIRST_PARTY_REVIEW_ONLY",
            "fresh_live_web_search": False, "quality_gate": "observed_topic_evidence_v1",
            "cache": False,
        },
        "credits_left": None,
    }
    if (moment.tzinfo is None or not isinstance(query, str)
            or not 4 <= len(query) <= 180
            or type(num) is not int or not 1 <= num <= 20):
        response["searchParameters"]["search_state"] = "INVALID_QUERY"
        return response
    verticals, intents, market, site = _query_scope(query)
    if site == "__INVALID__" or not intents or (not verticals and len(intents) < 2):
        return response
    source = root / SOURCE_PATH
    try:
        if (not source.is_file() or source.is_symlink() or source.stat().st_size > MAX_BYTES):
            return response
        raw = json.loads(source.read_text(encoding="utf-8"))
        if raw.get("schema_version") != SOURCE_SCHEMA or not isinstance(raw.get("sources"), dict):
            return response
    except (OSError, ValueError, TypeError):
        return response
    rows = []
    for domain, record in list(raw["sources"].items())[:100]:
        if not isinstance(record, dict) or not isinstance(domain, str):
            continue
        url = str(record.get("source_url") or "")
        if _hostname(url) != domain:
            continue
        if site and not (domain == site or domain.endswith("." + site)):
            continue
        if market and record.get("target_market") != market:
            continue
        if (record.get("status") != "FIRST_PARTY_OBSERVED"
                or record.get("source_class") != "FIRST_PARTY_PUBLIC_REVIEW"
                or record.get("buyer_accepted") is not False
                or record.get("outreach_authorized") is not False):
            continue
        try:
            age = moment - datetime.fromisoformat(str(record["observed_at"]))
            if not timedelta(0) <= age <= timedelta(hours=48):
                continue
        except (TypeError, ValueError, KeyError):
            continue
        topics = set(record.get("source_topics") or [])
        evidence = record.get("topic_evidence") or {}
        query_tokens = _tokens(query)
        # High-specificity legal niches need exact first-party evidence.
        if ("mass" in query_tokens and "tort" in query_tokens
                and "mass_tort" not in topics):
            continue
        if ("personal" in query_tokens and "injury" in query_tokens
                and "personal_injury" not in topics):
            continue
        if (not topics or not topics <= TOPICS or not isinstance(evidence, dict)
                or any(k not in evidence or not isinstance(evidence[k], list)
                       or not evidence[k]
                       or not all(_hostname(u) == domain for u in evidence[k])
                       for k in topics)):
            continue
        if verticals and not (verticals & topics):
            continue
        matched = intents & topics
        if not matched:
            continue
        # Niche-specific programme URLs are not interchangeable markets.
        # A roofing-only offer page must NEVER rank for solar, HVAC or legal.
        route_tokens = _tokens(urlsplit(url).path + " " + urlsplit(url).query)
        route_verticals = {
            k for k, aliases in VERTICAL_ALIASES.items()
            if aliases & route_tokens
        }
        if verticals and route_verticals and not (route_verticals & verticals):
            continue
        # A term observed in an unrelated footer or homepage cannot justify
        # returning an offer URL. Require the queried topic and intent on the
        # actual program page we link to, not merely somewhere on the site.
        if verticals and not any(url in evidence[k] for k in verticals & topics):
            continue
        if not any(url in evidence[k] for k in matched):
            continue
        if ("mass" in query_tokens and "tort" in query_tokens
                and url not in evidence.get("mass_tort", [])):
            continue
        if ("personal" in query_tokens and "injury" in query_tokens
                and url not in evidence.get("personal_injury", [])):
            continue
        # These are *observed terms* from first-party pages, not inferred
        # operating markets, available budgets or actual buying agreements.
        terms = sorted((verticals & topics) | matched)
        source_claims = [
            str(receipt.get("claim_excerpt") or "")[:150]
            for receipt in (record.get("claim_receipts") or [])[:5]
            if (isinstance(receipt, dict) and receipt.get("claim_excerpt")
                and receipt.get("source_url") == url)
        ]
        score = min(0.99, 0.42 + 0.18 * bool(verticals & topics)
                    + 0.11 * len(matched) + 0.05 * bool(market))
        rows.append({
            "title": f"{domain} — observed first-party source",
            "link": url,
            "snippet": ("Observed topics: " + ", ".join(terms) + ". "
                        + (source_claims[0] if source_claims else ""))[:350],
            "engine": "first_party_source_recovery",
            "source_class": "FIRST_PARTY_PUBLIC_REVIEW",
            "evidence_url": url,
            "observed_at": str(record["observed_at"]),
            "buyer_relationship": str(record.get("buyer_relationship") or "unknown"),
            "buyer_accepted": False,
            "outreach_authorized": False,
            "commercial_terms_verified": False,
            "fresh_live_web_search": False,
            "relevance_score": round(score, 4),
        })
    rows.sort(key=lambda r: (-r["relevance_score"], r["link"]))
    response["organic"] = [
        {**row, "position": i}
        for i, row in enumerate(rows[:num], 1)
    ]
    if rows:
        response["searchParameters"]["search_state"] = "INDEXED_FIRST_PARTY_EVIDENCE"
    return response
