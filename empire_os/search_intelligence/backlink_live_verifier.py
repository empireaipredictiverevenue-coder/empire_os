"""Bounded backlink recheck of historical WAT candidates, no DB writes.

Network backend pins publicly routable DNS addresses and TLS hostname verification.
No redirects, cookies, proxies, JS rendering, authentication or unbounded crawling.
No active network requests unless explicitly invoked with a transport.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
import http.client
import ipaddress
import re
import socket
import ssl
import time
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

USER_AGENT = "EmpireAI-SEO-Research/1.0 (+https://empire-ai.co.uk/)"
MAX_CANDIDATES = 25
MAX_HOSTS = 8
MAX_PAGES_PER_HOST = 4
HTML_LIMIT = 512 * 1024
ROBOTS_LIMIT = 128 * 1024
MIN_WAIT_SECONDS = 2.0
MAX_PERMITTED_DELAY = 30.0
PUBLIC_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")


class VerificationHeld(ValueError):
    pass


@dataclass(frozen=True)
class FetchResult:
    status: int
    content_type: str
    body: bytes


class Fetcher(Protocol):
    def __call__(self, url: str, *, max_bytes: int) -> FetchResult: ...


def safe_https_url(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        raise VerificationHeld("invalid_url")
    try:
        url = urlsplit(value)
        hostname = (url.hostname or "").lower().rstrip(".")
        if (url.scheme != "https" or not hostname or not PUBLIC_HOST.fullmatch(hostname)
                or hostname.startswith("www.localhost") or hostname.endswith(
                    (".localhost", ".local", ".internal", ".test", ".invalid", ".example")
                )
                or url.username or url.password or url.port is not None
                or hostname.startswith(("-", ".")) or ".." in hostname
                or "." not in hostname or any(ord(c) < 33 for c in value)
                or "\\" in value):
            raise VerificationHeld("unsafe_url")
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            raise VerificationHeld("ip_literal_not_allowed")
        if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
               for label in hostname.split(".")):
            raise VerificationHeld("invalid_hostname")
        return urlunsplit(("https", hostname, url.path or "/", url.query, ""))
    except ValueError as exc:
        if isinstance(exc, VerificationHeld):
            raise
        raise VerificationHeld("invalid_url") from exc


class _PinnedConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str, timeout: float):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.pinned_ip = address

    def connect(self):
        self.sock = socket.create_connection((self.pinned_ip, 443), self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


class PublicHttpsFetcher:
    """SSRF-resistant GET: no redirects, public IP pin, host TLS verification."""

    def __init__(self, *, timeout: float = 5.0):
        self.timeout = timeout

    def __call__(self, url: str, *, max_bytes: int) -> FetchResult:
        normalized = safe_https_url(url)
        parsed = urlsplit(normalized)
        try:
            addresses = {
                result[4][0]
                for result in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
            }
        except OSError as exc:
            raise VerificationHeld("dns_lookup_failed") from exc
        if (not addresses or
                any(not ipaddress.ip_address(addr).is_global for addr in addresses)):
            raise VerificationHeld("nonpublic_dns_address_blocked")
        # DNS is pinned to the resolved IP at TCP connection time, preventing rebinding.
        conn = _PinnedConnection(parsed.hostname, sorted(addresses)[0], self.timeout)
        try:
            path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
            conn.request("GET", path, headers={
                "Host": parsed.hostname,
                "User-Agent": USER_AGENT,
                "Accept": "text/html,text/plain;q=0.8",
                "Accept-Encoding": "identity",
                "Connection": "close",
            })
            resp = conn.getresponse()
            if resp.getheader("Content-Encoding", "identity").lower() not in ("", "identity"):
                raise VerificationHeld("encoded_body_not_supported")
            size_hint = resp.getheader("Content-Length")
            if size_hint and int(size_hint) > max_bytes:
                raise VerificationHeld("response_exceeds_byte_budget")
            body = resp.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise VerificationHeld("response_exceeds_byte_budget")
            return FetchResult(
                status=resp.status,
                content_type=resp.getheader("Content-Type", "").lower(),
                body=body,
            )
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise VerificationHeld("network_or_tls_error") from exc
        finally:
            conn.close()


class AnchorParser(HTMLParser):
    def __init__(self, source: str):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.matches: dict[str, set[str]] = {}

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() not in ("a", "area"):
            return
        a = dict(attrs)
        href = a.get("href")
        if not href or len(href) > 2048:
            return
        try:
            target = safe_https_url(urljoin(self.source, href))
        except VerificationHeld:
            return
        rel = str(a.get("rel") or "").strip().lower()
        self.matches.setdefault(target, set()).update(rel.split())


def _robots_review(source: str, fetch: Fetcher) -> tuple[RobotFileParser, float] | None:
    url = urlsplit(source)
    robots_url = f"https://{url.hostname}/robots.txt"
    try:
        r = fetch(robots_url, max_bytes=ROBOTS_LIMIT)
    except VerificationHeld:
        return None
    parser = RobotFileParser()
    parser.set_url(robots_url)
    if r.status in (404, 410):
        parser.parse([])
        return parser, MIN_WAIT_SECONDS
    if r.status != 200:
        return None
    if not ("text/plain" in r.content_type or "text/" in r.content_type):
        return None
    try:
        raw = r.body.decode("utf-8-sig")
    except UnicodeError:
        return None
    parser.parse(raw.splitlines())
    delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay("*") or 0
    if delay > MAX_PERMITTED_DELAY:
        return None
    return parser, max(float(delay), MIN_WAIT_SECONDS)


def preflight_historical_backlinks(
    observations: list[Mapping[str, Any]], *,
    approved_source_hosts: tuple[str, ...],
    approved_target_hosts: tuple[str, ...],
) -> dict[str, Any]:
    """Validate *entire* proposed batch before making any public request."""
    if not isinstance(observations, list) or len(observations) > MAX_CANDIDATES:
        raise VerificationHeld("candidate_budget_exceeded")
    if (not approved_source_hosts or len(approved_source_hosts) > MAX_HOSTS
            or not approved_target_hosts or len(approved_target_hosts) > 12):
        raise VerificationHeld("host_budget_exceeded")
    sources = {urlsplit(safe_https_url("https://" + x)).hostname for x in approved_source_hosts}
    targets = {urlsplit(safe_https_url("https://" + x)).hostname for x in approved_target_hosts}
    if len(sources) != len(approved_source_hosts) or len(targets) != len(approved_target_hosts):
        raise VerificationHeld("host_scope_invalid")
    pages = set()
    for obj in observations:
        if not isinstance(obj, Mapping):
            raise VerificationHeld("candidate_not_mapping")
        if obj.get("source") != "commoncrawl_wat_archived_link":
            raise VerificationHeld("unverified_candidate_source")
        prov = obj.get("provenance")
        if (not isinstance(prov, (list, tuple)) or
                "status:historical_unverified" not in prov or "type:html_anchor" not in prov):
            raise VerificationHeld("historical_link_provenance_required")
        source = safe_https_url(obj.get("source_url"))
        target = safe_https_url(obj.get("target_url"))
        if urlsplit(source).hostname not in sources or urlsplit(target).hostname not in targets:
            raise VerificationHeld("link_domain_not_approved")
        if urlsplit(source).hostname == urlsplit(target).hostname:
            raise VerificationHeld("self_link_not_a_backlink")
        pages.add(source)
    return {
        "status": "LIVE_LINK_REVIEW_PREFLIGHT_READY",
        "candidate_count": len(observations),
        "unique_source_pages": len(pages),
        "approved_source_hosts": sorted(sources),
        "approved_target_hosts": sorted(targets),
        "network_requests": 0,
        "empiredb_writes": False,
        "execution_authority": "none",
    }


def verify_historical_backlinks(
    observations: list[Mapping[str, Any]], *,
    approved_source_hosts: tuple[str, ...],
    approved_target_hosts: tuple[str, ...],
    fetch: Fetcher,
    wait: Callable[[float], Any] = time.sleep,
) -> dict[str, Any]:
    """Sequential fetches only; source host must be explicitly approved."""
    preflight_historical_backlinks(
        observations,
        approved_source_hosts=approved_source_hosts,
        approved_target_hosts=approved_target_hosts,
    )
    if not isinstance(observations, list) or len(observations) > MAX_CANDIDATES:
        raise VerificationHeld("candidate_budget_exceeded")
    if (not approved_source_hosts or len(approved_source_hosts) > MAX_HOSTS
            or not approved_target_hosts or len(approved_target_hosts) > 12):
        raise VerificationHeld("host_budget_exceeded")
    sources = {urlsplit(safe_https_url("https://" + x)).hostname for x in approved_source_hosts}
    targets = {urlsplit(safe_https_url("https://" + x)).hostname for x in approved_target_hosts}
    if len(sources) != len(approved_source_hosts) or len(targets) != len(approved_target_hosts):
        raise VerificationHeld("host_scope_invalid")
    robots_cache: dict[str, tuple[RobotFileParser, float] | None] = {}
    page_cache: dict[str, tuple[str, AnchorParser | None]] = {}
    per_host: dict[str, int] = {}
    blocked_hosts: set[str] = set()
    output = []
    for obj in observations:
        if not isinstance(obj, Mapping):
            raise VerificationHeld("candidate_not_mapping")
        if obj.get("source") != "commoncrawl_wat_archived_link":
            raise VerificationHeld("unverified_candidate_source")
        prov = obj.get("provenance")
        if (not isinstance(prov, (list, tuple)) or
                "status:historical_unverified" not in prov or "type:html_anchor" not in prov):
            raise VerificationHeld("historical_link_provenance_required")
        source = safe_https_url(obj.get("source_url"))
        target = safe_https_url(obj.get("target_url"))
        shost = urlsplit(source).hostname
        thost = urlsplit(target).hostname
        if shost not in sources or thost not in targets:
            raise VerificationHeld("link_domain_not_approved")
        if shost == thost:
            raise VerificationHeld("self_link_not_a_backlink")
        if shost not in robots_cache:
            robots_cache[shost] = _robots_review(source, fetch)
        robots = robots_cache[shost]
        status = "unavailable"
        rel: list[str] = []
        if shost in blocked_hosts:
            status = "host_retry_later"
        elif robots is None:
            status = "robots_unavailable_or_delay_exceeded"
        elif not robots[0].can_fetch(USER_AGENT, source):
            status = "robots_denied"
        else:
            if source not in page_cache:
                per_host[shost] = per_host.get(shost, 0) + 1
                if per_host[shost] > MAX_PAGES_PER_HOST:
                    page_cache[source] = ("host_page_budget_exceeded", None)
                else:
                    wait(robots[1])  # also wait between robots GET and the first page
                    try:
                        page = fetch(source, max_bytes=HTML_LIMIT)
                        if page.status in (429, 503):
                            blocked_hosts.add(shost)
                            page_cache[source] = ("host_retry_later", None)
                        elif page.status != 200:
                            page_cache[source] = ("page_unavailable", None)
                        elif "text/html" not in page.content_type:
                            page_cache[source] = ("non_html_page", None)
                        else:
                            parsed = AnchorParser(source)
                            parsed.feed(page.body.decode("utf-8", errors="replace"))
                            page_cache[source] = ("parsed_html", parsed)
                    except VerificationHeld:
                        page_cache[source] = ("page_fetch_held", None)
            page_status, links = page_cache[source]
            if links is not None:
                status = "verified_present" if target in links.matches else "not_observed_in_html"
                rel = sorted(links.matches.get(target, set()))
            else:
                status = page_status
        output.append({
            "source_url": source,
            "target_url": target,
            "historical_observed_at": obj.get("observed_at"),
            "status": status,
            "live_verified": status == "verified_present",
            "observed_rel": rel if status == "verified_present" else None,
            "verified_at": datetime.now(timezone.utc).isoformat() if status == "verified_present" else None,
            "current_link_absence_proven": False,
            "outbound_or_write_authority": False,
        })
    return {
        "schema_version": "empire.search.backlink_live_verification.v1",
        "mode": "OBSERVE",
        "source": "approved_commoncrawl_wat_candidates",
        "candidate_count": len(output),
        "live_verified_count": sum(x["live_verified"] for x in output),
        "results": output,
        "max_candidates": MAX_CANDIDATES,
        "max_source_hosts": MAX_HOSTS,
        "max_pages_per_host": MAX_PAGES_PER_HOST,
        "auto_crawling_enabled": False,
        "empiredb_writes": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
