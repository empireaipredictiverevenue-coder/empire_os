"""Synthetic end-to-end Scrapling evidence -> OWN Waterfall plan/gate replay."""
from datetime import datetime, timezone

import pytest

from empire_os.scrapling_source_evidence import ReviewedRecipe, extract_reviewed_page
from empire_os.waterfall import LeadContact
from empire_os.waterfall_source_bridge import (
    EvidenceReview, build_waterfall_source_review,
    replay_existing_waterfall_gate,
)


NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
HTML = """<html><body>
<article class='row'><span class='name'>Acme Solar Ltd</span>
<a href='/members/acme'>Directory record</a></article>
</body></html>"""


class Match:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Row:
    def css(self, selector):
        return Match({
            ".name::text": "Acme Solar Ltd",
            "a::attr(href)": "/members/acme",
        }.get(selector))


class Selector:
    def __init__(self, html, url):
        self.html = html

    def css(self, selector):
        return iter((Row(),))


def report(source="gb_recc_solar", niche="solar"):
    r = ReviewedRecipe(
        source_id=source,
        source_url=(
            "https://www.recc.org.uk/scheme/members" if source == "gb_recc_solar"
            else "https://api.company-information.service.gov.uk/"
        ),
        niche=niche, metro="London", row_css=".row",
        name_css=".name::text", website_css="a::attr(href)",
        max_rows=2, terms_reviewed=True, robots_reviewed=True,
        privacy_reviewed=True,
        review_evidence_refs=("terms:synthetic", "robots:synthetic", "privacy:synthetic"),
    )
    return extract_reviewed_page(
        recipe=r, html=HTML, observed_at=NOW,
        selector_factory=Selector,
    )


def review(vertical="solar", target_kind="contractor", **kwargs):
    params = dict(
        vertical=vertical, target_kind=target_kind,
        jurisdiction="GB-ENG",
        company_identity_ref="entity:manual-reviewed-test-001",
    )
    params.update(kwargs)
    return EvidenceReview(**params)


def plan(data=None, r=None):
    return build_waterfall_source_review(
        data if data is not None else report(),
        record_index=0,
        review=r or review(),
        now=NOW,
    )


def test_own_waterfall_registry_first_no_website_inference():
    result = plan()
    assert result["state"] == "EVIDENCE_REVIEW_READY"
    assert result["provider_order_review_only"] == ["registry_scraper"]
    assert result["default_provider_names"] == [
        "registry_scraper", "site_crawler", "empire_hunter",
    ]
    assert result["first_party_website_review_only"] is None
    assert result["contact_promotion_authorized"] is False
    assert result["outbound_authorized"] is False
    assert result["verified_lead_count"] == 0
    assert result["execution_authority"] == "none"


def test_independent_verified_site_changes_order_only_not_authority():
    result = plan(r=review(
        verified_first_party_website="https://acme-solar.example.com/",
        website_verification_ref="source:verified-owned-domain-001",
    ))
    assert result["state"] == "EVIDENCE_REVIEW_READY"
    assert result["provider_order_review_only"] == [
        "empire_hunter", "registry_scraper", "site_crawler",
    ]
    assert result["provider_execution_authorized"] is False


@pytest.mark.parametrize("vertical,kind", [
    ("insurance", "insurance_policyholder"),
    ("mass_torts", "claimant"),
    ("legal", "injured_person"),
    ("dental", "patient"),
    ("insurance", "individual_claimant"),
    ("unknown", "contractor"),
])
def test_consumer_and_unknown_target_fails_closed(vertical, kind):
    p = plan(r=review(vertical, kind))
    assert p["state"] == "HOLD"
    assert p["provider_order_review_only"] == []
    assert "not_an_approved_business_entity" in p["reasons"] or "vertical_not_approved" in p["reasons"]


@pytest.mark.parametrize("vertical,kind", [
    ("insurance", "insurance_broker"),
    ("insurance", "insurance_carrier"),
    ("insurance", "third_party_administrator"),
    ("insurance", "managed_repair_network"),
    ("legal", "law_firm"),
    ("mass_torts", "law_firm"),
    ("dental", "medical_practice"),
])
def test_regulated_b2b_firms_require_jurisdiction_policy(vertical, kind):
    p = plan(data=report(source="gb_companies_house", niche=vertical),
             r=review(vertical, kind))
    assert p["state"] == "HOLD"
    assert p["provider_order_review_only"] == []
    assert "jurisdiction" in " ".join(p["reasons"])
    allowed = plan(data=report(source="gb_companies_house", niche=vertical),
                   r=review(vertical, kind,
                            jurisdiction_policy_ref="compliance:synthetic-reviewed-only-001"))
    assert allowed["state"] == "EVIDENCE_REVIEW_READY"
    assert allowed["provider_order_review_only"] == ["registry_scraper"]
    assert allowed["execution_authority"] == "none"


def test_source_niche_crosswiring_is_held():
    p = plan(r=review("insurance", "insurance_broker",
                      jurisdiction_policy_ref="compliance:synthetic-only"))
    assert "source_not_authorized_for_vertical" in p["reasons"]


def test_missing_business_id_hold():
    assert "missing_independently_reviewed_company_identity" in plan(
        r=review(company_identity_ref="")
    )["reasons"]


def test_marketed_resale_or_live_report_flags_are_rejected():
    data = report()
    data["sellable_inventory_verified"] = True
    assert "source_report_invalid_commercial_claim" in plan(data=data)["reasons"]


def test_stale_report_is_held():
    data = report()
    data["observed_at"] = "2025-01-01T00:00:00+00:00"
    assert "stale_or_future_source_evidence" in plan(data=data)["reasons"]


def test_policy_ref_not_identity_proof():
    p = plan(data=report(source="gb_companies_house", niche="mass_torts"),
             r=review("mass_torts", "law_firm",
                      jurisdiction_policy_ref="review:law-firm-compliance-001",
                      company_identity_ref=""))
    assert p["state"] == "HOLD"


def test_missing_website_verification_rejected():
    p = plan(r=review(
        verified_first_party_website="https://acme-solar.example.com",
        website_verification_ref="",
    ))
    assert "verified_first_party_site_proof_required" in p["reasons"]


def test_replay_uses_existing_validation_gate_but_never_executes():
    p = plan(r=review(
        verified_first_party_website="https://acme-solar.example.com",
        website_verification_ref="source:domain-verified-by-independent-check",
    ))
    contacts = {
        "empire_hunter": LeadContact(
            email="general@acme.test", confidence=0.95,
            raw={"bound_to_decision_maker": False}
        ),
        "registry_scraper": LeadContact(
            email="founder@acme.test", confidence=0.94,
            raw={"bound_to_decision_maker": True}
        )
    }
    out = replay_existing_waterfall_gate(p, contacts)
    assert out["would_pass"] is True
    assert out["would_select_provider"] == "registry_scraper"
    assert out["checked"] == [
        {"provider": "empire_hunter", "gate_passed": False},
        {"provider": "registry_scraper", "gate_passed": True},
    ]
    assert out["outbound_authorized"] is False
    assert out["contact_promotion_authorized"] is False


def test_replay_blocked_plan_never_accepts_even_bound_contact():
    p = plan(r=review("mass_torts", "claimant"))
    out = replay_existing_waterfall_gate(
        p, {"registry_scraper": LeadContact(
            email="sensitive-person@example.test",
            confidence=1.0, raw={"bound_to_decision_maker": True},
        )},
    )
    assert out["status"] == "HOLD"
    assert not out["would_pass"]
    assert out["checked"] == []


def test_replay_rejects_forged_execution_authority():
    p = plan()
    p["execution_authority"] = "live"
    with pytest.raises(ValueError, match="execution authority"):
        replay_existing_waterfall_gate(p, {})


def test_no_default_provider_behaviour_changed():
    from empire_os.waterfall import build_default_waterfall
    w = build_default_waterfall()
    assert w.max_attempts == 3
    assert w.gate.min_confidence == 0.90
    assert w.gate.require_bound_contact is True


def _synthetic_yield_receipts(plan_value):
    return {
        name: {
            "attempts": 30,
            "validated_wins": {"empire_hunter": 12, "registry_scraper": 24, "site_crawler": 0}[name],
            "vertical": plan_value["vertical"],
            "jurisdiction": plan_value["jurisdiction"],
            "receipt_ref": "confirmed:synthetic-history-" + name,
            "observed_at": NOW.isoformat(),
        }
        for name in plan_value["provider_order_review_only"]
    }


def test_empirical_provider_order_must_have_comparable_receipts():
    from empire_os.waterfall_source_bridge import review_provider_order_by_verified_yield
    p = plan(r=review(
        verified_first_party_website="https://acme-solar.example.com",
        website_verification_ref="source:synthetic-website-001",
    ))
    proof = _synthetic_yield_receipts(p)
    out = review_provider_order_by_verified_yield(p, proof, now=NOW)
    assert out["state"] == "EVIDENCE_BASED_OFFLINE_ORDER_PROPOSAL"
    assert out["recommended_order_review_only"] == [
        "registry_scraper", "empire_hunter", "site_crawler"
    ]
    assert out["evidence_cohort_complete"] is True
    assert not out["provider_execution_authorized"]
    assert not out["outbound_authorized"]


def test_yield_planner_fail_closed_to_prior_order_on_incomplete_evidence():
    from empire_os.waterfall_source_bridge import review_provider_order_by_verified_yield
    p = plan(r=review(
        verified_first_party_website="https://acme-solar.example.com",
        website_verification_ref="source:synthetic-website-001",
    ))
    proof = _synthetic_yield_receipts(p)
    del proof["registry_scraper"]
    out = review_provider_order_by_verified_yield(p, proof, now=NOW)
    assert out["state"] == "DEFAULT_ORDER_PRESERVED"
    assert out["recommended_order_review_only"] == p["provider_order_review_only"]
    assert any("receipt_missing" in x for x in out["reasons"])


@pytest.mark.parametrize("corruption", [
    {"attempts": 2},
    {"validated_wins": 999},
    {"jurisdiction": "US-TX"},
    {"receipt_ref": ""},
    {"observed_at": "2025-01-01T00:00:00+00:00"},
])
def test_yield_planner_rejects_small_stale_unproven_or_cross_market(corruption):
    from empire_os.waterfall_source_bridge import review_provider_order_by_verified_yield
    p = plan(r=review(
        verified_first_party_website="https://acme-solar.example.com",
        website_verification_ref="source:synthetic-website-001",
    ))
    proof = _synthetic_yield_receipts(p)
    proof["empire_hunter"].update(corruption)
    out = review_provider_order_by_verified_yield(p, proof, now=NOW)
    assert out["state"] == "DEFAULT_ORDER_PRESERVED"
    assert out["recommended_order_review_only"] == p["provider_order_review_only"]
    assert out["execution_authority"] == "none"


def test_claimant_hold_cannot_be_reordered():
    from empire_os.waterfall_source_bridge import review_provider_order_by_verified_yield
    p = plan(r=review("mass_torts", "claimant"))
    out = review_provider_order_by_verified_yield(p, {}, now=NOW)
    assert out["recommended_order_review_only"] == []
    assert "source_review_hold" in out["reasons"]
