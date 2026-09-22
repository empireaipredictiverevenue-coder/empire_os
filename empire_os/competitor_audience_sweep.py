"""OBSERVE-only competitor audience discovery over Empire Search Fabric.

Public comparison/listing evidence is converted into canonical Intelligence
Fabric signals for companies whose identity is already resolved. This module
never creates prospects, infers buyer/commercial intent, or enables outreach.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from empire_os.competitive_intelligence import (
    build_competitor_audience_graph,
    competitor_audience_intelligence_signal,
)
from empire_os.intelligence_materializer_transport import (
    COMPETITOR_AUDIENCE_SOURCE_KEY,
    ROLE,
    PostgresIntelligenceMaterializer,
    persist_competitor_audience_signal,
)
from empire_os.search_fabric.search import search as search_web


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
    "(Empire-OS/3.0; +https://empire-ai.co.uk)"
)

_COMPARISON_TERMS = (
    "best ",
    "top ",
    "compare",
    "comparison",
    "alternatives",
    "companies",
    "contractors",
    "providers",
    "reviews",
    "directory",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _domain(value: Any) -> str:
    text = _clean(value).lower()
    if not text:
        return ""
    if text.startswith("//"):
        text = "https:" + text
    elif "://" not in text:
        text = "https://" + text
    host = (urlparse(text).hostname or "").lower().rstrip(".")
    return host.removeprefix("www.")


def _normalise_words(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _clean(value).lower()))


def _is_public_http_url(value: Any) -> bool:
    try:
        parsed = urlparse(_clean(value))
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
    )


def _host_resolves_public(host: str) -> bool:
    try:
        addresses = socket.getaddrinfo(host, None)
    except OSError:
        return False

    found = False
    for row in addresses:
        address = row[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False
        found = True
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
        ):
            return False
    return found


class _PageText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hrefs: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            self._skip += 1
        if lowered == "a":
            for key, value in attrs:
                if key.lower() == "href" and value:
                    self.hrefs.append(str(value))

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def fetch_public_html(
    url: str,
    *,
    timeout: float = 8.0,
    max_bytes: int = 750_000,
) -> str | None:
    """Fetch bounded public HTML only."""
    if not _is_public_http_url(url):
        return None
    host = urlparse(url).hostname or ""
    if not _host_resolves_public(host):
        return None

    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(
            request,
            timeout=max(1.0, min(float(timeout), 20.0)),
        ) as response:
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type.lower():
                return None
            raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raw = raw[:max_bytes]
            return raw.decode("utf-8", errors="ignore")
    except Exception:
        return None


def _page_projection(html: str) -> tuple[str, list[str]]:
    parser = _PageText()
    parser.feed(html)
    return _normalise_words(" ".join(parser.parts)), parser.hrefs


def _identity_observed(
    *,
    text: str,
    hrefs: Iterable[str],
    name: str,
    domain: str,
) -> bool:
    normalized_name = _normalise_words(name)
    normalized_domain = _domain(domain)

    if normalized_name and len(normalized_name) >= 4:
        if normalized_name in text:
            return True

    if normalized_domain:
        for href in hrefs:
            if _domain(href) == normalized_domain:
                return True

    return False


def _comparison_like(*values: Any) -> bool:
    joined = " ".join(_clean(value).lower() for value in values)
    return any(term in joined for term in _COMPARISON_TERMS)


SearchFn = Callable[..., Mapping[str, Any]]
FetchFn = Callable[[str], str | None]


def discover_competitor_audience_evidence(
    *,
    competitor_key: str,
    competitor_name: str,
    competitor_domain: str,
    market_query: str,
    candidates: Iterable[Mapping[str, Any]],
    search_fn: SearchFn = search_web,
    fetch_fn: FetchFn = fetch_public_html,
    max_results_per_query: int = 8,
    max_pages: int = 12,
    observed_at: str | None = None,
) -> list[dict[str, Any]]:
    """Find public pages that explicitly mention competitor and company."""
    key = _clean(competitor_key)
    name = _clean(competitor_name)
    domain = _domain(competitor_domain)
    market = _clean(market_query)

    if not key:
        raise ValueError("competitor_key_required")
    if not name and not domain:
        raise ValueError("competitor_identity_required")
    if not market:
        raise ValueError("market_query_required")

    candidate_rows = [
        {
            "entity_id": _clean(row.get("entity_id") or row.get("id")),
            "company_name": _clean(
                row.get("company_name") or row.get("canonical_name")
            ),
            "company_domain": _domain(
                row.get("company_domain")
                or row.get("canonical_website")
            ),
        }
        for row in candidates
        if isinstance(row, Mapping)
    ]

    timestamp = observed_at or datetime.now(timezone.utc).isoformat()
    queries = [
        f"best {market}",
        f"top {market} companies",
        f"{market} comparison",
        f"{market} reviews",
    ]

    pages: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for query in queries:
        result = search_fn(
            query,
            num=max(1, min(int(max_results_per_query), 20)),
        )
        if not isinstance(result, Mapping):
            continue

        for row in result.get("organic", []) or []:
            if not isinstance(row, Mapping):
                continue
            url = _clean(row.get("link") or row.get("url"))
            if not url or url in seen_urls or not _is_public_http_url(url):
                continue
            if not _comparison_like(
                row.get("title"),
                row.get("snippet"),
                url,
            ):
                continue

            seen_urls.add(url)
            pages.append({
                "url": url,
                "title": _clean(row.get("title")),
                "snippet": _clean(row.get("snippet")),
                "query": query,
            })

            if len(pages) >= max(1, int(max_pages)):
                break

        if len(pages) >= max(1, int(max_pages)):
            break

    evidence: list[dict[str, Any]] = []
    seen_evidence: set[tuple[str, str]] = set()

    for page in pages:
        html = fetch_fn(page["url"])
        if not html:
            continue

        text, hrefs = _page_projection(html)
        if not _comparison_like(
            page["title"],
            page["snippet"],
            page["url"],
            text,
        ):
            continue

        if not _identity_observed(
            text=text,
            hrefs=hrefs,
            name=name,
            domain=domain,
        ):
            continue

        for company in candidate_rows:
            entity_id = company["entity_id"]
            company_name = company["company_name"]
            company_domain = company["company_domain"]

            if not entity_id or (not company_name and not company_domain):
                continue
            if company_domain and company_domain == domain:
                continue

            if not _identity_observed(
                text=text,
                hrefs=hrefs,
                name=company_name,
                domain=company_domain,
            ):
                continue

            dedupe_key = (entity_id, page["url"])
            if dedupe_key in seen_evidence:
                continue
            seen_evidence.add(dedupe_key)

            evidence.append({
                "entity_id": entity_id,
                "competitor_key": key,
                "competitor_domain": domain,
                "company_name": company_name,
                "company_domain": company_domain,
                "evidence_type": "comparison_mention",
                "summary": (
                    f"{company_name or company_domain} and "
                    f"{name or domain} were both observed on the same "
                    "public comparison/listing page."
                ),
                "source_ref": page["url"],
                "observed_at": timestamp,
                "confidence": 0.90,
                "search_query": page["query"],
            })

    return evidence


def load_resolved_market_entities(
    writer: PostgresIntelligenceMaterializer,
    *,
    niche: str,
    metro: str,
    limit: int = 250,
) -> list[dict[str, Any]]:
    """Read already-resolved companies only; never creates identities."""
    niche_text = _clean(niche)
    metro_text = _clean(metro)
    if not niche_text or not metro_text:
        raise ValueError("niche_and_metro_required")

    with writer._connect(writer.dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {ROLE}")
            cursor.execute(
                """
                SELECT id, canonical_name, canonical_website
                FROM public.business_entities
                WHERE resolution_state='evidence_resolved_candidate'
                  AND identity_confidence >= 0.8
                  AND canonical_niche ILIKE %s
                  AND canonical_metro ILIKE %s
                ORDER BY identity_confidence DESC, canonical_name
                LIMIT %s
                """,
                (
                    f"%{niche_text}%",
                    f"%{metro_text}%",
                    max(1, min(int(limit), 1000)),
                ),
            )
            return [
                {
                    "entity_id": str(row[0]),
                    "company_name": row[1] or "",
                    "company_domain": _domain(row[2]),
                }
                for row in cursor.fetchall()
            ]


def load_competitor_audience_source_id(
    writer: PostgresIntelligenceMaterializer,
) -> str:
    with writer._connect(writer.dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {ROLE}")
            return writer._source_id(
                cursor,
                COMPETITOR_AUDIENCE_SOURCE_KEY,
            )


def run_competitor_audience_sweep(
    *,
    writer: PostgresIntelligenceMaterializer,
    competitor_key: str,
    competitor_name: str,
    competitor_domain: str,
    market_query: str,
    niche: str,
    metro: str,
    persist: bool = False,
    search_fn: SearchFn = search_web,
    fetch_fn: FetchFn = fetch_public_html,
) -> dict[str, Any]:
    candidates = load_resolved_market_entities(
        writer,
        niche=niche,
        metro=metro,
    )

    evidence = discover_competitor_audience_evidence(
        competitor_key=competitor_key,
        competitor_name=competitor_name,
        competitor_domain=competitor_domain,
        market_query=market_query,
        candidates=candidates,
        search_fn=search_fn,
        fetch_fn=fetch_fn,
    )

    graph = build_competitor_audience_graph(evidence)

    entity_by_identity: dict[str, str] = {}
    for row in candidates:
        domain = _domain(row.get("company_domain"))
        name = _normalise_words(row.get("company_name"))
        if domain:
            entity_by_identity[f"domain:{domain}"] = row["entity_id"]
        if name:
            entity_by_identity[f"name:{name}"] = row["entity_id"]

    source_id = load_competitor_audience_source_id(writer)
    signals: list[dict[str, Any]] = []
    persisted: list[dict[str, Any]] = []

    for company in graph["companies"]:
        identity = _clean(company.get("identity_key"))
        entity_id = entity_by_identity.get(identity)
        if entity_id is None and company.get("company_name"):
            entity_id = entity_by_identity.get(
                f"name:{_normalise_words(company['company_name'])}"
            )
        if not entity_id:
            continue

        signal = competitor_audience_intelligence_signal(
            company,
            entity_id=entity_id,
            source_id=source_id,
        )
        signals.append(signal)

        if persist:
            persisted.append(
                persist_competitor_audience_signal(writer, signal)
            )

    return {
        "schema_version": "empire.competitor_audience_sweep.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "market_query": _clean(market_query),
        "niche": _clean(niche),
        "metro": _clean(metro),
        "candidate_count": len(candidates),
        "evidence_count": len(evidence),
        "graph_company_count": graph["company_count"],
        "signal_count": len(signals),
        "persist_requested": bool(persist),
        "persisted_count": sum(
            1 for row in persisted if row.get("inserted") is True
        ),
        "existing_count": sum(
            1 for row in persisted if row.get("existing") is True
        ),
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_enabled": False,
        "evidence": evidence,
        "signals": signals,
        "persistence": persisted,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="OBSERVE-only Empire competitor audience sweep"
    )
    parser.add_argument("--competitor-key", required=True)
    parser.add_argument("--competitor-name", required=True)
    parser.add_argument("--competitor-domain", required=True)
    parser.add_argument("--market-query", required=True)
    parser.add_argument("--niche", required=True)
    parser.add_argument("--metro", required=True)
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persist evidence signals only; never creates prospects/outreach.",
    )
    args = parser.parse_args()

    writer = PostgresIntelligenceMaterializer.from_env()
    result = run_competitor_audience_sweep(
        writer=writer,
        competitor_key=args.competitor_key,
        competitor_name=args.competitor_name,
        competitor_domain=args.competitor_domain,
        market_query=args.market_query,
        niche=args.niche,
        metro=args.metro,
        persist=args.persist,
    )

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
