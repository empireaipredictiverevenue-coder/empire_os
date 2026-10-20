"""A2A first-party research is not sellable Exchange inventory."""
from copy import deepcopy
from datetime import datetime, timezone
import json

from empire_os.exchange_a2a_research_signal_bridge_v1 import (
    summarise_a2a_for_exchange,
)
from empire_os.exchange_self_serve_fulfilment_review_v1 import (
    build_exchange_self_serve_fulfilment_review,
)
from tests.exchange_snapshot_fixture_20261020 import fixture, NOW


def queue():
    return {
        "schema_version":"empire.buyer_scout.source_verification_queue.v1",
        "mode":"OBSERVE",
        "execution_authority":"NONE",
        "owner":"existing_buyer_scout",
        "ready_first_party_verification_tasks":[{
            "public_company_domain":"roofing-provider.example",
            "stable_review_task_id":"a"*24,
            "market":"tampa, fl",
            "sector":"roofing",
            "state":"OWNER_REVIEW_NOT_DELIVERED",
            "contact_allowed":False,
            "can_create_customer":False,
            "can_send_message":False,
            "commercial_claims_verified":False,
            "requires_canonical_empiredb_duplicate_and_suppression_check":True,
            "private_email":"do-not-disclose@example.com",
        }],
        "ready_first_party_verification_count":1,
        "held_site_tasks":[{
            "state":"SOURCE_HOLD_NO_RETRY_OR_PERSISTENCE",
            "contact_allowed":False,
            "private_email":"do-not-disclose-held@example.com",
        }],
        "held_site_count":1,
        "historical_official_company_context":[{
            "not_a_verified_buyer":True,
            "not_a_current_project_demand_signal":True,
            "contact_allowed":False,
            "private_name":"Confidential Name",
        }],
        "historical_official_context_count":1,
        "search_api_results_persisted":False,
        "verified_revenue_buyers":0,
        "canonical_crm_records_created":0,
        "canonical_empiredb_duplicate_checks_completed":0,
        "tasks_dispatched_to_live_buyer_scout":0,
        "outbound_messages_sent":0,
    }


def test_research_counts_do_not_inflate_inventory_mrr_or_authority():
    val=build_exchange_self_serve_fulfilment_review(
        fixture(),a2a_owner_queue=queue(),now=NOW,
    )
    a=val["a2a_research_only"]
    assert a["state"]=="OWNER_RESEARCH_COUNTS_ONLY"
    assert a["ready_company_website_review_tasks"]==1
    assert a["held_policy_or_source_sites"]==1
    assert a["historical_permit_company_hypotheses"]==1
    assert a["counts_count_as_canonical_inventory"] is False
    assert a["freshness_not_proven_by_queue_alone"] is True
    assert val["canonical_inventory"]["canonical_selected_research_inventory"]==4
    assert val["canonical_inventory"]["delivery_ready_now"]==0
    assert val["recognized_mrr_cents"]==0
    assert val["lead_delivery_authorized"] is False
    text=json.dumps(val)
    assert "do-not-disclose" not in text
    assert "Confidential Name" not in text
    assert "roofing-provider.example" not in text


def test_missing_queue_holds_only_research_section():
    val=build_exchange_self_serve_fulfilment_review(fixture(),now=NOW)
    assert val["a2a_research_only"]["state"]=="HOLD"
    assert val["state"]=="OPERATOR_REVIEW_ONLY"


def test_duplicate_company_and_spoofed_sales_fails_closed():
    for changed in ("duplicate","fake_lead","fake_authority","bad_held","permit_sale"):
        q=queue()
        if changed=="duplicate":
            q["ready_first_party_verification_tasks"].append(
                deepcopy(q["ready_first_party_verification_tasks"][0])
            )
            q["ready_first_party_verification_count"]=2
        elif changed=="fake_lead":
            q["ready_first_party_verification_tasks"][0]["can_send_message"]=True
        elif changed=="fake_authority":
            q["canonical_crm_records_created"]=1
        elif changed=="bad_held":
            q["held_site_tasks"][0]["state"]="READY_FOR_CONTACT"
        else:
            q["historical_official_company_context"][0]["not_a_verified_buyer"]=False
        result=summarise_a2a_for_exchange(q)
        assert result["state"]=="HOLD",changed
        assert result["buyer_capacity_added"]==0
        assert result["approved_buyer_deliveries"]==0
        assert result["revenue_added_cents"]==0


def test_brave_search_result_persistence_disallowed():
    q=queue()
    q["search_api_results_persisted"]=True
    result=summarise_a2a_for_exchange(q)
    assert result["state"]=="HOLD"
    assert result["saleable_personal_leads_added"]==0
