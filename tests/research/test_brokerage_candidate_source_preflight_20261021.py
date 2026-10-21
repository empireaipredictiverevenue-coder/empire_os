"""Exact publisher-candidate test harness, including negative authority checks."""
from datetime import datetime, timezone
from hashlib import sha256

import pytest

from empire_os.research.brokerage_candidate_source_preflight import (
    CANDIDATES, MAX_BYTES, preflight_candidate,
)
from empire_os.research.original_source_passages import extract_source_passage_anchors

URL = next(iter(CANDIDATES[("roofing", "GB")]))
NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)
HTML = b"""<!doctype html><html><body><main>
<h1>Birmingham Commercial Roofing Services</h1>
<p>We provide roofing repairs, commercial roofing and roof maintenance
for sites across Birmingham and the wider region.</p></main></body></html>"""


def test_original_candidate_observed_but_not_admitted():
    requested = []
    def fetch(url):
        requested.append(url)
        return HTML
    report = preflight_candidate(niche="roofing", country="GB",
                                 source_url=URL, fetch_fn=fetch,
                                 observed_at=NOW)
    assert requested == [URL]
    assert report["status"] == "CANDIDATE_ORIGINAL_PAGE_OBSERVED_NOT_ADMITTED"
    assert report["original_body_sha256"] == sha256(HTML).hexdigest()
    assert report["observed_headings"]
    assert report["short_source_anchors"]
    assert all(len(p["original_page_excerpt"]) <= 165
               and len(p["original_page_excerpt"].split()) <= 25
               for p in report["short_source_anchors"])
    for key in (
        "source_admitted", "source_reuse_rights_verified",
        "original_publisher_claims_verified", "research_owner_approved",
        "editorial_signoff", "outbound_authorized",
        "customer_delivery_authorized", "commercial_actions_authorized",
        "database_writes", "payment_authorized"
    ):
        assert report[key] is False


@pytest.mark.parametrize("url,niche,country", [
    ("http://ehsroofing.co.uk/", "roofing", "GB"),
    ("https://ehsroofing.co.uk@127.0.0.1/", "roofing", "GB"),
    ("https://ehsroofing.co.uk/redirect", "roofing", "GB"),
    ("https://127.0.0.1/private", "roofing", "GB"),
    ("https://ehsroofing.co.uk/", "dental", "GB"),
    ("https://ehsroofing.co.uk/", "roofing", "US"),
])
def test_unapproved_destinations_cannot_fetch(url, niche, country):
    calls = []
    with pytest.raises(ValueError, match="SOURCE_CANDIDATE_NOT_IN_EXACT_OWNER_REVIEW_SET"):
        preflight_candidate(
            niche=niche, country=country, source_url=url,
            fetch_fn=lambda u: calls.append(u) or HTML,
        )
    assert not calls


def test_incomplete_and_unavailable_source_stays_held():
    args = dict(niche="roofing", country="GB", source_url=URL)
    missing = preflight_candidate(**args, fetch_fn=lambda _: b"<html><body><h1>Directory</h1></body></html>")
    assert missing["status"] == "CANDIDATE_ORIGINAL_PAGE_TOPIC_OR_STRUCTURE_HELD"
    assert missing["source_admitted"] is False
    broken = preflight_candidate(**args, fetch_fn=lambda _: (_ for _ in ()).throw(TimeoutError()))
    assert broken["status"] == "CANDIDATE_ORIGINAL_PAGE_FETCH_HELD"
    assert broken["source_admitted"] is False
    oversized = preflight_candidate(**args, fetch_fn=lambda _: b"x" * (MAX_BYTES + 1))
    assert oversized["status"] == "CANDIDATE_ORIGINAL_PAGE_FETCH_HELD"


def test_bounded_custom_vocabulary_and_original_dental_default():
    terms = ("roofing", "roof repair")
    rows = extract_source_passage_anchors(HTML, terms=terms)
    assert any(x["term"] == "roofing" for x in rows)
    assert extract_source_passage_anchors(HTML) == []
    for invalid in (("x",), tuple(), tuple("roofing" for _ in range(13)),
                    ("roofing", "roofing"), ("rm -rf",)):
        with pytest.raises(ValueError, match="BOUNDED_SOURCE_TERM_CATALOGUE_REQUIRED"):
            extract_source_passage_anchors(HTML, terms=invalid)


def test_source_with_real_document_title_and_no_heading_is_reviewable():
    html = (b"<html><head><title>EHS Roofing | Birmingham Based Roofing "
            b"Contractors</title></head><body><main>"
            b"<p>Roofing repairs, roof maintenance and commercial roofing "
            b"services are displayed in this source document.</p></main></body></html>")
    report = preflight_candidate(
        niche="roofing", country="GB", source_url=URL,
        fetch_fn=lambda _: html, observed_at=NOW,
    )
    assert report["status"] == "CANDIDATE_ORIGINAL_PAGE_OBSERVED_NOT_ADMITTED"
    assert report["observed_document_title"].startswith("EHS Roofing")
    assert report["observed_headings"] == []
    assert report["short_source_anchors"][0]["term"] == "roofing"
    assert report["source_admitted"] is False
