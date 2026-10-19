"""Optional Scrapling HTML parser for Empire's EXISTING SiteCrawler.

It consumes already-fetched site HTML only: no browser, proxy, stealth bypass,
network request, company identity promotion, outbound or database mutation.
All returned contacts are unverified website observations, *not* person-bound
decision makers or commercial prospects.
"""
from __future__ import annotations

from urllib.parse import unquote, urlparse
import re

from empire_os.mx_validator import extract_emails_from_text, extract_phones_from_text
from empire_os.site_crawler import CrawledContact


MAX_HTML_BYTES = 512_000
MAX_CONTACTS_PER_PAGE = 40
MAX_TEXT_SEGMENTS = 1000


class ScraplingParserUnavailable(RuntimeError):
    """Parser dependency missing; do not quietly switch extraction engines."""


class ScraplingExtractionHeld(ValueError):
    """Input is unsafe or outside bounded public business page review."""


def _public_page(url: str) -> bool:
    if not isinstance(url, str) or not 0 < len(url) < 2049:
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port is not None:
            return False
    except ValueError:
        return False
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".localhost")):
        return False
    if not re.fullmatch(r"[a-z0-9.-]+", host) or "." not in host:
        return False
    if re.fullmatch(r"\d+(?:\.\d+){3}", host):
        return False
    return True


class ScraplingBusinessContactExtractor:
    """Explicitly opt-in parser, with byte, text, and contact caps."""

    engine = "scrapling_static_html"

    def extract_contacts(
        self, html: str, *, url: str, page_type: str
    ) -> list[CrawledContact]:
        if not _public_page(url):
            raise ScraplingExtractionHeld("nonpublic_or_untrusted_site_url")
        if (not isinstance(html, str) or not html.strip()
                or len(html.encode("utf-8")) > MAX_HTML_BYTES):
            raise ScraplingExtractionHeld("invalid_or_oversize_html")
        try:
            from scrapling.parser import Selector
        except ImportError as exc:
            raise ScraplingParserUnavailable("install Scrapling in a dedicated optional runtime") from exc

        page = Selector(html, url=url)
        contacts: list[CrawledContact] = []
        seen: set[tuple[str, str]] = set()

        def add(email: str = "", phone: str = "") -> None:
            if len(contacts) >= MAX_CONTACTS_PER_PAGE:
                return
            email = email.lower().strip()
            phone = phone.strip()
            if email and (len(email) > 254 or not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[a-zA-Z]{2,}", email)):
                return
            if phone and not 7 <= len(re.sub(r"\D", "", phone)) <= 17:
                return
            if not email and not phone:
                return
            key = (email, phone)
            if key in seen:
                return
            seen.add(key)
            contacts.append(CrawledContact(
                email=email, phone=phone, source_url=url, page_type=page_type,
            ))

        # Explicit business contact links take priority over incidental text.
        for value in page.css('a[href^="mailto:"]::attr(href)').getall()[:MAX_CONTACTS_PER_PAGE]:
            candidate = unquote(str(value).removeprefix("mailto:").split("?", 1)[0])
            add(email=candidate)
        for value in page.css('a[href^="tel:"]::attr(href)').getall()[:MAX_CONTACTS_PER_PAGE]:
            candidate = unquote(str(value).removeprefix("tel:")).strip()
            add(phone=candidate)

        # Static text only, no script, hidden forms, tracking pixels, or JS.
        segments = page.css("body :not(script):not(style):not(noscript)::text").getall()[:MAX_TEXT_SEGMENTS]
        # Limit total scanned characters; never parse a massive copied transcript.
        text = " ".join(str(v) for v in segments)[:100_000]
        for email in extract_emails_from_text(text):
            add(email=str(email))
        for phone in extract_phones_from_text(text):
            add(phone=str(phone))
        return contacts
