"""V15: protect original founder qualification from unverified heat pump claims."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

from empire_os.heat_pump_commercial_review import (
    OFFICIAL_PROGRAMME_REVIEWS, review, _read_original_scout,
)
from scripts.build_buyer_qualification_actions import plan

NOW=datetime.now(timezone.utc)  # use fresh original Scout when the suite runs
ROOT=Path('/srv/empire_os')


def test_first_party_market_roles_are_separated_and_no_false_revenue():
    packet=review(ROOT, now=NOW)
    assert packet["market_companies"]==34
    assert packet["exact_contact_or_identity_holds"]==2
    assert packet["consumer_programme_restricted_count"]==8
    assert packet["research_eligible_for_role_qualification"]==24
    assert packet["founder_prioritized_count"]==12
    assert packet["outbound_authorized"] is False
    assert packet["verified_payable_buyers"]==0
    assert packet["new_crm_records"]==0
    assert packet["source_original_scout_status"]=="CURRENT"
    assert packet["recent_original_scout_first_party_companies"]>=1
    assert all(row["outbound_authorized"] is False
               and row["paid_pilot_verified"] is False
               for row in packet["research_inventory"])


def test_no_prior_sent_company_recontact_or_disallowed_customer_offer():
    packet=review(ROOT,now=NOW)
    rows={x["domain"]:x for x in packet["research_inventory"]}
    for domain in ("leadpronto.co.uk","newpoweruk.co.uk"):
        assert rows[domain]["priority"]=="HOLD"
        assert rows[domain]["founder_next_action"]=="HOLD_PRIOR_CONTACT_OR_IDENTITY_RECONCILIATION"
    assert rows["cbheating.co.uk"]["priority"]=="HOLD"
    assert rows["cbheating.co.uk"]["founder_next_action"]=="NOT_A_BUSINESS_PROGRAMME_CONSUMER_REFERRAL_RESTRICTED"
    assert rows["poweredleads.co.uk"]["priority"]=="D_SUPPLY_EXCHANGE_ONLY_REVIEW"
    assert rows["poweredleads.co.uk"]["offer_or_commission_accepted_for_empire"] is False


def test_real_first_party_partner_programme_cannot_become_buyer_budget():
    packet=review(ROOT,now=NOW)
    rows={x["domain"]:x for x in packet["research_inventory"]}
    good=rows["goodenergy.co.uk"]
    assert good["priority"]=="A_PARTNER_TERMS_REVIEW"
    assert good["programme_evidence"]["research_contact"]=="partnerships@goodenergy.co.uk"
    assert good["direct_purchase_statement_verified"] is False
    alto=rows["altoenergy.co.uk"]
    assert alto["current_scout_first_party_page_receipts"]>=1
    assert alto["direct_purchase_statement_verified"] is False
    assert OFFICIAL_PROGRAMME_REVIEWS["hpin.co.uk"]["classification"].startswith("CERTIFIED_INSTALLER_")


def test_stale_scout_rejects_receipt_claims(tmp_path):
    p=tmp_path/"runtime/buyer_acquisition/scout_latest.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"schema_version":"empire.buyer_acquisition_scout.v1",
        "mode":"OBSERVE","generated_at":(NOW-timedelta(days=3)).isoformat(),
        "outbound_sent":False,"database_write_performed":False,
        "candidates":[{"domain":"altoenergy.co.uk"}]}))
    data,state=_read_original_scout(tmp_path,now=NOW)
    assert state=="STALE_OR_UNVERIFIED"
    assert data=={}


def test_in_original_qualification_plan_without_extra_buyer_admissions():
    result=plan(ROOT)
    assert result["schema_version"]=="empire.buyer_qualification_actions.v1"
    review_field=result["heat_pump_commercial_review"]
    assert review_field["status"]=="FOUNDER_COMMERCIAL_REVIEW_WITH_REAL_EVIDENCE_GAPS"
    assert review_field["market_companies"]==34
    assert review_field["verified_payable_buyers"]==0
    assert result["buyer_conversation_verified"] is False
    assert result["outbound_sent"] is False
    assert len(result["targets"])==result["shortlisted_count"]
