import copy

import pytest

from empire_os.storm_contractor_review import attach_existing_canonical_contact_history


def review():
    return {
        "schema": "empire.revenue_strike.contractor_founder_review.v1",
        "as_of": "2026-10-09",
        "outbound_authorized": False,
        "execution_authority": "none",
        "summary": {"historical_contractor_companies": 2},
        "packets": [
            {"company_domain": "maxexteriors.com", "review_tasks": [],
             "canonical_contact_history_checked": False,
             "suppression_verified_clear": False,
             "founder_review_ready": False, "outbound_authorized": False},
            {"company_domain": "spcroofs.com", "review_tasks": [],
             "canonical_contact_history_checked": False,
             "suppression_verified_clear": False,
             "founder_review_ready": False, "outbound_authorized": False},
        ],
    }


def test_prior_domain_contact_is_hold_not_resend_permission():
    original = review()
    checked = attach_existing_canonical_contact_history(
        original, prior_contact_domains={"maxexteriors.com"},
        suppressed_emails=set(),
    )
    assert checked["summary"]["prior_outbound_domain_review_holds"] == 1
    assert checked["packets"][0]["contact_history_state"] == "PRIOR_OUTBOUND_DOMAIN_REVIEW_HOLD"
    assert checked["packets"][1]["contact_history_state"] == "NO_DOMAIN_MATCH_RECIPIENT_STILL_UNVERIFIED"
    assert all(not p["outbound_authorized"] for p in checked["packets"])
    assert original["packets"][0].get("contact_history_state") is None
    assert checked["individual_recipient_suppression_cleared"] is False


def test_suppressed_email_domain_is_hold_without_email_leak():
    checked = attach_existing_canonical_contact_history(
        review(), prior_contact_domains=set(),
        suppressed_emails={"person@spcroofs.com"},
    )
    assert checked["packets"][1]["contact_history_state"] == "SUPPRESSED_DOMAIN_CONTACT_HOLD"
    assert checked["summary"]["suppressed_domain_contact_holds"] == 1
    assert "person@" not in str(checked)
    assert checked["packets"][1]["suppression_verified_clear"] is False


def test_missing_recipient_never_cleared_even_if_no_history():
    checked = attach_existing_canonical_contact_history(
        review(), prior_contact_domains=set(), suppressed_emails=set(),
    )
    assert all(p["domain_contact_history_checked"] for p in checked["packets"])
    assert not any(p["canonical_contact_history_checked"] for p in checked["packets"])
    assert not any(p["suppression_verified_clear"] for p in checked["packets"])


def test_overlay_is_deterministic_and_pure():
    a = review()
    x = attach_existing_canonical_contact_history(a, prior_contact_domains={"spcroofs.com"},
                                                 suppressed_emails={"abc@spcroofs.com"})
    y = attach_existing_canonical_contact_history(a, prior_contact_domains={"spcroofs.com"},
                                                 suppressed_emails={"abc@spcroofs.com"})
    assert x == y
    assert a == review()


def test_untrusted_authority_rejected():
    a=review()
    a["outbound_authorized"]=True
    with pytest.raises(ValueError, match="GOVERNED"):
        attach_existing_canonical_contact_history(a, prior_contact_domains=set(),
                                                 suppressed_emails=set())


def test_history_sets_must_be_valid():
    with pytest.raises(ValueError, match="UNVERIFIED_CANONICAL"):
        attach_existing_canonical_contact_history(review(), prior_contact_domains=[],
                                                 suppressed_emails=set())
