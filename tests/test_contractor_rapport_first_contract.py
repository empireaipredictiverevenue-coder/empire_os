"""The existing rapport-first policy must govern contractor research, not a new sales engine."""
from datetime import date
from pathlib import Path
import json
import pytest

from empire_os.outbound_department import plan_outbound_account
from empire_os.storm_contractor_independent_evidence import review_public_business_contact
from empire_os.storm_contractor_review import attach_existing_canonical_contact_history
from scripts.refresh_contractor_revenue_review import run

ROOT=Path(__file__).resolve().parents[1]
AS_OF=date(2026,10,10)


def candidate(domain):
    return next(r for r in run(as_of=AS_OF)["packets"] if r["company_domain"]==domain)


def test_all_eight_contractors_use_existing_rapport_guardrail_without_pitch():
    result=run(as_of=AS_OF)
    assert result["summary"]["rapport_gate_research_count"]==8
    assert result["summary"]["public_business_email_research_count"]==1
    for packet in result["packets"]:
        rapport=packet["existing_outbound_rapport_policy"]
        assert rapport["policy"]=="rapport_first_human_specific_v1"
        assert rapport["source"]=="empire_os.outbound_department.plan_outbound_account"
        assert rapport["next_action"]=="RESEARCH"
        assert rapport["first_touch_cta_allowed"] is False
        assert rapport["commercial_pricing_allowed"] is False
        assert rapport["execution_authority"]=="none"
        assert not packet["founder_review_ready"]
        assert not packet["outbound_authorized"]


def test_spc_historical_contact_evidence_not_person_or_consent():
    packet=candidate("spcroofs.com")
    record=packet["business_contact_research"]
    assert record["state"]=="PUBLIC_GENERAL_COMPANY_ROUTE_HISTORICAL_PERSON_HOLD"
    assert record["associated_public_business_email_domain"]=="spcgc.com"
    assert record["historical_registration_expired"] is True
    assert record["person_candidate_current_route_verified"] is False
    assert record["named_person_to_email_attribution_verified"] is False
    assert record["exact_recipient_suppression_clear"] is False
    assert not record["outbound_authorized"]


def test_spc_alternate_official_contact_domain_is_also_honoured_as_suppression_hold():
    reviewed=run(as_of=AS_OF)
    checked=attach_existing_canonical_contact_history(
        reviewed,prior_contact_domains={"spcgc.com"},suppressed_emails=set(),
    )
    spc=next(x for x in checked["packets"] if x["company_domain"]=="spcroofs.com")
    assert spc["previous_contact_domain_hold"] is True
    assert spc["contact_history_state"]=="PRIOR_OUTBOUND_DOMAIN_REVIEW_HOLD"
    assert spc["source_confirmed_company_domains_checked"]==["spcgc.com","spcroofs.com"]
    assert spc["outbound_authorized"] is False


def test_spc_historical_person_email_is_exact_match_suppression_hold_without_clearance():
    reviewed=run(as_of=AS_OF)
    checked=attach_existing_canonical_contact_history(
        reviewed,prior_contact_domains=set(),
        suppressed_emails={"jshaw@spcgc.com"},
    )
    spc=next(x for x in checked["packets"] if x["company_domain"]=="spcroofs.com")
    assert spc["historical_person_email_suppression_match"] is True
    assert spc["domain_has_suppressed_contact"] is True
    assert spc["contact_history_state"]=="SUPPRESSED_DOMAIN_CONTACT_HOLD"
    assert spc["suppression_verified_clear"] is False
    assert spc["outbound_authorized"] is False


def test_spc_general_mailbox_exact_suppression_match_not_send_permission():
    reviewed=run(as_of=AS_OF)
    checked=attach_existing_canonical_contact_history(
        reviewed,prior_contact_domains=set(),
        suppressed_emails={"info@spcgc.com"},
    )
    spc=next(x for x in checked["packets"] if x["company_domain"]=="spcroofs.com")
    assert spc["first_party_business_email_suppression_match"] is True
    assert spc["domain_has_suppressed_contact"] is True
    assert spc["recipient_level_suppression_verified"] is False
    assert not spc["outbound_authorized"]


def test_no_alias_prior_or_suppression_match_does_not_clear_to_contact():
    reviewed=run(as_of=AS_OF)
    checked=attach_existing_canonical_contact_history(
        reviewed,prior_contact_domains=set(),suppressed_emails=set(),
    )
    assert checked["summary"]["prior_outbound_domain_review_holds"]==0
    assert checked["summary"]["suppressed_domain_contact_holds"]==0
    assert checked["individual_recipient_suppression_cleared"] is False
    assert all(not p["outbound_authorized"] for p in checked["packets"])
    assert all(not p["suppression_verified_clear"] for p in checked["packets"])


@pytest.mark.parametrize("field,value",[
    ("outbound_authorized",True),
    ("do_not_contact_unless_governed_cleared",False),
    ("marketing_buyer_intent_verified",True),
])
def test_business_contact_evidence_cannot_grant_outbound(field,value):
    d=json.loads((ROOT/"docs/DFW_CONTRACTOR_BUSINESS_CONTACT_RESEARCH_20261010.json").read_text())
    d["records"][0][field]=value
    with pytest.raises(ValueError):
        review_public_business_contact(d,cohort_domains={"spcroofs.com"},as_of=AS_OF)


def test_historical_contact_cannot_claim_current_recipient():
    d=json.loads((ROOT/"docs/DFW_CONTRACTOR_BUSINESS_CONTACT_RESEARCH_20261010.json").read_text())
    d["records"][0]["official_historical_registry_contact"]["recipient_still_uses_email_verified"]=True
    with pytest.raises(ValueError,match="HISTORICAL_CONTACT_NOT_VALID_FOR_OUTBOUND"):
        review_public_business_contact(d,cohort_domains={"spcroofs.com"},as_of=AS_OF)


def test_unknown_person_cannot_enter_rapport_draft_even_with_source_evidence():
    plan = plan_outbound_account({
        "company_name": "SPC Construction & Roofing",
        "company_name_verified": True,
        "decision_maker": "Unknown",
        "contact_route": "company_routed",
        "person_bound": False,
        "buyer_review_status": "pending",
    }, evidence=[{
        "evidence_ref": "spc-first-party-public-website",
        "summary": "SPC publishes residential and commercial services",
        "verified": True, "fresh": True, "account_bound": True,
    }])
    assert plan["action_type"] == "RESEARCH"
    assert "decision_maker" in plan["missing_evidence"]
    assert plan["cta_allowed"] is False
    assert plan["price_allowed"] is False
    assert plan["execution_authority"] == "none"


def test_qualified_mock_identity_still_gets_rapport_not_pitch():
    from empire_os.outbound_department import review_outbound_draft
    fake_person = {
        "company_name": "SPC Construction & Roofing",
        "company_name_verified": True,
        "decision_maker": "Test Reviewer",
        "contact_route": "company_routed",
        "person_bound": False,
        "buyer_review_status": "pending",
    }
    evidence = [{
        "evidence_ref": "spc-first-party-public-website",
        "summary": "SPC publishes residential and commercial services",
        "verified": True, "fresh": True, "account_bound": True,
    }]
    plan = plan_outbound_account(fake_person, evidence=evidence)
    assert plan["action_type"] == "DRAFT_RAPPORT_TOUCH"
    assert plan["cta_allowed"] is False
    assert plan["price_allowed"] is False
    assert plan["execution_authority"] == "none"
    audit = review_outbound_draft(
        account=fake_person, plan=plan, subject="SPC Construction & Roofing",
        body=("SPC Construction & Roofing handles residential and commercial "
              "roofing in DFW. Book a call and see our $1500 pilot."),
        used_evidence_refs=["spc-first-party-public-website"],
    )
    assert "PREMATURE_CTA" in audit["blockers"]
    assert "PREMATURE_PRICE" in audit["blockers"]
    assert audit["send_enabled"] is False



def test_spc_founder_review_copy_passes_existing_policy_without_send_authority():
    from empire_os.outbound_department import review_outbound_draft

    path=ROOT/"docs/commercial/CONTRACTOR_SPC_RAPPORT_REVIEW_20261010.md"
    doc=path.read_text()
    subject=doc.split("**Proposed subject:** ", 1)[1].split("\n", 1)[0].strip()
    quoted=doc.split("**Proposed subject:** ", 1)[1].split("\n", 1)[1]
    quoted=quoted.split("## Blocking checklist", 1)[0]
    body="\n".join(line[2:].strip() for line in quoted.splitlines() if line.startswith("> "))
    # Simulated fixture ONLY: do not interpret this as a real person or
    # permission to move the original contractor out of RESEARCH.
    account={
        "company_name":"SPC Construction & Roofing",
        "company_name_verified":True,
        "decision_maker":"Mock Reviewer",
        "contact_route":"company_routed",
        "contact_email":"info@spcgc.com",
        "person_bound":False,
        "buyer_review_status":"pending",
    }
    evidence=[{
        "evidence_ref":"https://www.spcroofs.com/residential-roofing-services",
        "summary":"SPC lists both residential and commercial DFW roofing work",
        "verified":True,"fresh":True,"account_bound":True,
    }]
    plan=plan_outbound_account(account,evidence=evidence)
    assert plan["action_type"]=="DRAFT_RAPPORT_TOUCH"
    gate=review_outbound_draft(
        account=account,plan=plan,subject=subject,body=body,
        used_evidence_refs=[evidence[0]["evidence_ref"]],
    )
    assert gate["eligible"] is True and gate["blockers"]==[]
    assert gate["send_enabled"] is False
    assert gate["person_bound"] is False
    assert plan["cta_allowed"] is False
    assert plan["price_allowed"] is False
    assert plan["execution_authority"]=="none"
    assert "RESEARCH_ONLY" in doc
    assert "OUTBOUND_AUTHORIZED=false" in doc
    assert candidate("spcroofs.com")["existing_outbound_rapport_policy"]["next_action"]=="RESEARCH"
