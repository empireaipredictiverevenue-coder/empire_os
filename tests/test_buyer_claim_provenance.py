"""Buyer purchasing claims must be page-level, first-party, traceable evidence."""
import hashlib

from empire_os.buyer_claim_provenance import (
    classify_buyer_source_pages, verified_direct_purchase_receipt,
)


def classify(*texts, website="https://buyer.example/"):
    pages = [
        {"url": f"https://buyer.example/page-{i}", "visible_text": text}
        for i, text in enumerate(texts)
    ]
    return classify_buyer_source_pages(
        pages, company_website=website, observed_at="2026-10-09T15:00:00+00:00",
    )


def test_explicit_first_party_direct_buying_yields_auditable_receipt():
    result = classify("We buy leads from verified publishers.")
    assert result["buyer_relationship"] == "direct_inventory_buyer"
    assert result["explicit_direct_purchase_observed"] is True
    packet = result["claim_receipts"][0]
    assert packet["source_url"] == "https://buyer.example/page-0"
    assert packet["claim_excerpt"] == "We buy leads from verified publishers."
    assert packet["content_sha256"] == hashlib.sha256(
        b"We buy leads from verified publishers."
    ).hexdigest()
    assert packet["observed_at"] == "2026-10-09T15:00:00+00:00"
    assert result["outbound_authorized"] is False
    assert result["database_write_performed"] is False
    assert verified_direct_purchase_receipt({"buyer_claim_provenance": result},
                                            company_website="https://buyer.example")


def test_seller_reference_to_its_buyers_is_not_a_buying_claim():
    result = classify("Our lead buyers purchase qualified roofing leads. We generate leads.")
    assert result["explicit_direct_purchase_observed"] is False
    assert result["buyer_relationship"] == "lead_supplier_or_publisher"


def test_marketplace_or_broker_is_not_automatically_direct_buyer():
    result = classify("Our lead marketplace connects publishers with advertisers.")
    assert result["buyer_relationship"] == "intermediary_or_marketplace"
    assert not result["explicit_direct_purchase_observed"]


def test_mixed_direct_and_supplier_site_requires_review():
    result = classify("We buy leads. We sell leads to customers.")
    assert result["buyer_relationship"] == "mixed_role_requires_review"
    assert result["explicit_direct_purchase_observed"] is False
    assert not verified_direct_purchase_receipt(
        {"buyer_claim_provenance": result}, company_website="https://buyer.example",
    )


def test_buying_for_our_clients_is_intermediary_not_direct():
    result = classify("We buy leads for our clients.")
    assert result["explicit_direct_purchase_observed"] is False
    assert result["buyer_relationship"] == "intermediary_or_marketplace"


def test_direct_purchase_for_other_clients_is_not_end_buyer_proof():
    result = classify("We buy calls for our customers.")
    assert result["buyer_relationship"] == "intermediary_or_marketplace"
    assert result["explicit_direct_purchase_observed"] is False


def test_direct_purchase_and_lead_resale_requires_review():
    result = classify("We buy leads. We resell leads to our advertiser partners.")
    assert result["buyer_relationship"] == "mixed_role_requires_review"
    assert result["explicit_direct_purchase_observed"] is False


def test_negated_purchase_not_promoted():
    result = classify("We do not buy leads from lead sellers.")
    assert result["explicit_direct_purchase_observed"] is False


def test_search_query_description_is_not_an_observed_page():
    result = classify_buyer_source_pages(
        [{"url": "https://unrelated.test/", "visible_text": "We buy leads."}],
        company_website="https://buyer.example",
    )
    assert result["claim_receipts"] == []
    assert not result["explicit_direct_purchase_observed"]
    assert result["skipped_pages"]["off_domain_or_invalid_url"] == 1


def test_domain_spoofing_and_missing_page_are_rejected():
    result = classify_buyer_source_pages([
        {"url": "https://buyer.example@attacker.test/page", "visible_text": "We buy leads."},
        {"url": "https://buyer.example/empty", "visible_text": ""},
    ], company_website="https://buyer.example")
    assert result["explicit_direct_purchase_observed"] is False
    assert result["skipped_pages"] == {
        "off_domain_or_invalid_url": 1,
        "no_visible_text": 1,
    }


def test_cross_page_conflicts_cannot_establish_direct_purchase():
    result = classify(
        "We buy inbound calls.",
        "We generate leads and supply buyers.",
    )
    assert result["buyer_relationship"] == "mixed_role_requires_review"
    assert result["explicit_direct_purchase_observed"] is False


def test_stale_and_future_dated_claims_cannot_be_treated_as_current():
    from datetime import datetime, timezone, timedelta
    now = datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc)
    result = classify("We buy leads.")
    evidence = {"buyer_claim_provenance": result}
    packet = result["claim_receipts"][0]
    packet["observed_at"] = (now - timedelta(days=31)).isoformat()
    assert not verified_direct_purchase_receipt(evidence, company_website="https://buyer.example", now=now)
    packet["observed_at"] = (now + timedelta(days=1)).isoformat()
    assert not verified_direct_purchase_receipt(evidence, company_website="https://buyer.example", now=now)
    packet["observed_at"] = now.isoformat()
    assert verified_direct_purchase_receipt(evidence, company_website="https://buyer.example", now=now)


def test_unverified_or_wrong_domain_receipt_fails_closed():
    data = classify("We purchase qualified appointments.")
    evidence = {"buyer_claim_provenance": data}
    assert not verified_direct_purchase_receipt(
        evidence, company_website="https://other.example",
    )
    data["claim_receipts"][0]["content_sha256"] = "invalid"
    assert not verified_direct_purchase_receipt(
        evidence, company_website="https://buyer.example",
    )
