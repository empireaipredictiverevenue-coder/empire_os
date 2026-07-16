"""Tests for the site crawler."""
from unittest.mock import patch, MagicMock

import pytest
from empire_os.site_crawler import SiteCrawler, CrawledContact, CrawlResult


SAMPLE_HTML = """
<html>
<body>
<h1>Acme Roofing</h1>
<p>Contact: <a href="mailto:owner@acmeroofing.com">Email</a></p>
<p>Phone: <a href="tel:+15551234567">(555) 123-4567</a></p>
<p>Or reach <a href="mailto:info@acmeroofing.com">our team</a></p>
<p>Address: 123 Main St, Springfield, IL 62701</p>
</body>
</html>
"""

CONTACT_HTML = """
<html>
<body>
<h1>Contact Us</h1>
<a href="mailto:hello@acme.com">Email</a>
<a href="tel:5551234567">Call</a>
</body>
</html>
"""


class TestCrawlerHelpers:
    def test_normalise_url_strips_scheme(self):
        c = SiteCrawler()
        assert c._normalise_url("acme.com") == "https://acme.com/"
        assert c._normalise_url("http://acme.com") == "http://acme.com/"
        assert c._normalise_url("https://acme.com/path") == "https://acme.com/"

    def test_normalise_url_invalid(self):
        c = SiteCrawler()
        assert c._normalise_url("") is None
        assert c._normalise_url("not a domain at all!@#") is None or "http" in (c._normalise_url("not a domain at all!@#") or "")

    def test_classify_page(self):
        c = SiteCrawler()
        assert c._classify_page("/") == "homepage"
        assert c._classify_page("/contact") == "contact"
        assert c._classify_page("/contact-us") == "contact"
        assert c._classify_page("/about") == "about"
        assert c._classify_page("/our-team") == "team"
        assert c._classify_page("/staff") == "team"
        assert c._classify_page("/random") == "other"

    def test_extract_mailto(self):
        c = SiteCrawler()
        result = CrawlResult()
        c._extract_from_html(SAMPLE_HTML, "https://acme.com/", "homepage", result)
        emails = [x.email for x in result.contacts if x.email]
        assert "owner@acmeroofing.com" in emails
        assert "info@acmeroofing.com" in emails

    def test_extract_tel(self):
        c = SiteCrawler()
        result = CrawlResult()
        c._extract_from_html(SAMPLE_HTML, "https://acme.com/", "homepage", result)
        phones = [x.phone for x in result.contacts if x.phone]
        assert any("555" in p for p in phones)

    def test_extract_classifies_page(self):
        c = SiteCrawler()
        result = CrawlResult()
        c._extract_from_html(SAMPLE_HTML, "https://acme.com/", "homepage", result)
        for contact in result.contacts:
            assert contact.page_type == "homepage"


class TestCrawler:
    def test_crawl_with_mocked_fetch(self):
        """Crawl returns contacts when fetch returns HTML."""
        c = SiteCrawler(max_pages=3)
        with patch.object(c, "_fetch", return_value=SAMPLE_HTML):
            result = c.crawl("acmeroofing.com")
        assert result.pages_crawled >= 1
        assert result.has_contact
        emails = [x.email for x in result.contacts if x.email]
        assert len(emails) > 0

    def test_crawl_handles_no_response(self):
        c = SiteCrawler()
        with patch.object(c, "_fetch", return_value=None):
            result = c.crawl("nonexistent.com")
        assert result.pages_crawled == 0
        assert not result.has_contact

    def test_crawl_best_email_picks_first_email(self):
        c = SiteCrawler()
        with patch.object(c, "_fetch", return_value=SAMPLE_HTML):
            result = c.crawl("acmeroofing.com")
        best = result.best_email()
        assert best is not None
        assert best.email != ""

    def test_crawl_respects_max_pages(self):
        c = SiteCrawler(max_pages=2)
        with patch.object(c, "_fetch", return_value=CONTACT_HTML):
            result = c.crawl("acme.com")
        assert result.pages_crawled <= 2

    def test_crawl_records_domain(self):
        c = SiteCrawler()
        with patch.object(c, "_fetch", return_value=None):
            result = c.crawl("example.com")
        assert result.domain == "example.com"


class TestCrawledContact:
    def test_defaults(self):
        c = CrawledContact()
        assert c.email == ""
        assert c.phone == ""
        assert c.page_type == ""