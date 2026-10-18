"""Bounded first-party SEO/AEO/GEO/A2A visibility preflight; no mutation or tracking."""
from __future__ import annotations

from html.parser import HTMLParser
import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

BASE = "https://empire-ai.co.uk"
PATHS = (
    "/commercial",
    "/industries/roofing",
    "/aeo/roofing/DFW/",
    "/sitemap.xml",
    "/.well-known/agent-card.json",
    "/a2a/v1/discovery",
    "/agent-web/capabilities",
)
MAX_BYTES = 350_000


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Scan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.h1 = 0
        self.h2 = 0
        self.canonical = []
        self.robots = []
        self.main_depth = 0
        self.main_links = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "main":
            self.main_depth += 1
        if tag == "h1":
            self.h1 += 1
        if tag == "h2":
            self.h2 += 1
        if tag == "link" and "canonical" in str(a.get("rel", "")).split():
            self.canonical.append(a.get("href"))
        if tag == "meta" and a.get("name", "").lower() == "robots":
            self.robots.append(a.get("content", "").lower())
        if tag == "a" and self.main_depth:
            self.main_links.append(a.get("href", ""))

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "main":
            self.main_depth = max(0, self.main_depth - 1)

    def handle_data(self, text):
        if self.in_title:
            self.title += text


def fetch_public(path):
    if path not in PATHS:
        raise ValueError("unapproved_public_url")
    req = Request(BASE + path, headers={
        "User-Agent": "Empire-ReadOnly-Capability-Audit/1.0",
        "Accept": "text/html,application/json,application/xml;q=0.9",
    }, method="GET")
    try:
        response = build_opener(NoRedirect()).open(req, timeout=10)
    except HTTPError as error:
        response = error
    except (TimeoutError, OSError, URLError) as error:
        return {"status": None, "body": b"", "error": type(error).__name__}
    with response:
        blob = response.read(MAX_BYTES + 1)
        if len(blob) > MAX_BYTES:
            return {"status": response.status, "body": b"", "error": "response_size_exceeded"}
        return {"status": response.status, "body": blob, "error": None}


def review(observations):
    """Evaluate injected snapshots for safe offline tests and owner review."""
    result = {"schema": "empire.discovery.four_surface_readonly.v1",
              "authority": "OBSERVE", "production_mutation": False,
              "seo": {}, "aeo": {}, "geo": {}, "a2a": {}}
    scans = {}
    for path in PATHS[:3]:
        response = observations.get(path, {})
        item = {"http": response.get("status"),
                "available": response.get("status") == 200,
                "error": response.get("error")}
        if item["available"]:
            page = Scan()
            page.feed(response["body"].decode("utf8", "replace"))
            canon = page.canonical[0] if len(page.canonical) == 1 else None
            item.update({"title_present": bool(page.title.strip()),
                         "h1_count": page.h1, "h2_count": page.h2,
                         "self_canonical": canon == BASE + path.rstrip("/"),
                         "noindex": any("noindex" in x for x in page.robots),
                         "relevant_commercial_links": sum(
                             x.startswith("/commercial") or
                             x.startswith("/industries/roofing")
                             for x in page.main_links),
                         "link_to_roofing_pillar": "/industries/roofing" in page.main_links})
        scans[path] = item
    result["seo"]["pages"] = scans
    site = observations.get("/sitemap.xml", {})
    count = None
    if site.get("status") == 200:
        try:
            xml = ET.fromstring(site["body"])
            count = len(xml.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"))
        except ET.ParseError:
            pass
    result["seo"]["sitemap_http"] = site.get("status")
    result["seo"]["sitemap_declared_url_count"] = count
    result["seo"]["gsc_clicks_and_indexation"] = "UNKNOWN_THIS_REVIEW"
    aeo = scans["/aeo/roofing/DFW/"]
    result["aeo"] = {"reviewed_page": "/aeo/roofing/DFW/",
                     "answer_headings": aeo.get("h2_count"),
                     "contextual_roofing_pillar_link": aeo.get("link_to_roofing_pillar"),
                     "answer_engine_citation_verified": "UNKNOWN"}
    result["geo"] = {"first_party_explanation_page": "/commercial",
                     "external_ai_mentions_or_citations": "UNKNOWN",
                     "ai_visibility_not_inferable_from_schema": True}
    payloads = {}
    for path in PATHS[4:]:
        response = observations.get(path, {})
        if response.get("status") == 200:
            try:
                parsed = json.loads(response["body"])
                payloads[path] = parsed if isinstance(parsed, dict) else {}
            except (ValueError, UnicodeDecodeError, TypeError):
                payloads[path] = {}
        else:
            payloads[path] = {}
    card = payloads["/.well-known/agent-card.json"]
    discovery = payloads["/a2a/v1/discovery"]
    catalog = payloads["/agent-web/capabilities"]
    advertised = card.get("skills", [])
    catalogued = catalog.get("capabilities", [])
    interfaces = card.get("supportedInterfaces", [])
    advertised = advertised if isinstance(advertised, list) else []
    catalogued = catalogued if isinstance(catalogued, list) else []
    interfaces = interfaces if isinstance(interfaces, list) else []
    skills = {str(s.get("id")) for s in advertised if isinstance(s, dict)}
    names = {str(s.get("name")) for s in catalogued if isinstance(s, dict)}
    try:
        safe_interfaces = bool(interfaces) and all(
            isinstance(x, dict)
            and urlsplit(str(x.get("url", ""))).scheme == "https"
            and str(x.get("protocolBinding")) in ("HTTP+JSON", "JSONRPC", "GRPC")
            for x in interfaces)
    except ValueError:
        safe_interfaces = False
    exposure = [discovery.get(k) for k in (
        "privileged_actions_exposed", "payments_exposed", "allocations_exposed")]
    result["a2a"] = {
        "agent_card_http": observations.get("/.well-known/agent-card.json", {}).get("status"),
        "discovery_http": observations.get("/a2a/v1/discovery", {}).get("status"),
        "catalogue_http": observations.get("/agent-web/capabilities", {}).get("status"),
        "skills_advertised": len(skills),
        "catalogue_capabilities": len(names),
        "catalogue_skills_agree": bool(skills) and skills == {"empire." + n for n in names},
        "https_transport_declared": safe_interfaces,
        "no_privileged_actions_exposed": exposure == [False, False, False]
            and catalog.get("privilegedActionsExposed") is False,
        "seo_aeo_geo_advertised": {"growth.seo.audit", "growth.aeo.audit",
                                  "growth.geo.visibility"}.issubset(names),
        "authenticated_agent_transactions_proven": "UNKNOWN",
    }
    return result


def run():
    return review({p: fetch_public(p) for p in PATHS})
