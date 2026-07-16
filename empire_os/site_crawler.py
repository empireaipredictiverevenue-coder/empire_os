"""
Site Crawler — walks a company website, extracts contact info.

Uses stdlib urllib (no requests/beautifulsoup dependency).
Parses:
- mailto: links
- tel: links
- Contact / About / Team pages
- Plain-text emails and phone numbers

Returns a list of candidate contacts with provenance URLs.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from empire_os.mx_validator import extract_emails_from_text, extract_phones_from_text

logger = logging.getLogger("site_crawler")


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
    "(Empire-OS/3.0; +https://empire-os.local)"
)


@dataclass
class CrawledContact:
    """One contact candidate found on a site."""
    email: str = ""
    phone: str = ""
    name: str = ""
    title: str = ""
    source_url: str = ""
    page_type: str = ""  # "homepage" | "contact" | "about" | "team" | "other"


@dataclass
class CrawlResult:
    """Outcome of a site crawl."""
    domain: str = ""
    pages_crawled: int = 0
    contacts: list = field(default_factory=list)
    error: str = ""
    robots_blocked: bool = False

    @property
    def has_contact(self) -> bool:
        return len(self.contacts) > 0

    def best_email(self) -> Optional[CrawledContact]:
        """Return the highest-value contact (email > phone > nothing)."""
        with_email = [c for c in self.contacts if c.email]
        if with_email:
            return with_email[0]
        with_phone = [c for c in self.contacts if c.phone]
        if with_phone:
            return with_phone[0]
        return None


class SiteCrawler:
    """Walks a company site, collects contact candidates."""

    # Page paths to prioritise
    CONTACT_PATHS = [
        "/", "/contact", "/contact-us", "/contact.html", "/contact.php",
        "/about", "/about-us", "/about.html",
        "/team", "/our-team", "/staff", "/leadership", "/people",
        "/get-quote", "/request-quote",
    ]

    def __init__(self, max_pages: int = 5, timeout: int = 10):
        self.max_pages = max_pages
        self.timeout = timeout

    def crawl(self, domain_or_url: str) -> CrawlResult:
        """Crawl a site and return all contact candidates found."""
        result = CrawlResult(domain=domain_or_url)
        parsed = self._normalise_url(domain_or_url)
        if not parsed:
            result.error = "invalid domain"
            return result

        seen = set()
        for path in self.CONTACT_PATHS:
            if result.pages_crawled >= self.max_pages:
                break
            url = urllib.parse.urljoin(parsed, path)
            if url in seen:
                continue
            seen.add(url)
            html = self._fetch(url)
            if html is None:
                continue
            result.pages_crawled += 1
            page_type = self._classify_page(path)
            self._extract_from_html(html, url, page_type, result)

        return result

    def _normalise_url(self, domain_or_url: str) -> Optional[str]:
        """Turn 'acme.com' into 'https://acme.com/'."""
        if not domain_or_url:
            return None
        url = domain_or_url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parsed = urllib.parse.urlparse(url)
        if not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}/"

    def _fetch(self, url: str) -> Optional[str]:
        """Fetch a URL, return HTML body or None on failure."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                ct = resp.headers.get("content-type", "")
                if "html" not in ct.lower():
                    return None
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            logger.debug("fetch failed for %s: %s", url, e)
            return None

    def _classify_page(self, path: str) -> str:
        p = path.lower().rstrip("/")
        if p in ("", "/"):
            return "homepage"
        if "contact" in p:
            return "contact"
        if "about" in p:
            return "about"
        if any(k in p for k in ("team", "staff", "leadership", "people")):
            return "team"
        if "quote" in p:
            return "quote"
        return "other"

    def _extract_from_html(
        self, html: str, url: str, page_type: str, result: CrawlResult
    ):
        """Pull emails, phones, mailto:, tel: from HTML."""
        # mailto: links → contacts
        for m in re.finditer(r'href=["\']mailto:([^"\']+)["\']', html, re.I):
            email = m.group(1).split("?")[0].strip()
            if email and "@" in email:
                result.contacts.append(CrawledContact(
                    email=email, source_url=url, page_type=page_type,
                ))

        # tel: links → phones
        for m in re.finditer(r'href=["\']tel:([^"\']+)["\']', html, re.I):
            phone = m.group(1).strip()
            if phone:
                result.contacts.append(CrawledContact(
                    phone=phone, source_url=url, page_type=page_type,
                ))

        # Plain-text emails and phones from stripped HTML
        text = re.sub(r"<[^>]+>", " ", html)
        for email in extract_emails_from_text(text):
            # Skip generic role addresses (will be filtered later by validator)
            if not any(result.contacts and c.email == email for c in result.contacts):
                result.contacts.append(CrawledContact(
                    email=email, source_url=url, page_type=page_type,
                ))

        for phone in extract_phones_from_text(text):
            result.contacts.append(CrawledContact(
                phone=phone, source_url=url, page_type=page_type,
            ))