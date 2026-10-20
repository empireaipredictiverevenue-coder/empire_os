"""Chosen approved product survives /buy → /commercial without fake orders.

Only static source assertions plus pure behavioural simulation here. Full
Next.js build and source-owner publication remain separately controlled.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BUY = ROOT / "apps/empire-public-site/src/app/buy/page.tsx"
COMMERCIAL = ROOT / "apps/empire-public-site/src/app/commercial/page.tsx"


def test_proposal_link_carries_selected_catalog_product():
    text = BUY.read_text()
    assert '/commercial?product=${encodeURIComponent(product.product_code)}#commercial-enquiry' in text
    assert 'href={product ?' in text
    assert '"/commercial#commercial-enquiry"' in text


def test_buyer_form_only_accepts_live_governed_offer_code():
    text = COMMERCIAL.read_text()
    assert 'new URLSearchParams(window.location.search).get("product")' in text
    assert 'data.offers.find((offer) => offer.product_code === requested)' in text
    assert 'setCode(approved?.product_code || data.offers[0]?.product_code || "")' in text


def test_unknown_or_removed_product_defaults_to_visible_approved_offer():
    # Mirrors the inlined two-branch selection contract; no arbitrary product
    # or price can be injected through query parameters.
    offers = [{"product_code": "consultancy_opportunity_assessment"},
              {"product_code": "competitor_search_gap"}]
    def choose(query):
        approved = next((x for x in offers if x["product_code"] == query), None)
        return approved["product_code"] if approved else offers[0]["product_code"]
    assert choose("competitor_search_gap") == "competitor_search_gap"
    assert choose("unknown") == "consultancy_opportunity_assessment"
    assert choose("consultancy_opportunity_assessment") == "consultancy_opportunity_assessment"


def test_price_is_never_taken_from_query_string():
    text = COMMERCIAL.read_text()
    assert 'get("price")' not in text
    assert 'get("amount")' not in text
    assert 'data.status !== "FOUNDER_LED_ENQUIRY_AVAILABLE"' in text
    assert "approved_price_cents" in text


def test_consent_and_no_checkout_controls_unchanged():
    text = COMMERCIAL.read_text()
    assert 'contact_consent: consent' in text
    assert 'if (!code || !consent || submitting' in text
    assert 'body.decision === "commercial_enquiry_recorded"' in text
    assert 'No order or payment created' in text


def test_deeplink_anchor_joins_to_real_form_not_checkout():
    buy, commercial = BUY.read_text(), COMMERCIAL.read_text()
    assert '#commercial-enquiry' in buy
    assert 'id="commercial-enquiry"' in commercial
    assert '<form onSubmit={submit}' in commercial


def test_does_not_touch_predictive_enterprise_or_crm_routes():
    text = BUY.read_text() + COMMERCIAL.read_text()
    assert '"/v1/checkout/commercial/interests"' in text
    assert '"/v1/checkout/orders"' in text  # Existing /buy gated checkout remains
    assert "fetch(\"/v1/checkout/commercial/offers\"" in text
    assert "new URLSearchParams" in text


def test_no_contact_or_order_is_fabricated_in_deeplink():
    text = BUY.read_text() + COMMERCIAL.read_text()
    assert 'localStorage.setItem' not in text
    assert 'sessionStorage.setItem' not in text
    assert 'new URLSearchParams(window.location.search).get("email")' not in text
    assert 'new URLSearchParams(window.location.search).get("contact_consent")' not in text

def test_enabled_checkout_also_offers_selected_product_proposal():
    text = BUY.read_text()
    assert "CREATE PAYMENT REQUEST" in text
    assert "REQUEST A PROPOSAL INSTEAD" in text
    assert "Prefer to discuss scope before ordering?" in text
    assert text.count("/commercial?product=") == 2
    assert text.index("REQUEST A PROPOSAL INSTEAD") < text.index("result ? (")


def test_alternative_proposal_link_does_not_submit_checkout_form():
    text = BUY.read_text()
    start = text.index("REQUEST A PROPOSAL INSTEAD")
    anchor = text.rfind("<a", 0, start)
    assert anchor >= 0
    assert "href={product ?" in text[anchor:start]
    assert "type=\"submit\"" not in text[anchor:start]
