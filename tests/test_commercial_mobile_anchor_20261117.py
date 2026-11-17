"""Regression guard for the existing commercial enquiry mobile deep-link after catalogue load.

Code-only checks complement real-browser acceptance. No publication, POST or server.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "apps/empire-public-site/src/app/commercial/page.tsx"


def test_exact_offer_loaded_hash_scroll_is_bounded_and_user_respecting():
    text = PAGE.read_text(encoding="utf-8")
    assert '["#commercial-enquiry", "#proposal-heading"].includes(window.location.hash)' in text
    assert "if (!offers.length" in text
    assert 'document.getElementById("commercial-enquiry")' in text
    assert 'window.innerHeight - 175' in text
    assert 'section.scrollIntoView({ behavior: "instant", block: "start" })' in text
    assert '["wheel", "touchstart", "pointerdown", "keydown"]' in text
    assert "window.cancelAnimationFrame(scheduledFrame)" in text
    assert "new ResizeObserver(scheduleAlignment)" in text
    assert "new MutationObserver(scheduleAlignment)" in text
    assert "window.setTimeout(" in text
    assert "4500" in text


def test_original_first_party_contract_and_consent_are_not_bypassed():
    text = PAGE.read_text(encoding="utf-8")
    assert 'fetch("/v1/checkout/commercial/offers", { cache: "no-store" })' in text
    assert "selectApprovedProposalOffer(requested, data.offers)" in text
    assert 'fetch("/v1/checkout/commercial/interests", {' in text
    assert 'method: "POST"' in text
    assert "contact_consent: consent" in text
    assert "disabled={!code || !consent || submitting ||" in text
    assert "reuseCommercialInterestAttempt(" in text
    assert "setConsent(true)" not in text
    assert "regional_pricebook_sha256:" not in text
