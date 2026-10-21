"""Source-passage harness: no publisher claims or hallucinations promoted."""
from datetime import datetime, timezone
from hashlib import sha256

import pytest

from empire_os.research.original_source_passages import (
    extract_source_passage_anchors, MAX_EXCERPT_WORDS
)
from empire_os.research.brokerage_editorial_review import (
    COUNTRY_SOURCES, review_brokerage_editorial
)
from empire_os.research.brokerage_decision_brief import build_brokerage_decision_brief

NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)


def test_original_passage_quotes_keep_only_bounded_body_content():
    document = b"""
    <html><body><header><p>Dental implants guaranteed first in Google</p></header>
      <main><h1>Dental implant options</h1>
       <p>We describe dental implants as an option for replacing missing teeth
       and advise a consultation for individual choices.</p>
       <p>Our implant placement process is explained in a separate appointment.</p>
      </main><footer><p>Full arch therapy is the best in town</p></footer>
      <script>window.claim = 'best surgeon ever'</script></body></html>
    """
    anchors = extract_source_passage_anchors(document)
    terms = [a["term"] for a in anchors]
    assert "dental implants" in terms and "implant placement" in terms
    assert "surgeon" not in terms and "full arch" not in terms
    for anchor in anchors:
        assert len(anchor["original_page_excerpt"]) <= 165
        assert len(anchor["original_page_excerpt"].split()) <= MAX_EXCERPT_WORDS
        assert anchor["term"] in anchor["original_page_excerpt"].lower()
        assert anchor["excerpt_sha256"] == sha256(
            anchor["original_page_excerpt"].encode()).hexdigest()
        assert anchor["publisher_claim_truth_verified"] is False
        assert anchor["client_republication_rights_verified"] is False


def test_script_svg_hidden_navigation_will_not_supply_false_support():
    html = b"""<html><body><nav><p>Surgeon and dentures</p></nav>
        <main><svg><text>surgeon</text></svg><p aria-hidden="true">3d mapping</p>
        <p>Dental implants are included in our published service overview.</p>
        </main></body></html>"""
    result = extract_source_passage_anchors(html)
    assert [r["term"] for r in result] == ["dental implants"]


@pytest.mark.parametrize("bad", [b"", b"x" * 600_001, None])
def test_unbounded_or_missing_document_fails_closed(bad):
    with pytest.raises(ValueError, match="BOUNDED_ORIGINAL"):
        extract_source_passage_anchors(bad)


def test_passage_receipt_passes_to_brief_without_customer_approval():
    def fake(url):
        html = b"<main><h1>Dental implant surgery services</h1><p>Dental implants are on our published service page and described for patients.</p></main>"
        return {
            "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
            "content_sha256": sha256(html).hexdigest(),
            "document_headings": ["Dental implant surgery services"],
            "source_passage_anchors": extract_source_passage_anchors(html),
        }
    report = review_brokerage_editorial("US", inspect_fn=fake, observed_at=NOW)
    brief = build_brokerage_decision_brief(report)
    assert brief["original_pages_inspected"] == len(COUNTRY_SOURCES["US"])
    assert all(
        row["original_passage_anchors_for_editorial_only"]
        for row in brief["evidence_ledger"]
    )
    for row in brief["evidence_ledger"]:
        assert not row["licensing_reuse_cleared"]
        assert row["factual_interpretation_editorial_review_required"]
        assert row["original_passage_anchors_for_editorial_only"][0][
            "publisher_assertion_not_independently_verified"] is True
    assert brief["editorial_approval"] is False
    assert brief["client_delivery_authorized"] is False


def test_edited_passage_checksum_blocks_spoofed_claim():
    def injected(url):
        return {
            "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
            "content_sha256": "a" * 64,
            "document_headings": ["Original source"],
            "source_passage_anchors": [{
                "term": "dental implants",
                "original_page_excerpt": "We have dental implants and guarantee 5x more patients",
                "excerpt_sha256": "0" * 64,
            }],
        }
    source = review_brokerage_editorial("GB", inspect_fn=injected, observed_at=NOW)
    with pytest.raises(ValueError, match="TAMPERED"):
        build_brokerage_decision_brief(source)
