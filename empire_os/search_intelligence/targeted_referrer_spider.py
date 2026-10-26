"""Empire AI: bounded source-page discovery from historic Common Crawl domain leads.

Read-only one-shot: strictly selected source hosts; exact target hosts from reviewed
2026 graph receipt; pinned public HTTPS via existing EmpireOS fetch adapter.
No new DB or scheduler. Graph edges are NOT verified editorial backlinks.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable, Mapping
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET
import re

from .backlink_live_verifier import (
    Fetcher, VerificationHeld, safe_https_url, USER_AGENT,
    MIN_WAIT_SECONDS, MAX_PERMITTED_DELAY, ROBOTS_LIMIT, HTML_LIMIT,
)

MAX_HOSTS = 2
MAX_PAGES_PER_HOST = 5
MAX_HTTP_REQUESTS = MAX_HOSTS * (MAX_PAGES_PER_HOST + 2)
MAX_FRONTIER = 24
MAX_SITEMAP_PAGES = 24
MAX_EDGES = 40
MAX_DEPTH = 2
SITEMAP_LIMIT = 256 * 1024
NON_HTML = re.compile(r"\.(?:jpe?g|png|gif|webp|svg|woff2?|ttf|css|js|json|pdf|zip|gz|mp4|xml|webm)(?:$|/)", re.I)
DISALLOWED_PATHS = {"admin", "login", "signin", "checkout", "cart", "account", "api", "search"}

class SpiderHeld(VerificationHeld):
    pass


def canonical_host(host: object) -> str:
    if not isinstance(host, str):
        raise SpiderHeld("invalid_host_type")
    try:
        normalized = safe_https_url("https://" + host)
    except VerificationHeld as exc:
        raise SpiderHeld("unsafe_source_or_target_host") from exc
    if urlsplit(normalized).hostname != host or normalized != "https://" + host + "/":
        raise SpiderHeld("noncanonical_host")
    return host


def page_url(value: str, host: str) -> str | None:
    try:
        uri = safe_https_url(value)
    except VerificationHeld:
        return None
    p = urlsplit(uri)
    if (p.hostname != host or p.query or len(p.path) > 350
            or NON_HTML.search(p.path)
            or any(seg.lower() in DISALLOWED_PATHS for seg in p.path.split("/"))):
        return None
    return uri


def plan_from_review(review: Mapping[str, Any], selected: tuple[str, ...] = ()) -> dict[str, Any]:
    if (not isinstance(review, Mapping)
            or review.get("schema_version") != "empire.cc.graph.referrer_review_queue.v1"
            or review.get("source") != "commoncrawl_2026_domain_webgraph"
            or review.get("mode") != "OBSERVE"
            or review.get("empiredb_writes") is not False
            or review.get("verified_live_backlink_count") != 0):
        raise SpiderHeld("canonical_graph_review_required")
    rows = review.get("manual_review_queue")
    if (not isinstance(rows, list) or len(rows) > 5000
            or len(rows) != review.get("distinct_historical_source_domains")):
        raise SpiderHeld("consistent_review_queue_required")
    available = {}
    for item in rows:
        if not isinstance(item, Mapping):
            raise SpiderHeld("invalid_candidate")
        source = canonical_host(item.get("source_domain"))
        targets = item.get("observed_target_domains")
        if (source in available or not isinstance(targets, list)
                or not 1 <= len(targets) <= 4
                or item.get("editorial_link_verified") is not False
                or item.get("source_page_url_known") is not False
                or item.get("authority_score") is not None):
            raise SpiderHeld("unverified_graph_domain_candidate_required")
        available[source] = tuple(canonical_host(t) for t in targets)
    if not selected:
        suggestions = [item["source_domain"] for item in rows
                       if item.get("linked_target_count", 0) >= 2
                       and item.get("technical_name_hint") is False][:5]
        return {
            "schema_version": "empire.search.referrer_spider_plan.v1",
            "status": "REVIEW_ONLY_SELECT_SOURCES",
            "suggested_source_hosts": suggestions,
            "network_requests": 0,
            "empiredb_writes": False,
        }
    if (not 1 <= len(selected) <= MAX_HOSTS or len(set(selected)) != len(selected)
            or any(item not in available for item in selected)):
        raise SpiderHeld("selected_sources_not_approved")
    targets = sorted(set(t for host in selected for t in available[host]))
    return {
        "schema_version": "empire.search.referrer_spider_plan.v1",
        "status": "BOUNDED_ONE_SHOT_SCOPE_READY",
        "approved_source_hosts": list(selected),
        "approved_target_hosts": targets,
        "target_by_source": {host: list(available[host]) for host in selected},
        "max_pages_per_host": MAX_PAGES_PER_HOST,
        "max_http_requests": MAX_HTTP_REQUESTS,
        "network_requests": 0,
        "empiredb_writes": False,
        "scheduled_crawling": False,
    }



def _approved_target_host(actual: str | None, targets: frozenset[str]) -> str | None:
    """Match exact approved apex host or only its conventional www hostname."""
    if actual in targets:
        return actual
    if actual and actual.startswith("www.") and actual[4:] in targets:
        return actual[4:]
    return None


def _observed_outbound_url(base: str, href: str) -> str | None:
    """Normalise an HTML href for evidence only; this never causes a request.

    Strict fetch URLs remain HTTPS-only. An explicit HTTP link on a real HTTPS
    page is still an observed anchor. Validate its host via the existing HTTPS
    public-host policy before preserving the original HTTP scheme.
    """
    if not isinstance(href, str) or not 1 <= len(href) <= 2048:
        return None
    try:
        joined = urljoin(base, href)
    except ValueError:
        return None
    try:
        return safe_https_url(joined)
    except VerificationHeld:
        try:
            parts = urlsplit(joined)
            if parts.scheme.lower() != "http" or parts.username or parts.password:
                return None
        except ValueError:
            return None
        try:
            checked = safe_https_url("https://" + parts.netloc + (parts.path or "/")
                                     + ("?" + parts.query if parts.query else ""))
        except (VerificationHeld, ValueError):
            return None
        normalized = urlsplit(checked)
        return "http://" + normalized.netloc + normalized.path + (
            "?" + normalized.query if normalized.query else "")


def _known_fetch_hold_code(exc: VerificationHeld) -> str:
    """Opaque bounded reason labels, no leaked IPs, URLs or exception text."""
    known = {
        "dns_lookup_failed": "fetch_held_dns_failure",
        "nonpublic_dns_address_blocked": "fetch_held_private_dns_blocked",
        "response_exceeds_byte_budget": "fetch_held_byte_budget",
        "network_or_tls_error": "fetch_held_network_tls_failure",
        "encoded_body_not_supported": "fetch_held_encoded_body",
    }
    key = exc.args[0] if exc.args else None
    return known.get(key, "fetch_held")

class LinkParser(HTMLParser):
    def __init__(self, base: str, source_host: str, targets: frozenset[str]):
        super().__init__(convert_charrefs=True)
        self.base, self.source_host, self.targets = base, source_host, targets
        self.internal: list[str] = []
        self.outbound: dict[str, set[str]] = {}
        self.nofollow = False

    def handle_starttag(self, tag: str, attrs_list):
        attrs = dict(attrs_list)
        if tag == "meta" and (attrs.get("name") or "").lower() in ("robots", "googlebot"):
            if "nofollow" in (attrs.get("content") or "").lower().replace(",", " ").split():
                self.nofollow = True
        if tag not in ("a", "area"):
            return
        href = attrs.get("href")
        if not isinstance(href, str) or not 1 <= len(href) <= 2048:
            return
        dest = _observed_outbound_url(self.base, href)
        if dest is None:
            return
        hostname = urlsplit(dest).hostname
        if hostname == self.source_host:
            # Never add HTTP URLs to the live page frontier.
            if not dest.startswith("https://"):
                return
            uri = page_url(dest, self.source_host)
            if uri and uri not in self.internal and len(self.internal) < MAX_FRONTIER:
                self.internal.append(uri)
        elif _approved_target_host(hostname, self.targets) is not None:
            self.outbound.setdefault(dest, set()).update((attrs.get("rel") or "").lower().split())


def get_robots(host: str, fetch: Fetcher):
    robots_url = "https://" + host + "/robots.txt"
    try:
        response = fetch(robots_url, max_bytes=ROBOTS_LIMIT)
    except VerificationHeld:
        return None, 0, None, "robots_fetch_held"
    if len(response.body) > ROBOTS_LIMIT:
        return None, 0, None, "robots_size_exceeded"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    if response.status in (404, 410):
        parser.parse([])
        return parser, MIN_WAIT_SECONDS, None, None
    if response.status != 200 or "text/plain" not in response.content_type:
        return None, 0, None, "robots_unavailable"
    try:
        lines = response.body.decode("utf-8-sig").splitlines()
    except UnicodeError:
        return None, 0, None, "robots_encoding_invalid"
    if len(lines) > 5000:
        return None, 0, None, "robots_line_limit"
    parser.parse(lines)
    delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay("*") or 0
    if delay > MAX_PERMITTED_DELAY:
        return None, 0, None, "robots_delay_exceeds_budget"
    sitemap = None
    for line in lines:
        if line.lower().lstrip().startswith("sitemap:"):
            try:
                dest = safe_https_url(line.split(":", 1)[1].strip())
            except VerificationHeld:
                continue
            if urlsplit(dest).hostname == host:
                sitemap = dest
                break
    return parser, max(MIN_WAIT_SECONDS, float(delay)), sitemap, None


def parse_sitemap(raw: bytes, host: str) -> list[str]:
    if len(raw) > SITEMAP_LIMIT or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        return []
    try:
        doc = ET.fromstring(raw)
    except ET.ParseError:
        return []
    if not doc.tag.endswith("urlset"):
        return []
    result = []
    for node in doc:
        if not node.tag.endswith("url"):
            continue
        for child in node:
            if child.tag.endswith("loc") and child.text:
                url = page_url(child.text.strip(), host)
                if url and url not in result:
                    result.append(url)
                break
        if len(result) >= MAX_SITEMAP_PAGES:
            break
    return result


def safe_fetch(fetch: Fetcher, uri: str, size_limit: int):
    try:
        response = fetch(uri, max_bytes=size_limit)
    except VerificationHeld as exc:
        return None, _known_fetch_hold_code(exc)
    if len(response.body) > size_limit:
        return None, "response_size_exceeded"
    if response.status in (429, 503):
        return None, "backoff_host"
    if response.status != 200:
        return None, "non_200"
    return response, None



def _prioritize_discovery(urls: list[str], targets: list[str]) -> list[str]:
    """Prioritise likely commercial article paths, never claim ranking/SEO value."""
    keywords = {"solar", "roof", "roofing", "sunrun", "tecta", "nations",
                "freedom", "case-study", "project", "news", "article"}
    keywords.update(t.split(".")[0].replace("-", "") for t in targets)
    def score(url: str):
        path = urlsplit(url).path.lower()
        tokens = set(re.split(r"[^a-z0-9]+", path))
        hits = len(tokens & keywords)
        editorial = int(any(segment in tokens for segment in ("blog", "story", "stories", "news", "article")))
        return (-hits, -editorial, len(path), url)
    return sorted(urls, key=score)


def _diagnosed_fetch(fetch: Fetcher, uri: str, cap: int):
    """Keep bounded outcome codes even where a source returned no HTML."""
    try:
        response = fetch(uri, max_bytes=cap)
    except VerificationHeld:
        return None, "fetch_held"
    if len(response.body) > cap:
        return None, "response_size_exceeded"
    if response.status in (429, 503):
        return None, "host_backoff"
    if response.status in (301, 302, 303, 307, 308):
        return None, "redirect_not_followed"
    if response.status in (401, 403):
        return None, "access_denied"
    if response.status in (404, 410):
        return None, "not_found"
    if response.status >= 500:
        return None, "server_error"
    if response.status != 200:
        return None, "other_http_status"
    return response, None


def _sitemap_discovery(raw: bytes, host: str, targets: list[str]):
    """Safe bounded sitemap URL list or first approved nested sitemap URL."""
    if len(raw) > SITEMAP_LIMIT or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        return [], None, "sitemap_invalid_or_oversize"
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return [], None, "sitemap_invalid_xml"
    if root.tag.endswith("urlset"):
        urls = []
        for node in root:
            if not node.tag.endswith("url"):
                continue
            for child in node:
                if child.tag.endswith("loc") and child.text:
                    u = page_url(child.text.strip(), host)
                    if u and u not in urls:
                        urls.append(u)
                    break
            if len(urls) >= 256:
                break
        return _prioritize_discovery(urls, targets)[:MAX_SITEMAP_PAGES], None, (
            "sitemap_pages_selected" if urls else "sitemap_without_eligible_pages")
    if root.tag.endswith("sitemapindex"):
        children = []
        for node in root:
            if not node.tag.endswith("sitemap"):
                continue
            for child in node:
                if child.tag.endswith("loc") and child.text:
                    try:
                        url = safe_https_url(child.text.strip())
                    except VerificationHeld:
                        break
                    if (urlsplit(url).hostname == host and not urlsplit(url).query
                            and urlsplit(url).path.endswith(".xml")):
                        children.append(url)
                    break
            if len(children) >= 32:
                break
        if not children:
            return [], None, "sitemap_index_without_eligible_child"
        def rank(uri: str):
            low = urlsplit(uri).path.lower()
            return (-int(any(k in low for k in ("post", "blog", "news", "article", "solar", "roof"))),
                    int(any(k in low for k in ("image", "product", "tag"))), low)
        return [], sorted(set(children), key=rank)[0], "sitemap_index_child_selected"
    return [], None, "sitemap_unknown_xml_root"


def crawl_pilot(plan: Mapping[str, Any], *, fetch: Fetcher,
                wait: Callable[[float], Any]) -> dict[str, Any]:
    """One-shot source-crawl with precise bounded, non-sensitive diagnostics."""
    if (plan.get("schema_version") != "empire.search.referrer_spider_plan.v1"
            or plan.get("status") != "BOUNDED_ONE_SHOT_SCOPE_READY"
            or plan.get("max_http_requests") != MAX_HTTP_REQUESTS
            or plan.get("max_pages_per_host") != MAX_PAGES_PER_HOST
            or plan.get("network_requests") != 0
            or plan.get("empiredb_writes") is not False
            or plan.get("scheduled_crawling") is not False):
        raise SpiderHeld("reviewed_plan_contract_required")
    sources, targets, mapping = (
        plan.get("approved_source_hosts"), plan.get("approved_target_hosts"),
        plan.get("target_by_source"))
    if (not isinstance(sources, list) or not 1 <= len(sources) <= MAX_HOSTS
            or len(set(sources)) != len(sources) or not isinstance(targets, list)
            or not 1 <= len(targets) <= 4 or len(set(targets)) != len(targets)
            or not isinstance(mapping, dict) or set(mapping) != set(sources)):
        raise SpiderHeld("invalid_source_target_scope")
    for host in sources + targets:
        canonical_host(host)
    for host in sources:
        if (not isinstance(mapping[host], list) or not mapping[host]
                or len(mapping[host]) != len(set(mapping[host]))
                or not set(mapping[host]) <= set(targets)):
            raise SpiderHeld("invalid_target_mapping")

    seeded = plan.get("historical_page_seeds")
    if seeded is not None:
        if (plan.get("historical_seed_provenance") !=
                "commoncrawl_wat_archived_html_anchor_unverified"
                or not isinstance(seeded, dict) or set(seeded) != set(sources)
                or type(plan.get("historical_page_seed_count")) is not int):
            raise SpiderHeld("historical_seed_scope_or_provenance_invalid")
        actual_count = 0
        for host in sources:
            urls = seeded[host]
            if (not isinstance(urls, list) or len(urls) > MAX_PAGES_PER_HOST
                    or urls != sorted(set(urls))
                    or any(not isinstance(url, str) or page_url(url, host) != url
                           for url in urls)):
                raise SpiderHeld("historical_seed_url_scope_invalid")
            actual_count += len(urls)
        if actual_count != plan["historical_page_seed_count"]:
            raise SpiderHeld("historical_seed_count_invalid")
    else:
        seeded = {host: [] for host in sources}

    count, html_count = 0, 0
    evidence: list[dict[str, Any]] = []
    outcomes = []
    for host in sources:
        reasons: dict[str, int] = {}
        def mark(key):
            reasons[key] = reasons.get(key, 0) + 1
        host_requests = 0
        attempted = 0
        inspected = 0
        sitemap_seen = 0
        frontier_added = 0
        paused = False
        def allocate_request():
            nonlocal count, host_requests
            if count >= MAX_HTTP_REQUESTS:
                return False
            count += 1
            host_requests += 1
            return True

        if not allocate_request():
            outcomes.append({"source_host": host, "status": "global_request_budget_exhausted",
                             "pages": 0, "reason_counts": {"request_budget_exhausted": 1}})
            continue
        robots, delay, sitemap, held = get_robots(host, fetch)
        if held:
            mark(held)
            outcomes.append({"source_host": host, "status": held, "pages": 0,
                             "http_requests": host_requests, "attempted_pages": 0,
                             "sitemap_outcome": "not_requested_robots_held",
                             "reason_counts": reasons, "no_pages_reason": held})
            continue

        # WAT page-level anchors are useful *candidate starting points* only.
        # Robots and all standard network limits still apply to each page.
        host_seeds = seeded[host]
        frontier = deque([(url, 0) for url in host_seeds] +
                         [("https://" + host + "/", 0)])
        seeded_attempted = 0
        seeded_html_checked = 0
        seen = set()
        sitemap_outcome = "not_requested"
        sitemap_uri = sitemap or "https://" + host + "/sitemap.xml"
        if not robots.can_fetch(USER_AGENT, sitemap_uri):
            sitemap_outcome = "robots_denied_sitemap"
            mark(sitemap_outcome)
        elif allocate_request():
            wait(delay)
            result, problem = _diagnosed_fetch(fetch, sitemap_uri, SITEMAP_LIMIT)
            if problem:
                sitemap_outcome = "sitemap_" + problem
                mark(sitemap_outcome)
                if problem == "host_backoff":
                    paused = True
            elif "xml" not in result.content_type and "text/plain" not in result.content_type:
                sitemap_outcome = "sitemap_non_xml_content"
                mark(sitemap_outcome)
            else:
                urls, nested, reason = _sitemap_discovery(result.body, host, mapping[host])
                sitemap_outcome = reason
                sitemap_seen += len(urls)
                if nested and robots.can_fetch(USER_AGENT, nested) and allocate_request():
                    wait(delay)
                    inner, problem = _diagnosed_fetch(fetch, nested, SITEMAP_LIMIT)
                    if problem:
                        sitemap_outcome = "nested_sitemap_" + problem
                        mark(sitemap_outcome)
                        if problem == "host_backoff":
                            paused = True
                    elif "xml" not in inner.content_type and "text/plain" not in inner.content_type:
                        sitemap_outcome = "nested_sitemap_non_xml_content"
                        mark(sitemap_outcome)
                    else:
                        urls, _, reason = _sitemap_discovery(inner.body, host, mapping[host])
                        sitemap_outcome = "nested_" + reason
                        sitemap_seen += len(urls)
                elif nested:
                    sitemap_outcome = "nested_sitemap_denied_or_request_budget"
                    mark(sitemap_outcome)
                for u in urls:
                    if len(frontier) >= MAX_FRONTIER:
                        break
                    frontier.append((u, 1))
                    frontier_added += 1
        else:
            sitemap_outcome = "sitemap_request_budget_exhausted"
            mark(sitemap_outcome)

        while frontier and not paused and attempted < MAX_PAGES_PER_HOST:
            uri, depth = frontier.popleft()
            if uri in seen:
                continue
            seen.add(uri)
            if page_url(uri, host) != uri:
                mark("ineligible_internal_url")
                continue
            if not robots.can_fetch(USER_AGENT, uri):
                mark("robots_denied_page")
                continue
            if not allocate_request():
                mark("global_request_budget_exhausted")
                break
            attempted += 1
            if uri in host_seeds:
                seeded_attempted += 1
            wait(delay)
            response, problem = _diagnosed_fetch(fetch, uri, HTML_LIMIT)
            if problem:
                mark(problem)
                if problem == "host_backoff":
                    paused = True
                continue
            if "text/html" not in response.content_type:
                mark("non_html_content")
                continue
            inspected += 1
            html_count += 1
            if uri in host_seeds:
                seeded_html_checked += 1
            parsed = LinkParser(uri, host, frozenset(mapping[host]))
            parsed.feed(response.body.decode("utf-8", errors="replace"))
            if parsed.nofollow:
                mark("page_meta_nofollow")
            for target, rel in parsed.outbound.items():
                if len(evidence) >= MAX_EDGES:
                    raise SpiderHeld("html_anchor_edge_budget_exceeded")
                evidence.append({
                    "source_url": uri,
                    "target_url": target,
                    "source_host": host,
                    "target_host": urlsplit(target).hostname,
                    "approved_target_host": _approved_target_host(
                        urlsplit(target).hostname, frozenset(mapping[host])),
                    "outbound_href_scheme": urlsplit(target).scheme,
                    "target_url_not_fetched": True,
                    "observed_rel": sorted(rel),
                    "page_robots_meta_nofollow": parsed.nofollow,
                    "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                    "evidence_type": "spider_observed_html_anchor",
                    "live_html_anchor_observed": True,
                    "search_engine_counts_link": None,
                    "editorial_link_value_verified": False,
                })
            if depth < MAX_DEPTH and not parsed.nofollow:
                for u in _prioritize_discovery(parsed.internal, mapping[host]):
                    if u not in seen and len(frontier) < MAX_FRONTIER:
                        frontier.append((u, depth + 1))
                        frontier_added += 1

        if inspected:
            no_pages_reason = None
        elif paused:
            no_pages_reason = "host_backoff"
        elif attempted == 0 and reasons.get("robots_denied_page"):
            no_pages_reason = "robots_denied_page"
        elif reasons:
            no_pages_reason = sorted(reasons.items(), key=lambda x: (-x[1], x[0]))[0][0]
        else:
            no_pages_reason = "no_inspectable_html"
        status = "host_retry_later" if paused else (
            "global_request_budget_exhausted" if reasons.get("global_request_budget_exhausted")
            else "bounded_scan_complete")
        outcomes.append({
            "source_host": host,
            "status": status,
            "historical_seed_candidates": len(host_seeds),
            "historical_seed_pages_attempted": seeded_attempted,
            "historical_seed_pages_html_checked": seeded_html_checked,
            "pages": inspected,
            "attempted_pages": attempted,
            "http_requests": host_requests,
            "sitemap_outcome": sitemap_outcome,
            "sitemap_candidates_found": sitemap_seen,
            "frontier_entries_added": frontier_added,
            "skipped_or_denied": sum(v for k, v in reasons.items()
                                     if k not in ("page_meta_nofollow",)),
            "reason_counts": dict(sorted(reasons.items())),
            "no_pages_reason": no_pages_reason,
        })
    return {
        "schema_version": "empire.search.targeted_referrer_spider.review.v1",
        "diagnostic_version": 2,
        "mode": "OBSERVE",
        "source_hosts": sources,
        "target_hosts": targets,
        "http_requests": count,
        "html_pages_checked": html_count,
        "html_anchor_edges_observed": len(evidence),
        "historical_page_seed_count": sum(len(v) for v in seeded.values()),
        "historical_seeds_do_not_prove_live_links": True,
        "evidence": evidence,
        "host_outcomes": outcomes,
        "graph_domain_edges_do_not_prove_html_backlinks": True,
        "google_counted_backlinks": None,
        "empiredb_writes": False,
        "outbound_sent": False,
        "paid_api_calls": 0,
        "production_changed": False,
        "scheduled_crawling": False,
    }
