"""Bounded first-party sitemap/indexability analysis; no indexation authority.

A successful HTTP page + self-canonical is an indexability *signal*, not
Google indexing, quality, ranking, buyer intent or revenue evidence.
"""
from __future__ import annotations

from datetime import datetime
import ipaddress
import re
from typing import Any, Mapping
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

_SITE = "empire-ai.co.uk"
_ORIGIN = "https://" + _SITE
_MAX_SITEMAP_BYTES = 120_000
_MAX_PAGES = 50
_EXPECTED_GATED = {
    "/roofing": "BUYER_LEADSMART_NO_INDEX",
    "/roofing/replacement-vs-repair": "NEW_BUYER_GUIDE_NOT_RELEASED",
    "/roofing/installation-checklist": "NEW_BUYER_GUIDE_NOT_RELEASED",
    "/research/agent-governance": "RESEARCH_EDITORIAL_HOLD",
    "/privacy": "LEGAL_OWNER_VERIFICATION_REQUIRED",
    "/terms": "LEGAL_OWNER_VERIFICATION_REQUIRED",
}
_AEO_MAXIMUM_ROUTES = 10


def _owned_url(url: Any) -> str:
    if not isinstance(url, str) or len(url) > 2000 or any(c.isspace() for c in url):
        raise ValueError("invalid_owned_sitemap_url")
    try:
        loc = urlsplit(url)
        if (loc.scheme != "https" or loc.hostname != _SITE
            or loc.username is not None or loc.password is not None
            or loc.port is not None or loc.fragment or loc.query
            or (loc.path and not loc.path.startswith("/"))):
            raise ValueError("invalid_owned_sitemap_url")
    except ValueError:
        raise ValueError("invalid_owned_sitemap_url") from None
    return loc.path or "/"


def _normalised_path(value: str) -> str:
    return value.rstrip("/") or "/"


def analyse_owned_indexability(
    *, sitemap: bytes, robots: bytes, pages: list[Mapping[str, Any]],
    gated_pages: list[Mapping[str, Any]], observed_at: str,
) -> dict[str, Any]:
    if not isinstance(sitemap, bytes) or len(sitemap) > _MAX_SITEMAP_BYTES:
        raise ValueError("invalid_bounded_sitemap")
    if not isinstance(robots, bytes) or len(robots) > 32_000:
        raise ValueError("invalid_bounded_robots")
    try:
        time = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if time.tzinfo is None:
            raise ValueError()
    except (AttributeError, ValueError):
        raise ValueError("indexability_observation_requires_aware_timestamp") from None
    try:
        sitemap_tree = ET.fromstring(sitemap)
    except ET.ParseError:
        raise ValueError("invalid_sitemap_xml") from None
    if not sitemap_tree.tag.endswith("urlset"):
        raise ValueError("urlset_sitemap_required")
    nodes = sitemap_tree.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url")
    if not 1 <= len(nodes) <= _MAX_PAGES:
        raise ValueError("unbounded_sitemap_url_count")
    sitemap_urls = []
    for node in nodes:
        children = node.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        if len(children) != 1 or not children[0].text:
            raise ValueError("missing_sitemap_location")
        url = children[0].text
        _owned_url(url)
        if url in sitemap_urls:
            raise ValueError("duplicate_owned_sitemap_url")
        sitemap_urls.append(url)
    if not isinstance(pages, list) or len(pages) != len(sitemap_urls):
        raise ValueError("sitemap_must_have_exact_observations")
    by_url={}
    for row in pages:
        if not isinstance(row, Mapping):
            raise ValueError("invalid_sitemap_page_evidence")
        url=row.get("url")
        _owned_url(url)
        if url in by_url or url not in sitemap_urls:
            raise ValueError("unmatched_or_duplicate_sitemap_observation")
        by_url[url]=row
    if not isinstance(gated_pages,list) or len(gated_pages) != len(_EXPECTED_GATED):
        raise ValueError("explicit_gated_route_observations_required")
    gate={}
    for row in gated_pages:
        if not isinstance(row,Mapping):
            raise ValueError("invalid_gated_page_evidence")
        path=row.get("path")
        if path not in _EXPECTED_GATED or path in gate:
            raise ValueError("unexpected_duplicate_or_missing_gate")
        gate[path]=row
    if set(gate) != set(_EXPECTED_GATED):
        raise ValueError("missing_explicit_gates")
    for path,row in gate.items():
        if row.get("http") is None:
            # Provider/DNS errors are UNKNOWN, not a proof of secure gating.
            raise ValueError("gated_route_fetch_unavailable")
        if type(row["http"]) is not int:
            raise ValueError("invalid_gated_http_status")
    blocked_leadsmart=gate["/roofing"]
    allowed_block_status = (
        blocked_leadsmart["http"] == 200 and (
            "noindex" in " ".join(blocked_leadsmart.get("html_robots") or []).casefold()
            or "noindex" in " ".join(blocked_leadsmart.get("xrobots") or []).casefold()
        )
    )
    if not allowed_block_status:
        raise ValueError("leadsmart_buyer_landing_accidentally_indexable_or_unavailable")
    # Publication of legal pages is a separate website/legal decision, NOT
    # a buyer funnel activation. Previously we required both legal URLs to
    # be 404; they have since become publicly available. Observe this truth
    # without retroactively asserting policy sign-off or hiding them.
    unreleased = {
        "/roofing/replacement-vs-repair",
        "/roofing/installation-checklist",
        "/research/agent-governance",
    }
    for path in unreleased:
        if gate[path]["http"] not in {404, 410}:
            raise ValueError("unreleased_or_legal_route_in_public_view")
    legal_public = []
    for path in ("/privacy", "/terms"):
        row = gate[path]
        status = row["http"]
        if status not in (200, 404, 410):
            raise ValueError("legal_page_unexpected_http_status")
        if status != 200:
            legal_public.append({
                "path": path, "observed_http": status,
                "status": "NOT_PUBLIC", "canonical_present": False,
                "legal_owner_release_verified": False,
                "page_publication_mutation_allowed": False,
            })
            continue
        canonicals = row.get("canonical") or []
        if not isinstance(canonicals, list) or len(canonicals) > 2:
            raise ValueError("legal_page_malformed_canonical_evidence")
        canonical_match = len(canonicals) == 1 and (
            canonicals[0] == _ORIGIN + path
            or canonicals[0] == _ORIGIN + path + "/"
        )
        title = row.get("title")
        h1 = row.get("h1_count")
        metadata_complete = (
            isinstance(title, str) and bool(title.strip())
            and type(h1) is int and h1 >= 1
        )
        legal_public.append({
            "path": path, "observed_http": 200,
            "status": (
                "PUBLIC_TECHNICAL_SIGNALS_PRESENT_REVIEW_ONLY"
                if canonical_match and metadata_complete
                else "PUBLIC_TECHNICAL_METADATA_INCOMPLETE"
            ),
            "canonical_present": canonical_match,
            "title_and_h1_present": metadata_complete,
            "legal_owner_release_verified": False,
            "page_publication_mutation_allowed": False,
        })
    if any(_ORIGIN+p in sitemap_urls for p in gate):
        raise ValueError("gated_content_must_not_appear_in_sitemap")
    try:
        robots_text=robots.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("malformed_robots_encoding") from None
    if "Sitemap: "+_ORIGIN+"/sitemap.xml" not in robots_text:
        raise ValueError("sitemap_not_advertised_in_robots")
    robots_directives=re.findall(r"(?im)^\s*Disallow:\s*(.*?)\s*$",robots_text)
    if "/" in robots_directives:
        raise ValueError("sitewide_disallow_in_robots")
    results=[]
    aeo_routes=0
    for url in sitemap_urls:
        evidence=by_url[url]
        observed_status=evidence.get("http")
        if type(observed_status) is not int:
            status="FETCH_UNKNOWN"
        elif observed_status != 200:
            status="HTTP_NOT_200"
        else:
            html_meta=evidence.get("html_robots")
            x_meta=evidence.get("xrobots")
            canon=evidence.get("canonical")
            h1=evidence.get("h1_count")
            title=evidence.get("title")
            if (
                not isinstance(html_meta,list) or not isinstance(x_meta,list)
                or not isinstance(canon,list) or type(h1) is not int
                or not isinstance(title,str)
            ):
                raise ValueError("incomplete_html_indexability_observation")
            robots_directives_page=" ".join(html_meta+x_meta).lower()
            if "noindex" in robots_directives_page:
                status="NOINDEX_SITEMAP_CONFLICT"
            elif len(canon)!=1:
                status="MISSING_OR_DUPLICATE_CANONICAL"
            else:
                try:canonical_path=_owned_url(canon[0])
                except ValueError:canonical_path=None
                if (canonical_path is None
                    or _normalised_path(canonical_path)!=_normalised_path(_owned_url(url))):
                    status="CANONICAL_POINTS_ELSEWHERE"
                elif h1 < 1 or not title.strip():
                    status="PAGE_TITLE_OR_HEADING_MISSING"
                else:
                    status="FETCHED_INDEXABILITY_SIGNALS_PRESENT"
        path=_owned_url(url)
        if path.startswith("/aeo/"):
            aeo_routes+=1
        results.append({
            "url":url,
            "observed_http":observed_status if type(observed_status) is int else None,
            "signal_status":status,
            "google_indexing_verified":False,
            "ranking_verified":False,
            "crawlability_is_not_commercial_conversion":True,
        })
    if aeo_routes > _AEO_MAXIMUM_ROUTES:
        raise ValueError("unbounded_aeo_sitemap_inclusion")
    problems=[r for r in results if r["signal_status"]!="FETCHED_INDEXABILITY_SIGNALS_PRESENT"]
    # Historical `expected_gated` key retained for downstream compatibility.
    # Legal page visibility is reported separately: HTTP 200 is observable,
    # not authorisation, and must not be described as a 404 security gate.
    holds={
        p:{"reason":_EXPECTED_GATED[p],"observed_http":gate[p]["http"],
           "publication_allowed":False,"remove_noindex_authorized":False,
           "public_visibility_observed": p in {"/privacy", "/terms"} and gate[p]["http"] == 200,
           "legal_owner_release_verified": False if p in {"/privacy", "/terms"} else None,
        }
        for p in sorted(gate)
    }
    return {
        "schema_version":"empire.search.owned_indexability_review.v1",
        "tenant_id":"empire-ai","site_id":_SITE,"mode":"OBSERVE",
        "observed_at":time.isoformat(),
        "sitemap_url_count":len(sitemap_urls),
        "sitemap_indexability_signal_count":len(results)-len(problems),
        "needs_technical_review_count":len(problems),
        "probed_aeo_routes":aeo_routes,
        "indexability_signal_observations":results,
        "technical_issues":problems,
        "expected_gated":holds,
        "published_legal_pages_review":legal_public,
        "legal_publication_approval_inferred":False,
        "existing_approved_roofing_page_is_intentionally_noindex":True,
        "leadsmart_guides_are_not_authorized_content":True,
        "google_indexation_verified":False,
        "search_console_impressions_assessed_here":False,
        "revenue_verified":False,
        "remove_buyer_noindex_allowed":False,
        "publication_authorized":False,
        "outbound_authorized":False,
        "production_write":False,
    }
