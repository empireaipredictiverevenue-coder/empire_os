"""First-party, evidence-labelled GSC/page corpus for existing Empire SEO.

Consumes the existing Search Console read API contract and observed public page
metadata. Does NOT retrieve data, grant SEO authority, publish pages, claim
indexing, infer Google volume, or equate query observations with revenue.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit
import re

from empire_os.semantic_keyword_search import SemanticSearchInputError


DOMAIN = "empire-ai.co.uk"
PROPERTY = "sc-domain:empire-ai.co.uk"


@dataclass(frozen=True)
class PageSpec:
    path: str
    product_key: str
    cluster_key: str
    intent_class: str
    funnel_stage: str
    icp_key: str
    cta_key: str
    territory_key: str | None = None

    @property
    def url(self) -> str:
        return "https://" + DOMAIN + self.path


# Exact approved routes; avoid auto-classifying historical AEO URLs as leads.
PRIORITY_PAGES: tuple[PageSpec, ...] = (
    PageSpec("/industries/roofing", "roofing", "commercial-roofing",
             "commercial", "conversion", "commercial-roofing-operator",
             "commercial-enquiry"),
    PageSpec("/industries/solar", "solar", "solar-installer-demand",
             "commercial", "conversion", "solar-installer",
             "commercial-enquiry"),
    PageSpec("/industries/hvac", "hvac", "hvac-demand",
             "commercial", "conversion", "hvac-operator",
             "commercial-enquiry"),
    PageSpec("/predictive-revenue", "predictive-revenue-os",
             "predictive-revenue", "product", "evaluation",
             "b2b-revenue-leader", "commercial-enquiry"),
)


class _PageTags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.canonical: str | None = None
        self.description: str | None = None
        self.noindex = False
        self._current: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        fields = {k.lower(): (v or "") for k, v in attrs}
        if tag in {"title", "h1"}:
            self._current = tag
        if tag == "link" and fields.get("rel", "").casefold().strip() == "canonical":
            self.canonical = fields.get("href")
        if tag == "meta":
            name = fields.get("name", "").casefold().strip()
            if name == "description":
                self.description = fields.get("content")
            if name in {"robots", "googlebot"} and re.search(
                r"(?<![a-z])noindex(?![a-z])", fields.get("content", ""), re.I
            ):
                self.noindex = True

    def handle_endtag(self, tag: str) -> None:
        if tag == self._current:
            self._current = None

    def handle_data(self, data: str) -> None:
        if self._current == "title":
            self.title_parts.append(data)
        elif self._current == "h1":
            self.h1_parts.append(data)


def _site_url(url: str) -> str:
    try:
        p = urlsplit(url)
    except ValueError:
        return ""
    host = (p.hostname or "").casefold()
    if (p.scheme != "https" or host != DOMAIN or p.username or p.password
            or p.query or p.fragment or p.port not in (None, 443)):
        return ""
    return "https://" + DOMAIN + p.path.rstrip("/") + ("/" if p.path == "/" else "")


def _gsc_owned_url(url: str) -> str:
    """Normalise *owned* GSC URL aliases for comparison, not as a redirect claim.

    Source URL survives in every receipt; HTTP/www observations are NOT
    evidence that an apex redirect has been configured or published.
    """
    try:
        p = urlsplit(url)
        host = (p.hostname or "").casefold()
        port = p.port
    except ValueError:
        return ""
    if (p.scheme not in {"http", "https"}
            or host not in {DOMAIN, "www." + DOMAIN}
            or p.username or p.password or p.query or p.fragment
            or (port is not None and port != (443 if p.scheme == "https" else 80))):
        return ""
    path = p.path.rstrip("/") or "/"
    return "https://" + DOMAIN + path


def page_record(spec: PageSpec, *, html: str, http_status: int) -> dict[str, Any]:
    """Parse only a known live owned route; every page must have evidence."""
    if not isinstance(html, str):
        raise SemanticSearchInputError("HTML must be text")
    if len(html) > 2_000_000:
        raise SemanticSearchInputError("page HTML larger than bounded import")
    parser = _PageTags()
    parser.feed(html)
    title = " ".join(" ".join(parser.title_parts).split())
    h1 = " ".join(" ".join(parser.h1_parts).split())
    valid = (
        http_status == 200 and _site_url(parser.canonical or "") == spec.url
        and bool(title) and bool(h1) and not parser.noindex
    )
    receipt = "owned-html-sha256:" + sha256(html.encode("utf-8")).hexdigest()
    return {
        "canonical_url": spec.url,
        "title": title,
        "h1": h1,
        "target_query": None,  # No invented keyword targeting from title.
        "topic": spec.cluster_key,
        "product_key": spec.product_key,
        "territory_key": spec.territory_key,
        "search_intent": spec.intent_class,
        "funnel_stage": spec.funnel_stage,
        "evidence_refs": [receipt],
        "http_status": http_status,
        "canonical_observed": parser.canonical,
        "noindex_observed": parser.noindex,
        "content_body_reviewed": False,
        "eligible_for_local_topic_review": bool(valid),
        "reason": None if valid else "page_http_canonical_title_or_noindex_gate",
    }


def _numeric(value: Any, *, allow_float: bool = True) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    number = float(value)
    if number < 0 or number != number or number == float("inf"):
        return None
    return number if allow_float else float(int(number)) if number.is_integer() else None


def prepare_first_party_semantic_corpus(
    search_console: Mapping[str, Any],
    pages: Sequence[Mapping[str, Any]],
    *,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Return distinct real GSC query observations and unmeasured page seeds.

    Only query/page rows for exact declared routes can be mapped to products.
    Other first-party observations remain in 'unmapped' — not discarded, and
    not labelled buyer-qualified. GSC samples do not equal sitewide totals.
    """
    if not isinstance(search_console, Mapping) or (
        search_console.get("source") != "google_search_console"
        or search_console.get("site_url") != PROPERTY
        or search_console.get("available") is not True
    ):
        raise SemanticSearchInputError("authenticated first-party GSC response required")
    if not isinstance(start_date, str) or not isinstance(end_date, str) or (
        not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start_date)
        or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end_date)
        or end_date < start_date
    ):
        raise SemanticSearchInputError("bounded date window required")
    items = search_console.get("items")
    if not isinstance(items, list) or len(items) > 10000:
        raise SemanticSearchInputError("GSC observations must be a bounded items array")
    spec_by_url = {spec.url: spec for spec in PRIORITY_PAGES}
    page_by_url: dict[str, Mapping[str, Any]] = {}
    for raw in pages:
        if not isinstance(raw, Mapping):
            raise SemanticSearchInputError("page inventory must contain mappings")
        url = str(raw.get("canonical_url") or "")
        if url not in spec_by_url or url in page_by_url:
            raise SemanticSearchInputError("unknown or duplicate page route")
        page_by_url[url] = raw

    seen_pairs = set()
    total_impressions = 0
    mapped: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    for row in items:
        if not isinstance(row, Mapping):
            raise SemanticSearchInputError("invalid GSC row")
        keys = row.get("keys")
        if not isinstance(keys, list) or len(keys) != 2:
            raise SemanticSearchInputError("GSC query/page dimensions required")
        query, original_url = keys
        if not isinstance(query, str) or not isinstance(original_url, str):
            raise SemanticSearchInputError("GSC keys must be strings")
        query = " ".join(query.split())
        url = _gsc_owned_url(original_url)
        if not query or not url:
            raise SemanticSearchInputError("GSC query/page URL missing or not first-party")
        pair = (query.casefold(), original_url)
        if pair in seen_pairs:
            raise SemanticSearchInputError("duplicate GSC query/page result")
        seen_pairs.add(pair)
        clicks = _numeric(row.get("clicks"), allow_float=False)
        impressions = _numeric(row.get("impressions"), allow_float=False)
        position = _numeric(row.get("position"))
        if (clicks is None or impressions is None or clicks > impressions):
            raise SemanticSearchInputError("invalid GSC click/impression metrics")
        total_impressions += int(impressions)
        evidence = "gsc-row-sha256:" + sha256(
            f"{PROPERTY}|{start_date}|{end_date}|{query}|{original_url}|{int(clicks)}|{int(impressions)}|{position}".encode()
        ).hexdigest()
        base = {
            "query": query,
            "page_url": url,
            "gsc_observed_page_url": original_url,
            "query_page_impressions": int(impressions),
            "query_page_clicks": int(clicks),
            "reported_average_position": position,
            "evidence_refs": [evidence],
            "source": "google_search_console",
            "date_window": [start_date, end_date],
            "buyer_intent_verified": False,
            "revenue_verified": False,
        }
        spec = spec_by_url.get(url)
        observed_page = page_by_url.get(url)
        if not spec or not observed_page or not observed_page.get("eligible_for_local_topic_review"):
            unmapped.append({**base, "mapping_status": "UNMAPPED_OR_PAGE_UNVERIFIED"})
            continue
        mapped.append({
            "keyword": query,
            "cluster_key": spec.cluster_key,
            "intent_class": spec.intent_class,
            "product_key": spec.product_key,
            "icp_key": spec.icp_key,
            "funnel_stage": spec.funnel_stage,
            "cta_key": spec.cta_key,
            "territory_key": spec.territory_key,
            "evidence_refs": [evidence, *observed_page["evidence_refs"]],
            "source_evidence_kind": "GSC_QUERY_PAGE",
            "gsc_query_page_impressions": int(impressions),
            "gsc_query_page_clicks": int(clicks),
            "gsc_reported_average_position": position,
            "observed_demand": None,
            "buyer_fit": None,
            "conversion_evidence": None,
            "realized_revenue": None,
        })

    # Reject cross-page duplicates rather than pretending one query has
    # a single unambiguous commercial product.
    by_keyword: dict[str, list[dict[str, Any]]] = {}
    for rec in mapped:
        by_keyword.setdefault(rec["keyword"].casefold(), []).append(rec)
    ambiguous_keywords = sorted(
        {k for k, group in by_keyword.items() if len(group) > 1}
    )
    mapped = [
        row for row in mapped if row["keyword"].casefold() not in ambiguous_keywords
    ]
    for k in ambiguous_keywords:
        for row in by_keyword[k]:
            unmapped.append({
                "query": row["keyword"],
                "page_url": next(
                    (u for u, spec in spec_by_url.items()
                     if spec.product_key == row["product_key"]), None
                ),
                "evidence_refs": row["evidence_refs"],
                "mapping_status": "AMBIGUOUS_MULTIPLE_PAGES",
            })

    title_seeds = []
    verified_pages = []
    for spec in PRIORITY_PAGES:
        page = page_by_url.get(spec.url)
        if not page or not page.get("eligible_for_local_topic_review"):
            continue
        verified_pages.append(dict(page))
        title = re.sub(r"\s*[|–-]\s*Empire AI\s*$", "", str(page["title"]), flags=re.I).strip()
        if not title:
            continue
        title_seeds.append({
            "keyword": title,
            "cluster_key": spec.cluster_key,
            "intent_class": spec.intent_class,
            "product_key": spec.product_key,
            "icp_key": spec.icp_key,
            "funnel_stage": spec.funnel_stage,
            "cta_key": spec.cta_key,
            "territory_key": spec.territory_key,
            "evidence_refs": list(page["evidence_refs"]),
            "source_evidence_kind": "PAGE_TITLE_UNMEASURED",
            "observed_demand": None,
            "buyer_fit": None,
            "conversion_evidence": None,
            "realized_revenue": None,
        })
    return {
        "schema_version": "first_party_semantic_corpus.v1",
        "source": "google_search_console_plus_owned_page_metadata",
        "mode": "OBSERVE",
        "site_property": PROPERTY,
        "date_window": [start_date, end_date],
        "returned_query_page_rows": len(items),
        "returned_query_page_impressions": total_impressions,
        "mapped_gsc_keywords": mapped,
        "unmapped_gsc_query_pages": unmapped,
        "ambiguous_gsc_keywords": ambiguous_keywords,
        "unmeasured_page_title_seeds": title_seeds,
        "evidenced_page_inventory": verified_pages,
        "inventory_claimed_complete": False,
        "sitewide_search_demand_inferred": False,
        "commercial_intent_from_query_verified": False,
        "published_content_changed": False,
    }
