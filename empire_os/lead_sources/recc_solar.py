"""Bounded RECC Solar PV member source for UK business identity.

The RECC public directory is used as provenance for internal acquisition only.
Raw directory content is not republished or resold.
"""
from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import re
import urllib.parse
import urllib.request
from typing import Iterator

from empire_os.lead_sources import LeadCandidate, SourceInfo


BASE = "https://www.recc.org.uk"
SEARCH_URL = BASE + "/scheme/members"
USER_AGENT = "EmpireOS-SourceIntelligence/1.0 (contact@empire-ai.co.uk)"
MAX_DETAILS = 40
TIMEOUT = 30

_UK_POSTCODE = re.compile(
    r"\b(?:GIR ?0AA|(?:[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}))\b",
    re.I,
)
_PHONE = re.compile(r"\bTel:\s*([+\d][\d ()-]{6,})", re.I)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.current_href = ""
        self.current_text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        self.current_href = dict(attrs).get("href", "") or ""
        self.current_text = []

    def handle_data(self, data):
        if self.current_href:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() != "a" or not self.current_href:
            return
        text = " ".join("".join(self.current_text).split())
        self.links.append((self.current_href, unescape(text)))
        self.current_href = ""
        self.current_text = []


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8", "ignore")


def _member_links(html: str, limit: int = MAX_DETAILS) -> list[tuple[str, str]]:
    parser = _LinkParser()
    parser.feed(html)
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for href, name in parser.links:
        if not href.startswith("/scheme/members/"):
            continue
        tail = href.rsplit("/", 1)[-1]
        if not tail or tail == "all" or tail.isdigit():
            continue
        if href in seen or not name:
            continue
        seen.add(href)
        rows.append((urllib.parse.urljoin(BASE, href), name))
        if len(rows) >= limit:
            break
    return rows


def _detail(name: str, url: str) -> LeadCandidate | None:
    html = _get(url)
    text = " ".join(
        re.sub(r"<[^>]+>", " ", unescape(html)).split()
    )
    if "Solar PV" not in text:
        return None

    phone_match = _PHONE.search(text)
    phone = " ".join(phone_match.group(1).split()) if phone_match else ""

    postcode_match = _UK_POSTCODE.search(text)
    postcode = postcode_match.group(0).upper().replace("  ", " ") if postcode_match else ""

    parser = _LinkParser()
    parser.feed(html)
    website = ""
    for href, _label in parser.links:
        clean = str(href or "").strip()
        if not clean.startswith(("http://", "https://")):
            continue
        host = urllib.parse.urlparse(clean).netloc.casefold()
        if "recc.org.uk" in host or "realschemes.org.uk" in host:
            continue
        website = clean
        break

    return LeadCandidate(
        name=name,
        phone=phone,
        niche="solar",
        metro="United Kingdom",
        state="",
        country_code="GB",
        language_code="en-GB",
        source_language="en-GB",
        timezone="Europe/London",
        details=(
            "Current RECC member; sector Solar PV. "
            + (f"Postcode {postcode}. " if postcode else "")
            + "Public RECC member detail used as identity provenance."
        ),
        source="recc_solar",
        lead_score=95 if website or phone else 85,
        url=url,
        raw={
            "recc_member_url": url,
            "business_website": website,
            "postcode": postcode,
            "sector": "Solar PV",
            "raw_resale_allowed": False,
        },
    )


def run(metro: str | None = None) -> Iterator[LeadCandidate]:
    # RECC is a UK-wide source. A metro is accepted for SourceInfo compatibility
    # but does not alter the directory query; downstream geo enrichment can use
    # postcode/company evidence.
    query = urllib.parse.urlencode({
        "technology": "Solar PV",
        "submitbutton": "submit",
    })
    html = _get(f"{SEARCH_URL}?{query}")
    for url, name in _member_links(html):
        try:
            candidate = _detail(name, url)
        except Exception:
            continue
        if candidate is not None:
            yield candidate


def register_source(reg):
    reg(SourceInfo(
        name="recc_solar",
        tier="real",
        requires=[],
        description=(
            "Renewable Energy Consumer Code current Solar PV member directory; "
            "bounded internal acquisition/provenance use, no raw directory resale."
        ),
        run_fn=run,
    ))
