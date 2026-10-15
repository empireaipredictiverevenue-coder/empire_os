"""Evidenced TAM buyer-readiness SEO asset remains human/founder gated."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import review_tam_editorial_evidence as review


@pytest.fixture
def article():
    return review.DRAFT.read_text("utf-8")


def source_exists(path):
    return Path(path).is_file()


def test_current_draft_is_reviewable_without_any_release_or_outbound():
    result = review.run()
    assert result["status"] == "EVIDENCED_DRAFT_READY_FOR_HUMAN_REVIEW"
    assert result["public_article_word_count"] >= 900
    assert result["content_sha256"] == hashlib.sha256(
        review.DRAFT.read_bytes()
    ).hexdigest()
    assert result["reader_cta_paths"] == ["/commercial", "/predictive-revenue"]
    assert result["known_revenue_topic_disclosed_impressions"] == 1
    assert result["keyword_opportunity_score"] is None
    assert result["observed_keyword_search_volume"] is None
    assert result["editorial_review_approved"] is False
    assert result["founder_release_approved"] is False
    assert result["privacy_and_legal_review_approved"] is False
    assert result["publishing_authorized"] is False
    assert result["indexation_authorized"] is False
    assert result["redirect_authorized"] is False
    assert result["network_calls"] is False
    assert result["database_writes"] is False
    assert result["outbound_sent"] is False


def test_provenance_refs_are_backed_by_exact_existing_evidence_files(article):
    data = review.inspect_draft(article, exists=source_exists)
    assert data["source_evidence_refs_verified"] == list(review.SOURCE_REFS)
    assert data["local_source_reference_file_count"] == 7


@pytest.mark.parametrize("change", [
    lambda t: t.replace("status: DRAFT_REQUIRES_EDITORIAL_AND_FOUNDER_RELEASE",
                        "status: PUBLISHED"),
    lambda t: t.replace("publication_authorized: false", "publication_authorized: true"),
    lambda t: t.replace("indexation_authorized: false", "indexation_authorized: true"),
    lambda t: t.replace("redirect_authorized: false", "redirect_authorized: true"),
    lambda t: t.replace("canonical_url: NOT_DECIDED",
                        "canonical_url: https://empire-ai.co.uk/aeo/accounting/TAM/"),
    lambda t: t.replace("outbound_authorized: false", "outbound_authorized: true"),
])
def test_attempt_to_grant_approval_by_editing_metadata_fails_closed(article, change):
    report = review.inspect_draft(change(article), exists=source_exists)
    assert report["status"] == "HELD_EDITORIAL_SOURCE_REVIEW"
    assert report["publishing_authorized"] is False


@pytest.mark.parametrize("alteration", [
    lambda t: t.replace("](/commercial)", "](https://external-sales.example/buy)"),
    lambda t: t.replace("](/commercial)", "](/buy)"),
    lambda t: t.replace("](/predictive-revenue)", "](https://empire-ai.co.uk/payment)"),
    lambda t: t.replace("](/commercial)", "](/commercial) [free stuff](/hidden)"),
])
def test_cta_escaping_or_unapproved_purchase_link_is_rejected(article, alteration):
    report = review.inspect_draft(alteration(article), exists=source_exists)
    assert report["reason_code"] == "UNVERIFIED_EXTERNAL_OR_BINDING_CTA"


@pytest.mark.parametrize("claim", [
    "Guaranteed ROI", "Guaranteed revenue", "proven conversion uplift",
    "99% accurate", "live checkout", "buy now",
    "98% accuracy on our internal tests",
])
def test_invented_sales_performance_or_payment_claims_block(article, claim):
    changed = article.replace("A total addressable market (TAM)", claim + ". A total addressable market (TAM)")
    result = review.inspect_draft(changed, exists=source_exists)
    assert result["status"] == "HELD_EDITORIAL_SOURCE_REVIEW"
    assert result["reason_code"] == "UNSUPPORTED_SALES_CLAIM" or result["reason_code"] == "UNSUPPORTED_MEASURED_PERFORMANCE_CLAIM"


def test_changed_factual_provenance_or_missing_file_holds(article):
    report = review.inspect_draft(article.replace("EMPIRE-CONTROLS-01", "EVIDENCE-NOT-FOUND"),
                                  exists=source_exists)
    assert report["reason_code"] == "MISSING_EDITORIAL_PROVENANCE_REF"
    report = review.inspect_draft(article, exists=lambda _: False)
    assert report["reason_code"] == "SOURCE_EVIDENCE_FILE_UNAVAILABLE"


def test_buyer_readiness_levels_must_all_remain(article):
    bad = article.replace("**4. Declared buying interest**", "Confirmed buyer")
    report = review.inspect_draft(bad, exists=source_exists)
    assert report["reason_code"] == "BUYER_INTENT_EVIDENCE_LADDER_INCOMPLETE"


def test_draft_must_define_limitations_and_unverified_conversion(article):
    bad = article.replace("not probabilities", "probabilities")
    report = review.inspect_draft(bad, exists=source_exists)
    assert report["reason_code"] == "SIGNALS_UNLAWFULLY_PRESENTED_AS_PROBABILITIES"


def test_draft_size_and_source_trust_bound(tmp_path, article):
    bad = tmp_path / "draft.md"
    bad.write_text(article)
    assert review.run(bad)["status"] == "EVIDENCED_DRAFT_READY_FOR_HUMAN_REVIEW"
    bad.write_text("spam" * 10000)
    report = review.run(bad)
    assert report["reason_code"] == "DRAFT_UNBOUNDED_OR_TRIVIAL"
    linked = tmp_path / "alias.md"
    linked.symlink_to(review.DRAFT)
    assert review.run(linked)["reason_code"] == "DRAFT_FILE_UNTRUSTED"


def test_article_never_infers_industry_wide_statistics_from_one_gsc_impression():
    text = review.DRAFT.read_text("utf-8")
    public, notes = text.split("## Editorial release notes — not public article copy", 1)
    assert "one **disclosed impression**" in notes
    assert "50 impressions" not in public
    assert "conversion rate" not in public.casefold()
    assert "signed order" in public
    assert "actual" in public.casefold()
    assert "no evidence means no automatic outreach" in public.casefold()


def test_exact_keyword_strategy_has_no_fabricated_demand_score():
    from empire_os.keyword_universe import review_keyword_record
    assert review.KEYWORD_INPUT["keyword"] == "which companies in my tam are ready to buy"
    result = review_keyword_record(review.KEYWORD_INPUT)
    assert result["review_ready"] is True
    assert result["opportunity"]["available"] is False
    assert "observed_demand" in result["opportunity"]["missing"]
    assert result["publishing_enabled"] is False
    assert result["indexation_enabled"] is False


def test_review_inherits_no_network_api_or_secret_access(monkeypatch):
    import socket
    def forbid(*_args, **_kwargs):
        raise AssertionError("UNEXPECTED_NETWORK")
    monkeypatch.setattr(socket, "create_connection", forbid)
    result = review.run()
    assert result["network_calls"] is False
    assert result["outbound_sent"] is False
    assert "secret" not in json.dumps(result).lower()
