"""GET-only existing Website & Growth audit: sitemap -> actual page -> buyer form.

No crawler service, scheduler, contact details, outbound, DB credentials or mutations.
Never confuse indexability/discovery with verified Google indexing or paid conversions.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

BASE = "https://empire-ai.co.uk"
LOCAL = "http://127.0.0.1"
HOST = "empire-ai.co.uk"
GTM = Path("/srv/empire_os/runtime/gtm_pipeline/integration_observer_latest.json")
MAX_ROUTES = 40
ROUTES_TO_FORMS = {"/commercial", "/predictive-revenue"}
PRIORITY = {
    "/commercial", "/predictive-revenue", "/industries/roofing",
    "/industries/solar", "/industries/hvac", "/industries/property",
    "/industries/legal-mass-tort", "/industries/private-equity",
}


class AuditHeld(ValueError):
    pass


class Markup(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.canonicals: list[str] = []
        self.robots: list[str] = []
        self.links: list[str] = []
        self.form_count = 0
        self.consent = 0
        self.email = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "link" and a.get("rel") == "canonical":
            self.canonicals.append(a.get("href") or "")
        if tag == "meta" and a.get("name", "").lower() == "robots":
            self.robots.append(a.get("content") or "")
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "form":
            self.form_count += 1
        if tag == "input" and a.get("type") == "checkbox" and "required" in a:
            self.consent += 1
        if tag == "input" and a.get("type") == "email" and "required" in a:
            self.email += 1


def local_get(path: str) -> tuple[int, dict[str, str], bytes]:
    if not path.startswith("/") or path.startswith("//") or any(
        ch in path for ch in ("?", "#", "\r", "\n", "\\")
    ):
        raise AuditHeld("UNSAFE_GET_PATH")
    req = Request(
        LOCAL + path, method="GET",
        headers={"Host": HOST, "User-Agent": "EmpireOS-SEO-Commercial-GET-Only/1"},
    )
    with urlopen(req, timeout=8) as response:
        body = response.read(750_001)
        if len(body) > 750_000:
            raise AuditHeld("UNBOUNDED_RESPONSE")
        return response.status, dict(response.headers.items()), body


def _links_to_buyers(links: list[str]) -> set[str]:
    out = set()
    for link in links:
        parsed = urlsplit(link)
        if parsed.scheme or parsed.netloc:
            if parsed.scheme != "https" or parsed.netloc != HOST:
                continue
        if parsed.path in ROUTES_TO_FORMS:
            out.add(parsed.path)
    return out


def _gtm_summary(snapshot: dict) -> dict:
    source = snapshot.get("canonical_sales_source_ops") or {}
    status = source.get("status", "SOURCE_UNAVAILABLE")
    known_zero = (
        status == "CANONICAL_COMMERCIAL_SALES_INTAKE_ZERO_OBSERVED"
        and source.get("source_count_verified") is True
        and source.get("canonical_sales_acquisitions") == 0
        and source.get("canonical_predictive_revenue_enquiries") == 0
        and source.get("canonical_commercial_enquiries") == 0
    )
    return {
        "source_status": status,
        "observed_utc": snapshot.get("generated_at"),
        "canonical_zero_verified_in_snapshot": known_zero,
        "canonical_enquiries": 0 if known_zero else None,
        "qualified_buyer_verified": False,
        "money_received_verified": False,
    }


def review(
    get: Callable[[str], tuple[int, dict[str, str], bytes]] = local_get,
    gtm: dict | None = None,
) -> dict:
    rc, _, robots = get("/robots.txt")
    sc, _, sitemap = get("/sitemap.xml")
    if rc != 200 or sc != 200:
        raise AuditHeld("ROBOTS_OR_SITEMAP_GET_FAILED")
    robot_text = robots.decode("utf8", "strict")
    if ("Sitemap: " + BASE + "/sitemap.xml" not in robot_text
        or "User-agent: *" not in robot_text
        or "Disallow: /" in robot_text):
        raise AuditHeld("UNTRUSTED_CRAWL_INSTRUCTIONS")
    tree = ElementTree.fromstring(sitemap)
    locations = [node.text for node in tree.iter() if node.tag.endswith("}loc") or node.tag == "loc"]
    if not 1 <= len(locations) <= MAX_ROUTES or len(set(locations)) != len(locations):
        raise AuditHeld("SITEMAP_EMPTY_UNBOUNDED_OR_DUPLICATE")
    expected = {}
    for url in locations:
        parts = urlsplit(url or "")
        if (parts.scheme != "https" or parts.netloc != HOST
            or not parts.path.startswith("/") or parts.query or parts.fragment):
            raise AuditHeld("SITEMAP_OFF_HOST_OR_UNSAFE_URL")
        expected[parts.path] = url
    if not PRIORITY.issubset(expected):
        raise AuditHeld("MISSING_PRIORITY_BUYER_ROUTES_FROM_SITEMAP")
    rows = []
    for route, original in expected.items():
        status, headers, html = get(route)
        tags = Markup()
        tags.feed(html.decode("utf8", "replace"))
        expected_canonical = original.rstrip("/")
        got = [canon.rstrip("/") for canon in tags.canonicals]
        issues = []
        if status != 200:
            issues.append("NON_200")
        if "html" not in headers.get("Content-Type", headers.get("content-type", "")).lower():
            issues.append("NON_HTML_RESPONSE")
        if got != [expected_canonical]:
            issues.append("CANONICAL_MISSING_OR_NOT_SELF")
        if any("noindex" in directive.lower() for directive in tags.robots):
            issues.append("META_NOINDEX")
        if "noindex" in headers.get("X-Robots-Tag", headers.get("x-robots-tag", "")).lower():
            issues.append("HEADER_NOINDEX")
        direct = _links_to_buyers(tags.links)
        rows.append({
            "route": route, "http_status": status, "canonical_self": got == [expected_canonical],
            "direct_buyer_destinations": sorted(direct),
            "priority_commercial_route": route in PRIORITY,
            "issues": issues,
        })
    catalogues = {}
    for route, field in (
        ("/v1/checkout/commercial/offers", "offers"),
        ("/v1/checkout/predictive-revenue/products", "products"),
    ):
        status, _, payload = get(route)
        obj = json.loads(payload)
        catalogues[route] = {
            "healthy": status == 200 and isinstance(obj, dict)
                and isinstance(obj.get(field), list) and len(obj[field]) > 0,
            "count": len(obj.get(field, [])),
        }
    gtm_snapshot = gtm if gtm is not None else json.loads(GTM.read_text())
    blocking = [x["route"] for x in rows if x["issues"]]
    if not all(v["healthy"] for v in catalogues.values()):
        blocking.append("EXISTING_READONLY_CATALOGUE_API")
    gaps = [x["route"] for x in rows if not x["direct_buyer_destinations"]
            and x["route"] not in ROUTES_TO_FORMS]
    return {
        "schema_version": "empire.search.live_organic_to_buyer_observer.v1",
        "status": "GET_ONLY_PUBLIC_DISCOVERY_AUDIT",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "sitemap_routes_checked": len(rows),
        "routes_with_http_canonical_indexability_issues": blocking,
        "priority_buyer_routes_checked": len(PRIORITY),
        "direct_buyer_link_review_candidates": gaps,
        "direct_buyer_link_review_count": len(gaps),
        "catalogues": catalogues,
        "gtm_snapshot": _gtm_summary(gtm_snapshot),
        "routes": rows,
        "google_indexing_verified": False,
        "organic_attribution_verified": False,
        "traffic_growth_verified": False,
        "publication_authorized": False,
        "site_mutations": False, "database_writes": False,
        "customer_submissions": 0, "outbound_sent": False, "payments_executed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        print(json.dumps(review(), sort_keys=True))
    except (OSError, ValueError, ElementTree.ParseError) as exc:
        print(json.dumps({
            "status": "LIVE_ORGANIC_BUYER_AUDIT_HELD",
            "reason": type(exc).__name__ if not isinstance(exc, AuditHeld) else str(exc),
            "website_mutations": False, "execution_authority": "NONE",
        }, sort_keys=True))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
