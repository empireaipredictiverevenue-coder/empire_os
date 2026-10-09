from copy import deepcopy
from datetime import date

import pytest

from empire_os.storm_contractor_review import build_contractor_review

NOW = date(2026, 10, 9)
SITES_SCHEMA = "empire.claims_exchange.dfw_site_review_v1"
SIGNALS_SCHEMA = "empire.revenue_strike.dfw_public_signals.v1"


def source():
    cohort = {
        "schema_version": "empire.revenue_strike.storm.v1",
        "outbound_sent": False, "market": "Dallas-Fort Worth, TX",
        "prospects": [
            {"business_name": "Company One Roofing", "website": "https://one-roof.com"},
            {"business_name": "Company Two Roofing", "website": "https://two-roof.com"},
        ],
    }
    sites = {
        "schema": SITES_SCHEMA,
        "sites": [
            {
                "original_domain": "one-roof.com", "source_url": "https://one-roof.com/",
                "final_url": "https://one-roof.com/", "observed_at": NOW.isoformat(),
                "reviewer": "public_review", "self_described_name": "Company One Roofing",
                "roofing_services_observed": True, "dfw_service_area_observed": True,
                "public_business_contact": {"type": "email", "value": "info@one-roof.com"},
                "insurance_claims_wording_observed": True,
            },
            {
                "original_domain": "two-roof.com", "source_url": "https://two-roof.com/",
                "final_url": "https://unrelated-roof.com/", "observed_at": NOW.isoformat(),
                "reviewer": "public_review", "self_described_name": "Unrelated Roofing",
                "roofing_services_observed": True, "dfw_service_area_observed": True,
                "public_business_contact": None,
                "insurance_claims_wording_observed": False,
            },
        ],
    }
    signals = {
        "schema": SIGNALS_SCHEMA, "market": "Dallas-Fort Worth, TX",
        "signals": [
            {
                "company_domain": "one-roof.com",
                "kind": "public_sales_hiring",
                "source_url": "https://one-roof.com/careers",
                "observed_at": NOW.isoformat(),
                "observed_fact": "The company's website publishes an open roofing sales careers page.",
                "verified_from_first_party_site": True,
            },
        ],
    }
    return cohort, sites, signals


def test_founder_review_is_stable_evidence_no_authority():
    a,b,c = source()
    result = build_contractor_review(a,b,c,as_of=NOW)
    assert result == build_contractor_review(a,b,c,as_of=NOW)
    assert result["summary"]["historical_contractor_companies"] == 2
    assert result["summary"]["independently_verified_purchase_intent"] == 0
    assert result["summary"]["approved_outbound_count"] == 0
    assert not result["outbound_authorized"]
    assert not result["contract_sent"]
    first, second = result["packets"]
    assert first["company_name"] == "Company One Roofing"
    assert first["research_priority_score"] == 56
    assert first["confirmed_commercial_buyer"] is False
    assert first["signing"]["provider"] == "documenso"
    assert not first["signing"]["send_authorized"]
    assert first["proposed_offer"]["pilot_fee_usd_hypothesis"] == 1500
    assert first["proposed_offer"]["binding_quote"] is False
    assert second["qualification"] == "IDENTITY_CHANGE_HOLD"
    assert second["research_priority_score"] == 0
    assert second["signing"]["contract_stage"] == "NOT_CREATED"


def test_claims_copy_flags_remain_for_human_legal_review():
    r=build_contractor_review(*source(),as_of=NOW)
    assert "INSURANCE_ADVERTISING_LEGAL_COPY_REVIEW" in r["packets"][0]["review_tasks"]


def test_unknown_external_signal_company_fails_closed():
    a,b,c=source()
    c["signals"][0]["company_domain"]="unknown-roof.com"
    c["signals"][0]["source_url"]="https://unknown-roof.com/careers"
    with pytest.raises(ValueError, match="OUTSIDE_VERIFIED_COHORT"):
        build_contractor_review(a,b,c,as_of=NOW)


def test_unsafe_signal_host_not_accepted():
    a,b,c=source()
    c["signals"][0]["source_url"]="https://evil.example.org/"
    with pytest.raises(ValueError, match="NOT_FIRST_PARTY_SOURCE"):
        build_contractor_review(a,b,c,as_of=NOW)


@pytest.mark.parametrize("when",["2020-10-09","2026-10-10"])
def test_stale_or_future_signals_rejected(when):
    a,b,c=source()
    c["signals"][0]["observed_at"]=when
    with pytest.raises(ValueError, match="SIGNAL_STALE_OR_FUTURE"):
        build_contractor_review(a,b,c,as_of=NOW)


def test_buyer_assertion_cannot_inflate_score():
    a,b,c=source()
    c["signals"][0]["observed_fact"] = "They definitely want to buy our $1500 pilot"
    r=build_contractor_review(a,b,c,as_of=NOW)
    assert r["summary"]["independently_verified_purchase_intent"] == 0
    assert not r["packets"][0]["founder_review_ready"]


def test_duplicate_signal_not_double_counted():
    a,b,c=source()
    c["signals"].append(deepcopy(c["signals"][0]))
    r=build_contractor_review(a,b,c,as_of=NOW)
    assert len(r["packets"][0]["source_evidence"]) == 1
    assert r["packets"][0]["research_priority_score"] == 56


def test_raw_homeowner_claims_data_rejected():
    a,b,c=source()
    c["signals"][0]["claim_number"]="private-data"
    with pytest.raises(ValueError):
        build_contractor_review(a,b,c,as_of=NOW)


def test_invalid_source_schema_fails():
    a,b,c=source()
    c["schema"]="wrong"
    with pytest.raises(ValueError, match="UNSUPPORTED"):
        build_contractor_review(a,b,c,as_of=NOW)


def test_registry_and_documenso_links_are_existing_empireos():
    r=build_contractor_review(*source(),as_of=NOW)
    assert r["packets"][0]["proposed_offer"]["marketing_registry_key"]=="storm_home_services_gtm"
    assert r["packets"][0]["signing"]["existing_deal_room"]=="/v1/deal-room"
    assert all(not p["canonical_contact_history_checked"] and not p["suppression_verified_clear"]
               for p in r["packets"])


def test_claim_contingent_fees_never_derived_from_storm_source():
    r=build_contractor_review(*source(),as_of=NOW)
    assert all(p["proposed_offer"]["payable_claims_or_settlement_percentage"] is False
               for p in r["packets"])
