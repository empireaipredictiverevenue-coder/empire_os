"""Original A2A owner + Lead Supply + Finance pickup; zero commercial execution."""
from copy import deepcopy
from datetime import timedelta
import json

import pytest

from empire_os.predictive_commercial_requirements import review_commercial_requirement
from empire_os.predictive_commercial_supply_readiness import review_original_lead_readiness
from empire_os.predictive_commercial_fulfilment import plan_commercial_fulfilment
from empire_os.predictive_existing_owner_pickup import (
    review_existing_a2a_owner_research,
    review_department_owner_pickup,
    read_existing_a2a_owner_reports,
)
from empire_os.enterprise_finance_evidence_readiness import review_finance_source_readiness
from test_predictive_commercial_requirements_fulfilment import (
    NOW,source_packets,H,
)
from empire_os.predictive_commercial_requirements import tampa_roofing_founder_example


def requirement(*,industry="roofing",country="US",state="FL",city="Tampa",currency="USD",qty=20):
    a=tampa_roofing_founder_example()
    a.update(country=country,state=state,city=city,currency=currency,
             industry=industry,requested_qualified_leads=qty)
    return review_commercial_requirement(a,as_of=NOW)


def report():
    return {
        "schema_version":"empire.a2a.targeted_owner_research_handoff.v1",
        "mode":"OBSERVE","execution_authority":"NONE",
        "generated_at":NOW.isoformat(),
        "profiles_reviewed":2,
        "prepared_handoff_ticket_count":4,
        "owner_queue_published":False,"owner_response_received":False,
        "tasks_dispatched":0,"messages_sent":0,
        "buyer_record_writes":0,"externally_verified_new_buyers":0,
        "handoff_tickets":[
            {
                "ticket_id":H(n)[:24],"sector":sector,"market":metro,
                "review_owner":owner,"state":"PREPARED_NOT_DELIVERED",
                "may_send_messages":False,"may_write_canonical_crm":False,
                "may_call_external_api":False,"owner_approval_required":True,
            }
            for n,sector,metro,owner in [
                ("a","roofing","tampa, fl","buyer_scout"),
                ("b","roofing","tampa, fl","community_intent"),
                ("c","hvac","phoenix, az","buyer_scout"),
                ("d","hvac","phoenix, az","community_intent"),
            ]
        ],
    }


def receipts():
    return {
        "schema_version":"empire.a2a.owner_research_receipt_review.v1",
        "mode":"OBSERVE","execution_authority":"NONE",
        "owner_task_dispatches_by_this_protocol":0,
        "outbound_authority":False,"money_movement_authority":False,
        "buyer_identity_verified_by_this_protocol":False,
        "buyer_qualified_by_this_protocol":False,
        "purchase_intent_verified_by_this_protocol":False,
        "authenticated_owner_replies":0,
        "prepared_research_requests":4,
        "owner_public_keys_configured":[],
    }


def existing(req=None,rep=None,rcpt=None):
    return review_existing_a2a_owner_research(
        req or requirement(),rep if rep is not None else report(),
        rcpt if rcpt is not None else receipts(),as_of=NOW,
    )


def test_exact_roofing_tampa_reuses_only_original_existing_owner_research_tickets():
    r=existing()
    assert r["status"]=="EXISTING_A2A_PROFILE_RESEARCH_ONLY_NO_CUSTOMER_ACK"
    assert r["source_existing_profiles_count"]==2
    assert r["source_prepared_review_tickets_count"]==4
    assert r["source_matching_exact_sector_city_region_tickets_count"]==2
    assert r["source_matching_review_owners"]==["buyer_scout","community_intent"]
    assert len(set(r["source_matching_prepared_ticket_ids"]))==2
    assert r["original_owner_authenticated_reply_count"]==0
    assert r["original_owner_receipt_state"]=="NO_AUTHENTICATED_OWNER_REPLY_OR_KEYS"
    assert r["original_owner_dispatch_receipt"] is None
    assert r["owner_source_reported_match_is_our_requirement_acknowledgement"] is False
    assert r["source_authenticated_buyer_or_customer_order"] is False
    assert r["outbound_authorized"] is False


def test_hvac_phoenix_matches_distinct_owner_tickets_but_not_a_buyer():
    req=requirement(industry="hvac",state="AZ",city="Phoenix",qty=30)
    a=existing(req=req)
    assert a["source_matching_exact_sector_city_region_tickets_count"]==2
    assert a["reviewed_industry"]=="hvac"
    assert a["reviewed_city_region"]=="phoenix, az"
    assert a["source_authenticated_buyer_or_customer_order"] is False


@pytest.mark.parametrize("industry,state,city",[
    ("roofing","AZ","Phoenix"),
    ("hvac","FL","Tampa"),
    ("solar","TX","Houston"),
    ("roofing","FL","St Petersburg"),
    ("construction","NY","New York"),
])
def test_no_imagined_company_market_equivalence_or_new_research_dispatch(industry,state,city):
    req=requirement(industry=industry,state=state,city=city)
    a=existing(req=req)
    assert a["status"]=="NO_EXACT_PREEXISTING_A2A_SECTOR_CITY_REGION_PROFILE"
    assert a["source_matching_exact_sector_city_region_tickets_count"]==0
    assert a["source_authenticated_buyer_or_customer_order"] is False


def test_original_no_a2a_report_is_unknown_not_zero():
    out=review_existing_a2a_owner_research(requirement(),None,None,as_of=NOW)
    assert out["status"]=="ORIGINAL_A2A_OWNER_RESEARCH_UNAVAILABLE"
    assert out["source_prepared_review_tickets_count"] is None
    assert out["source_matching_exact_sector_city_region_tickets_count"] is None
    assert out["original_owner_authenticated_reply_count"] is None


def test_stale_a2a_report_cannot_create_fresh_leads():
    p=report();p["generated_at"]=(NOW-timedelta(days=4)).isoformat()
    out=existing(rep=p)
    assert out["status"]=="ORIGINAL_A2A_OWNER_RESEARCH_STALE_HOLD"
    assert out["source_matching_exact_sector_city_region_tickets_count"] is None


@pytest.mark.parametrize("key,value",[
    ("tasks_dispatched",1),
    ("messages_sent",1),
    ("buyer_record_writes",1),
    ("externally_verified_new_buyers",1),
    ("execution_authority","DISPATCH"),
    ("owner_queue_published",True),
    ("owner_response_received",True),
    ("prepared_handoff_ticket_count",10),
])
def test_forged_a2a_owner_delivery_or_ticket_counts_rejected(key,value):
    p=report();p[key]=value
    with pytest.raises(ValueError):
        existing(rep=p)


@pytest.mark.parametrize("key,value",[
    ("state","OWNER_ACKNOWLEDGED"),
    ("review_owner","finance_os"),
    ("may_send_messages",True),
    ("may_write_canonical_crm",True),
    ("may_call_external_api",True),
    ("owner_approval_required",False),
    ("sector","roofing company private email"),
])
def test_a2a_ticket_self_promotion_or_unsafe_sector_rejected(key,value):
    p=report();p["handoff_tickets"][0][key]=value
    with pytest.raises(ValueError):
        existing(rep=p)


def test_duplicate_original_a2a_ticket_is_rejected():
    p=report();p["handoff_tickets"][1]["ticket_id"]=p["handoff_tickets"][0]["ticket_id"]
    with pytest.raises(ValueError):
        existing(rep=p)


@pytest.mark.parametrize("key,value",[
    ("outbound_authority",True),
    ("money_movement_authority",True),
    ("purchase_intent_verified_by_this_protocol",True),
    ("buyer_qualified_by_this_protocol",True),
    ("buyer_identity_verified_by_this_protocol",True),
    ("owner_task_dispatches_by_this_protocol",1),
    ("prepared_research_requests",3),
])
def test_replayed_or_privilege_escalated_owner_receipt_summary_rejected(key,value):
    receipt=receipts();receipt[key]=value
    with pytest.raises(ValueError):
        existing(rcpt=receipt)


def test_owner_claimed_signed_replies_without_independent_proof_stay_research():
    receipt=receipts();receipt["authenticated_owner_replies"]=2
    receipt["owner_public_keys_configured"]=["some-claimed-key-id"]
    a=existing(rcpt=receipt)
    assert a["original_owner_authenticated_reply_count"]==2
    assert a["owner_trust_store_ready"] is False
    assert a["original_owner_receipt_state"]=="OWNER_REPORTED_RECEIPTS_NEED_INDEPENDENT_KEY_READBACK"
    assert a["source_authenticated_buyer_or_customer_order"] is False


def test_cross_department_owner_queue_preserves_original_idempotency_and_unverified_finance(tmp_path):
    req=requirement()
    supply=review_original_lead_readiness(
        *source_packets(),as_of=NOW,
        industry=req["industry"],country=req["country"],
        state=req["state"],city=req["city"],
    )
    plan=plan_commercial_fulfilment(req,supply,as_of=NOW)
    finance=review_finance_source_readiness(tmp_path,as_of=NOW)
    a=existing(req=req)
    report=review_department_owner_pickup(req,plan,supply,finance,a)
    assert report["status"]=="COMMERCIAL_CROSS_OWNER_RESEARCH_PLAN_BLOCKED_PENDING_EVIDENCE"
    assert report["handoff_draft_count"]==8
    assert report["owner_handoffs_dispatched"]==0
    assert report["finance_independent_evidence_gaps_remaining"]==7
    assert report["lead_supply_global_sellable_count_not_market_inventory"]==0
    assert report["original_market_eligible_lead_inventory"] is None
    assert report["existing_a2a_matching_research_tickets_not_customer_acks"]==2
    tickets=report["owner_required_action_queue"]
    assert len({v["original_draft_idempotency_key"] for v in tickets})==8
    assert [a["owner"] for a in tickets]==[
        a["owner"] for a in plan["owner_handoffs_prepared_not_dispatched"]]
    assert all(t["original_cryptographic_owner_acknowledgement"] is None
               and t["live_service_execution_eligible"] is False for t in tickets)
    assert report["commercial_revenue_recognized_minor"] is None
    assert report["database_writes"] is False


def test_nonphysical_agency_request_does_not_require_supplier_purchase(tmp_path):
    req=requirement(industry="agency",country="GB",state="LON",
                    city="London",currency="GBP",qty=15)
    supply=review_original_lead_readiness(
        *source_packets(),as_of=NOW,industry="agency",
        country="GB",state="LON",city="London",
    )
    plan=plan_commercial_fulfilment(req,supply,as_of=NOW)
    out=review_department_owner_pickup(
        req,plan,supply,review_finance_source_readiness(tmp_path,as_of=NOW),
        existing(req=req),
    )
    proc=next(item for item in out["owner_required_action_queue"]
              if item["owner"]=="procurement_supply_intelligence")
    assert proc["operational_state"]=="NO_PHYSICAL_MATERIAL_RFQ_REQUIRED"
    assert proc["owner_required_original_proof"]=="NOT_APPLICABLE"
    assert proc["review_prepared_not_dispatched"] is False
    assert out["owner_handoffs_dispatched"]==0


def test_wrong_original_requirement_revision_or_market_cannot_reuse_owner_validation(tmp_path):
    req=requirement()
    supply=review_original_lead_readiness(
        *source_packets(),as_of=NOW,industry="roofing",
        country="US",state="FL",city="Tampa",
    )
    plan=plan_commercial_fulfilment(req,supply,as_of=NOW)
    finance=review_finance_source_readiness(tmp_path,as_of=NOW)
    a=existing(req=req)
    bad=deepcopy(a);bad["reviewed_original_requirement_revision_sha256"]=H("different")
    with pytest.raises(ValueError):
        review_department_owner_pickup(req,plan,supply,finance,bad)
    bad=deepcopy(plan)
    bad["owner_handoffs_prepared_not_dispatched"][0]["task_dispatched"]=True
    with pytest.raises(ValueError):
        review_department_owner_pickup(req,bad,supply,finance,a)


def test_missing_a2a_source_files_are_not_mock_owner_replies(tmp_path):
    r=read_existing_a2a_owner_reports(tmp_path,requirement=requirement(),as_of=NOW)
    assert r["status"]=="ORIGINAL_A2A_OWNER_RESEARCH_UNAVAILABLE"
    assert r["original_owner_dispatch_receipt"] is None


def test_owner_packet_symlink_is_not_followed(tmp_path):
    p=tmp_path/"runtime/a2a_commercial_signal_mining"
    p.mkdir(parents=True)
    outside=tmp_path/"outside.json"
    outside.write_text(json.dumps(report()))
    (p/"buyer_owner_research_handoffs_v1.json").symlink_to(outside)
    r=read_existing_a2a_owner_reports(tmp_path,requirement=requirement(),as_of=NOW)
    assert r["status"]=="ORIGINAL_A2A_OWNER_RESEARCH_UNAVAILABLE"


@pytest.mark.parametrize("counter",[
    "tasks_dispatched","messages_sent",
    "buyer_record_writes","externally_verified_new_buyers",
])
def test_boolean_cannot_spoof_original_numeric_zero_activity(counter):
    p=report()
    p[counter]=False
    with pytest.raises(ValueError):
        existing(rep=p)


def test_receipt_task_count_false_does_not_validate_as_numeric_zero():
    r=receipts()
    r["owner_task_dispatches_by_this_protocol"]=False
    with pytest.raises(ValueError):
        existing(rcpt=r)
