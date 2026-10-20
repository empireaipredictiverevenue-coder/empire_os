"""Bounded, explicitly approved read-only company website evidence collection.

The Search Fabric provider returned no fresh domains. This does NOT attempt
search-engine circumvention. Only founder-approved, fixed first-party HTTPS
websites are queried with robots-policy checks and strict response limits.
No contacts, post text, phone numbers, sales or buyer claims are extracted.

Not an OpenManus executor. Owner review required before CRM use/contact.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from ipaddress import ip_address
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import re
import socket

SCHEMA = "empire.a2a.first_party_site_evidence_recovery.v1"
CONFIG_SCHEMA = "empire.a2a.approved_first_party_business_sites.v1"
ALLOWED_MARKETS = {
    ("tampa, fl", "roofing"),
    ("little rock, ar", "hvac"),
    ("nyc", "general_contractor"),
}
SCOPE = {
    "tampa, fl": ("tampa", "tampa bay", "hillsborough", "florida"),
    "little rock, ar": ("little rock", "central arkansas", "arkansas"),
    "nyc": ("new york city", "nyc", "manhattan", "brooklyn", "new york"),
}
TRADE = {
    "roofing": ("roofing", "roofer", "roof repair", "roof replacement"),
    "hvac": ("hvac", "air conditioning", "heating and cooling", "heat and air"),
    "general_contractor": ("general contracting", "general contractor", "construction management", "commercial construction"),
}
USER_AGENT = "EmpireAI-Public-Business-Research/0.1 (+https://empireai.uk; bounded read-only business website review)"
_LIMIT = 9
_MAX_HTML = 400_000
_MAX_ROBOTS = 100_000
_TIMEOUT = (3, 8)
_HOST = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")


class _Plain(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and len(self.text) < 5000:
            self.text.append(data)


def _parse_site(url: Any) -> tuple[str, str]:
    if not isinstance(url, str) or len(url) > 180:
        raise ValueError("UNSAFE_SITE_URL")
    parts = urlparse(url)
    try:
        hostname = parts.hostname
        port = parts.port
    except ValueError:
        raise ValueError("UNSAFE_SITE_URL") from None
    if (parts.scheme != "https" or not hostname or not _HOST.fullmatch(hostname)
            or port is not None or parts.username or parts.password
            or parts.query or parts.fragment or parts.path not in ("", "/")):
        raise ValueError("UNSAFE_SITE_URL")
    return hostname, "https://" + hostname + "/"


def _public_dns_only(host: str, resolve: Callable[[str, int], list] = socket.getaddrinfo) -> None:
    # A DNS preflight, not a replacement for firewall-enforced egress policy;
    # the allowlist and no redirect remain the core destination boundaries.
    answers = resolve(host, 443)
    if not answers:
        raise ValueError("NO_DNS_RESULT")
    for row in answers:
        addr = ip_address(row[4][0])
        if not addr.is_global:
            raise ValueError("NON_PUBLIC_SITE_ADDRESS_REJECTED")


def _get_capped(session: Any, url: str, cap: int, *, timeout: tuple[int,int]) -> tuple[str, bytes]:
    response = session.get(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain"},
        timeout=timeout, allow_redirects=False, stream=True,
    )
    try:
        status = response.status_code
        if status != 200:
            return f"HTTP_{status}", b""
        content_type = response.headers.get("Content-Type", "").lower()
        if not any(t in content_type for t in ("text/html", "text/plain")):
            return "UNSUPPORTED_MIME", b""
        size = response.headers.get("Content-Length")
        if size and size.isdigit() and int(size) > cap:
            return "CONTENT_TOO_LARGE", b""
        data = bytearray()
        for part in response.iter_content(chunk_size=16384):
            data.extend(part)
            if len(data) > cap:
                return "CONTENT_TOO_LARGE", b""
        return "HTTP_200", bytes(data)
    finally:
        response.close()


def _robots_permission(session: Any, origin: str) -> str:
    status, raw = _get_capped(session, urljoin(origin, "/robots.txt"), _MAX_ROBOTS, timeout=_TIMEOUT)
    if status == "HTTP_404" or status == "HTTP_410":
        return "ROBOTS_NOT_PRESENT_NO_RESTRICTION_FILE"
    if status != "HTTP_200":
        return "ROBOTS_UNAVAILABLE_HOLD"
    robot = RobotFileParser()
    robot.parse(raw.decode("utf-8", "replace").splitlines())
    return "ROBOTS_ALLOWED" if robot.can_fetch(USER_AGENT, origin) else "ROBOTS_DISALLOWED"


def collect_approved_first_party_sites(
    config: Mapping[str, Any],
    *,
    session: Any,
    dns_resolve: Callable = socket.getaddrinfo,
    now: datetime | None = None,
    max_sites: int = 9,
    offline_html_parser: Callable[..., dict[str, Any]] | None = None,
    offline_crawl4ai_parser: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    time = now or datetime.now(timezone.utc)
    if time.tzinfo is None:
        raise ValueError("AWARE_CLOCK_REQUIRED")
    if (not isinstance(config, Mapping)
            or config.get("schema_version") != CONFIG_SCHEMA
            or config.get("mode") != "OBSERVE"
            or config.get("activation") != "LIVE_READONLY_BY_EXPLICIT_OPERATOR_ACTION"
            or config.get("send_messages") is not False
            or config.get("no_private_contacts") is not True
            or config.get("assume_buyer_intent") is not False
            or config.get("budget_usd") != 0):
        raise ValueError("UNTRUSTED_FIRST_PARTY_SOURCE_MANIFEST")
    rows = config.get("sites")
    if (not isinstance(rows, list) or not 1 <= len(rows) <= _LIMIT
            or isinstance(max_sites, bool) or not isinstance(max_sites, int)
            or not 1 <= max_sites <= _LIMIT):
        raise ValueError("FIRST_PARTY_SITE_LIMIT")
    seen = set()
    records = []
    for site in rows[:max_sites]:
        if not isinstance(site, Mapping):
            raise ValueError("INVALID_FIRST_PARTY_SITE")
        host, origin = _parse_site(site.get("url"))
        niche, metro = site.get("niche"), site.get("market")
        if (metro, niche) not in ALLOWED_MARKETS or site.get("source_type") != "FIRST_PARTY_PUBLIC_SITE":
            raise ValueError("UNAPPROVED_INDUSTRY_OR_LOCATION")
        if host in seen:
            raise ValueError("DUPLICATE_SOURCE_DOMAIN")
        seen.add(host)
        entry = {
            "company_site": origin, "public_domain": host,
            "market_requested": metro, "sector_requested": niche,
            "source_role": "SELF_PUBLISHED_COMPANY_SITE",
            "source_observed_at": time.astimezone(timezone.utc).isoformat(),
            "site_fetch_status": "NOT_FETCHED",
            "robots_policy": "NOT_CHECKED",
            "source_body_sha256": None,
            "offline_structured_extraction": None,
            "offline_crawl4ai_extraction": None,
            "self_described_sector_matched": False,
            "self_described_city_or_region_matched": False,
            "independently_verified_company_identity": False,
            "independently_verified_service_territory": False,
            "actual_buyer_intent": False, "buyer_budget_verified": False,
            "contact_authorised": False,
            "person_contact_details_recorded": False,
        }
        try:
            _public_dns_only(host, dns_resolve)
            robots = _robots_permission(session, origin)
            entry["robots_policy"] = robots
            if robots not in ("ROBOTS_ALLOWED", "ROBOTS_NOT_PRESENT_NO_RESTRICTION_FILE"):
                entry["site_fetch_status"] = "ROBOTS_POLICY_HOLD"
            else:
                status, body = _get_capped(session, origin, _MAX_HTML, timeout=_TIMEOUT)
                entry["site_fetch_status"] = status
                if status == "HTTP_200":
                    parser = _Plain()
                    parser.feed(body.decode("utf-8", "replace"))
                    content = " ".join(parser.text).casefold()
                    entry["source_body_sha256"] = sha256(body).hexdigest()
                    if offline_html_parser is not None:
                        try:
                            parsed = offline_html_parser(body, source_url=origin)
                            if (not isinstance(parsed, dict)
                                    or parsed.get("schema_version") !=
                                    "empire.a2a.scrapling_approved_homepage_extraction.v1"
                                    or parsed.get("network_access_performed_by_parser") is not False
                                    or parsed.get("records_promoted_to_crm") != 0):
                                raise ValueError("UNSAFE_OFFLINE_PARSE_RECEIPT")
                            if (parsed.get("status") == "SCRAPLING_STRUCTURED_PAGE_PARSED"
                                    and parsed.get("document_sha256") != entry["source_body_sha256"]):
                                raise ValueError("UNBOUND_OFFLINE_PARSE_RECEIPT")
                            entry["offline_structured_extraction"] = parsed
                        except Exception:
                            entry["offline_structured_extraction"] = {
                                "schema_version": "empire.a2a.scrapling_approved_homepage_extraction.v1",
                                "status": "OFFLINE_PARSER_UNTRUSTED_HOLD",
                                "network_access_performed_by_parser": False,
                                "records_promoted_to_crm": 0,
                            }
                    if offline_crawl4ai_parser is not None:
                        try:
                            result = offline_crawl4ai_parser(body, source_url=origin)
                            if (not isinstance(result,dict) or result.get("schema_version") !=
                                    "empire.a2a.crawl4ai_offline_markdown.v1"
                                    or result.get("raw_markdown_or_pii_exported") is not False
                                    or result.get("records_promoted_to_crm") != 0
                                    or result.get("source_url_fetched_by_this_module") is not False):
                                raise ValueError("INVALID_CRAWL4AI_EXTRACTION_RESULT")
                            if (result.get("status") == "CRAWL4AI_MARKDOWN_EXTRACTED"
                                    and result.get("source_html_sha256") != entry["source_body_sha256"]):
                                raise ValueError("INVALID_CRAWL4AI_SOURCE_BINDING")
                            entry["offline_crawl4ai_extraction"] = result
                        except Exception:
                            entry["offline_crawl4ai_extraction"] = {
                                "schema_version":"empire.a2a.crawl4ai_offline_markdown.v1",
                                "status":"CRAWL4AI_INVALID_SOURCE_HOLD",
                                "source_url_fetched_by_this_module":False,
                                "raw_markdown_or_pii_exported":False,
                                "records_promoted_to_crm":0,
                            }
                    entry["self_described_sector_matched"] = any(k in content for k in TRADE[niche])
                    entry["self_described_city_or_region_matched"] = any(k in content for k in SCOPE[metro])
        except Exception:
            # Real network outages/robots challenges are visible as holds,
            # never converted into verified commercial evidence.
            entry["site_fetch_status"] = "NETWORK_OR_DNS_HOLD"
        records.append(entry)
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "execution_authority": "NONE",
        "collected_at_utc": time.astimezone(timezone.utc).isoformat(),
        "source_type": "FOUNDER_APPROVED_FIRST_PARTY_COMPANY_WEBSITES",
        "websites_attempted": len(records),
        "websites_http_200": sum(r["site_fetch_status"] == "HTTP_200" for r in records),
        "pages_converted_with_crawl4ai_offline": sum(
            isinstance(r["offline_crawl4ai_extraction"], dict) and
            r["offline_crawl4ai_extraction"].get("status") == "CRAWL4AI_MARKDOWN_EXTRACTED"
            for r in records
        ),
        "pages_structured_with_scrapling": sum(
            isinstance(r["offline_structured_extraction"], dict) and
            r["offline_structured_extraction"].get("status") == "SCRAPLING_STRUCTURED_PAGE_PARSED"
            for r in records
        ),
        "self_described_sector_and_region_matches": sum(
            r["self_described_sector_matched"] and r["self_described_city_or_region_matched"]
            for r in records
        ),
        "records": records,
        "source_data_is_self_published_not_independent_business_verification": True,
        "robots_denials_never_bypassed": True,
        "no_search_engine_anti_bot_circumvention": True,
        "no_openmanus_unrestricted_browser": True,
        "no_personal_contact_harvesting": True,
        "buyers_verified": 0, "city_level_purchase_demand_verified": False,
        "contacts_sent": 0, "crm_write_performed": False,
        "new_prospects_created": 0, "payment_transactions": 0,
    }
