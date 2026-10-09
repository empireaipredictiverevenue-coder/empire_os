import json
from datetime import date
from pathlib import Path

import pytest

from empire_os.storm_contractor_independent_evidence import review_independent_evidence
from empire_os.storm_contractor_review import build_contractor_review

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 10, 9)


def _loaded():
    def load(path):
        return json.loads((ROOT / path).read_text(encoding="utf-8"))
    return (
        load("runtime/revenue_strike/dfw_storm_2026-09-20.json"),
        load("docs/DFW_SITE_OBSERVATIONS_20261009.json"),
        load("docs/DFW_CONTRACTOR_PUBLIC_SIGNALS_20261009.json"),
        load("docs/DFW_CONTRACTOR_INDEPENDENT_EVIDENCE_20261009.json"),
    )


def _review(inputs):
    a,b,c,d=inputs
    return build_contractor_review(a,b,c,as_of=TODAY,independent_evidence=d)


def test_real_8_current_company_corrob_and_holds():
    result=_review(_loaded())
    counts=result["summary"]
    assert counts["historical_contractor_companies"] == 8
    assert counts["third_party_directory_domain_matches"] == 3
    assert counts["third_party_identity_conflict_holds"] == 2
    assert counts["identity_change_holds"] == 1
    assert counts["verified_company_legal_registrations"] == 0
    assert counts["independently_verified_purchase_intent"] == 0
    assert not result["outbound_authorized"]
    assert not result["contract_sent"]
    assert [p["company_domain"] for p in result["packets"][:3]] == [
        "maxexteriors.com", "180roofing.com", "spcroofs.com",
    ]
    assert all(not p["founder_review_ready"] for p in result["packets"])


def test_conflicting_bbb_cannot_promote_company():
    result=_review(_loaded())
    for domain in ("riseroofingconstruction.com","topnotchroofingrr.com"):
        packet=next(p for p in result["packets"] if p["company_domain"]==domain)
        assert packet["qualification"]=="IDENTITY_EVIDENCE_CONFLICT_HOLD"
        assert packet["research_priority_score"]==0
        assert "RESOLVE_THIRD_PARTY_IDENTITY_CONFLICT_DO_NOT_CONTACT" in packet["review_tasks"]


def test_third_party_directory_not_state_company_registration():
    result=_review(_loaded())
    company=next(p for p in result["packets"] if p["company_domain"]=="maxexteriors.com")
    research=company["independent_business_research"]
    assert research["state"]=="THIRD_PARTY_PROFILE_DOMAIN_MATCH"
    assert research["state_registry_identity_verified"] is False
    assert research["domain_ownership_verified"] is False
    assert not company["confirmed_commercial_buyer"]


def test_unreferenced_domain_fails():
    data=list(_loaded())
    data[3]["records"][0]["company_domain"]="someone-else.com"
    with pytest.raises(ValueError, match="DOMAIN_NOT_UNIQUE"):
        _review(data)


def test_duplicate_same_company_not_counted():
    data=list(_loaded())
    data[3]["records"].append(dict(data[3]["records"][0]))
    with pytest.raises(ValueError, match="DOMAIN_NOT_UNIQUE"):
        _review(data)


def test_imposter_directory_url_rejected():
    data=list(_loaded())
    data[3]["records"][0]["source_url"]="https://bbb.org.bad-host.com/us/tx/profile"
    with pytest.raises(ValueError, match="NOT_APPROVED_DIRECTORY"):
        _review(data)


def test_source_url_must_be_https():
    data=list(_loaded())
    data[3]["records"][0]["source_url"]="http://www.bbb.org/us/tx/profile"
    with pytest.raises(ValueError, match="NOT_HTTPS"):
        _review(data)


def test_third_party_bbb_stale_not_allowed():
    data=list(_loaded())
    data[3]["records"][0]["observed_at"]="2024-09-10"
    with pytest.raises(ValueError, match="STALE"):
        _review(data)


def test_third_party_different_name_not_promoted():
    data=list(_loaded())
    data[3]["records"][0]["listed_business_name"]="Some Other Roofing Company"
    with pytest.raises(ValueError, match="UNRELATED"):
        _review(data)


def test_third_party_domain_mismatch_auto_holds():
    data=list(_loaded())
    r=data[3]["records"][0]
    r["listing_website_url"]="https://different-roofing.com/"
    result=_review(data)
    row=next(p for p in result["packets"] if p["company_domain"]=="maxexteriors.com")
    assert row["qualification"]=="IDENTITY_EVIDENCE_CONFLICT_HOLD"
    assert row["research_priority_score"]==0


def test_third_party_not_hard_requirement_for_existing_review_api():
    a,b,c,_=_loaded()
    result=build_contractor_review(a,b,c,as_of=TODAY)
    assert result["summary"]["third_party_directory_domain_matches"] == 0
    assert result["summary"]["independently_verified_purchase_intent"] == 0


def test_three_public_directory_principals_added_as_unverified_work_leads():
    rows=_review(_loaded())["packets"]
    expected={
        "maxexteriors.com":("Pedro Torres","Owner/Director"),
        "180roofing.com":("Sebastian L. Ventura","Owner/Manager"),
        "spcroofs.com":("Jonathan Shaw","President"),
    }
    for domain,(name,role) in expected.items():
        company=next(p for p in rows if p["company_domain"]==domain)
        manager=company["independent_business_research"]["business_management_research"]
        assert manager["name"]==name
        assert manager["role_as_listed"]==role
        assert manager["status"]=="PUBLIC_DIRECTORY_LISTED_UNCONFIRMED"
        assert manager["real_person_identity_verified"] is False
        assert manager["decision_or_budget_authority_verified"] is False
        assert manager["business_contact_route_verified"] is False
        assert manager["recipient_suppression_verified"] is False
        assert manager["outbound_authorized"] is False
        assert company["founder_review_ready"] is False
        assert "VERIFY_DIRECTORY_LISTED_PRINCIPAL_IS_CURRENT_AUTHORISED_BUYER" in company["review_tasks"]


def test_directory_principal_cannot_claim_recipient_or_buyer_authority():
    a,b,c,d=_loaded()
    d["records"][0]["business_principal"]["recipient_suppression_clear"]=True
    with pytest.raises(ValueError,match="PRINCIPAL_AUTHORITY_UNVERIFIED"):
        build_contractor_review(a,b,c,as_of=TODAY,independent_evidence=d)


def test_directory_principal_cannot_claim_verified_decision_authority():
    a,b,c,d=_loaded()
    d["records"][0]["business_principal"]["decision_making_or_budget_authority_verified"]=True
    with pytest.raises(ValueError,match="PRINCIPAL_AUTHORITY_UNVERIFIED"):
        build_contractor_review(a,b,c,as_of=TODAY,independent_evidence=d)


def test_directory_principal_source_must_be_exactly_its_profile():
    a,b,c,d=_loaded()
    d["records"][0]["business_principal"]["source_url"]="https://www.bbb.org/us/tx/different-profile"
    with pytest.raises(ValueError,match="PRINCIPAL_AUTHORITY_UNVERIFIED"):
        build_contractor_review(a,b,c,as_of=TODAY,independent_evidence=d)


def test_directory_principal_cannot_inject_contact_or_email():
    a,b,c,d=_loaded()
    d["records"][0]["business_principal"]["email"]="not-verified@example.com"
    with pytest.raises(ValueError,match="PRINCIPAL_SCHEMA_INVALID"):
        build_contractor_review(a,b,c,as_of=TODAY,independent_evidence=d)
