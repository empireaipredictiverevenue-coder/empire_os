"""Public supplier interest != a payable, contactable or deliverable order."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from copy import deepcopy
import json
import pytest

from empire_os.jev_preoffer_evidence_review import review_preoffer

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "docs/commercial/JEV_B2B_SUPPLIER_REQUESTS_COUNTERPARTY_READINESS_20261022.json"
LIVE = ROOT / "docs/commercial/JEV_PUBLIC_TWO_CASE_PREOFFER_REVIEW_20261022.json"
SUPPLY = Path("/srv/empire_os/runtime/lead_supply/private_leadgen/research_queue_latest.json")
NOW = datetime(2026, 10, 22, 13, 0, tzinfo=timezone.utc)


def inputs():
    cases = json.loads(CASE.read_text())
    lead = json.loads(SUPPLY.read_text())
    # Synthetic fixed clock: production source refreshes in parallel.
    cases["as_of_utc"] = (NOW - timedelta(minutes=40)).isoformat()
    lead["generated_at"] = (NOW - timedelta(minutes=5)).isoformat()
    # Canonical Lead Supply refreshes throughout the day. Keep the fixed
    # regression numbers synthetic, not dependent on a moving live file.
    lead.update({
        "canonical_selected_inventory_records": 180,
        "canonical_evidence_hold_records": 84,
        "canonical_capacity_waitlist_records": 96,
        "immediately_sellable_inventory": 0,
        "qualified_buyers": 0,
        "verified_buyer_capacity": 0,
        "ready_for_outbound": 0,
    })
    return cases, lead


def evaluate(cases=None, supply=None, as_of=NOW):
    a, b = inputs()
    return review_preoffer(
        a if cases is None else cases,
        b if supply is None else supply,
        as_of=as_of)


def test_real_aggregate_portfolio_finds_zero_ready_delivery():
    out = evaluate()
    assert out["status"] == "B2B_PREOFFER_READINESS_HELD_RESEARCH_ONLY"
    assert out["lead_supply_status"] == "CURRENT_AGGREGATE_RESEARCH_ONLY_ZERO_SELLABLE"
    assert out["lead_supply_counts"] == {
        "selected":180, "held_for_evidence":84,
        "waiting_for_buyer_capacity":96,"sellable":0}
    assert out["commercial_offers_ready"] == 0
    assert out["promised_deliveries"] == 0
    assert out["messages_sent"] == 0
    assert out["database_writes"] is False


def test_web_agency_full_batch_economics_are_not_guaranteed():
    out = evaluate()
    web = next(x for x in out["plans"] if x["public_case_reference"] == "1uk1vw1")
    assert web["full_batch_record_target"] == 50
    assert web["gross_payment_per_fully_accepted_batch_usd"] == 150
    assert web["actual_accepted_record_count"] == 0
    assert web["projected_profit_verified"] is False
    assert web["source_reuse_and_contact_purpose_rights_verified"] is False
    assert web["commercial_offer_ready"] is False
    assert web["contact_authorized"] is False


def test_tennessee_closed_deal_commission_is_not_received_revenue():
    out = evaluate()
    roofer = next(x for x in out["plans"] if x["public_case_reference"] == "1wciats")
    assert roofer["stated_close_based_commission_percent"] == 10
    assert roofer["guaranteed_commission_revenue_usd"] == 0
    assert roofer["closed_deal_value_verified"] is False
    assert roofer["qualified_appointment_definition_agreed"] is False
    assert roofer["appointment_pilot_ready"] is False
    assert roofer["contact_authorized"] is False


@pytest.mark.parametrize("key,value", [
    ("verified_named_buyer_companies",1),
    ("current_buying_commitments_verified",1),
    ("ready_to_contact",True),
    ("ready_to_deliver",True),
    ("source_licensing_or_contact_consent_verified",True),
    ("actual_supply_committed",1),
    ("outbound_sent",1),
    ("crm_writes",True),
    ("execution_authority","execute"),
])
def test_upstream_counterparty_authority_spoof_rejected(key,value):
    cases,_ = inputs()
    cases[key] = value
    with pytest.raises(ValueError):
        evaluate(cases=cases)


@pytest.mark.parametrize("key,value", [
    ("legal_business_identity_verified",True),
    ("current_request_reconfirmed_by_company",True),
    ("organic_compliant_source_supply_proven",True),
    ("automatic_contact_allowed",True),
    ("available_qualifying_appointments_or_b2b_batches",50),
])
def test_individual_counterparty_promotion_rejected(key,value):
    cases,_ = inputs()
    cases["cases"][0][key] = value
    with pytest.raises(ValueError):
        evaluate(cases=cases)


def test_stale_source_is_not_called_current():
    _, supply = inputs()
    supply["generated_at"] = (NOW - timedelta(days=2)).isoformat()
    report = evaluate(supply=supply)
    assert report["lead_supply_status"] == "SOURCE_MISSING_OR_STALE"
    assert report["lead_supply_counts"]["selected"] is None
    assert report["commercial_offers_ready"] == 0


def test_missing_supply_is_safe():
    report = evaluate(supply={})
    assert report["commercial_offers_ready"] == 0
    assert report["lead_supply_status"] == "SOURCE_MISSING_OR_STALE"


@pytest.mark.parametrize("key,value", [
    ("buyer_outreach_authorized",True),
    ("canonical_empiredb_writes",True),
    ("public_inventory_claim_allowed",True),
    ("immediately_sellable_inventory",50),
    ("qualified_buyers",1),
    ("verified_buyer_capacity",1),
])
def test_live_supply_must_not_grant_unverified_commercial_authority(key,value):
    _, supply = inputs()
    supply[key] = value
    with pytest.raises(ValueError):
        evaluate(supply=supply)


def test_count_tampering_rejected():
    _, supply = inputs()
    supply["canonical_evidence_hold_records"] = 83
    with pytest.raises(ValueError):
        evaluate(supply=supply)


def test_naive_review_clock_rejected():
    with pytest.raises(ValueError):
        evaluate(as_of=datetime(2026,10,22,13))


def test_immutable_live_receipt_has_no_contact_details_or_sales_claims():
    packet = json.loads(LIVE.read_text())
    assert packet["schema_version"] == "empire.jev.public_b2b_preoffer_review.v1"
    assert packet["original_public_source_fingerprint_verified"] is True
    assert packet["recipient_records_opened"] == 0
    assert packet["commercial_offers_ready"] == 0
    assert packet["lead_supply_counts"]["sellable"] == 0
    assert packet["paid_revenue_verified"] is False
    assert packet["messages_sent"] == 0
    assert packet["database_writes"] is False
    assert packet["execution_authority"] == "none"
    text = LIVE.read_text()
    assert "@" not in text
    assert "private_evidence_url" not in text
    assert "phone_number" not in text
    assert "contact_name" not in text
