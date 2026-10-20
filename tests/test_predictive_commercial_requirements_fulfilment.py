"""Requirement/Tampa lead inventory/roofing RFQ/A2A/Cloud source contracts."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json

import pytest

from empire_os.predictive_commercial_requirements import (
    tampa_roofing_founder_example,review_commercial_requirement,
)
from empire_os.predictive_commercial_supply_readiness import (
    review_original_lead_readiness,review_lead_readiness_runtime,
)
from empire_os.predictive_commercial_fulfilment import (
    plan_commercial_fulfilment,review_roofing_procurement,
    prepare_owner_handoffs,review_cloud_commercial_research,
)

NOW=datetime(2026,10,20,13,tzinfo=timezone.utc)
H=lambda s:sha256(s.encode()).hexdigest()


def requirement(data=None):
    return review_commercial_requirement(
        data if data is not None else tampa_roofing_founder_example(),as_of=NOW,
    )


def source_packets():
    supply={
        "schema_version":"empire.leadgen_revenue_activation_queue.v1",
        "mode":"READ_ONLY_PRIVATE_LEADGEN","execution_authority":"none",
        "canonical_empiredb_writes":False,"buyer_outreach_authorized":False,
        "prospect_insert_authorized":False,"generated_at":NOW.isoformat(),
        "observed_supply_by_vertical_not_buyer_mapped":{
            "hvac":34,"roofing":56,"solar":9,"plumbing":21},
        "immediately_sellable_inventory":0,"canonical_selected_inventory_records":175,
        "canonical_capacity_waitlist_records":91,
        "qualified_buyers":0,"verified_buyer_capacity":0,
        "territory_matching_performed":False,
    }
    buyer={
        "schema_version":"empire.buyer_capacity_readiness.v1",
        "mode":"OBSERVE","execution_authority":"none",
        "allocation_executed":False,"payment_action":False,
        "observed_at":NOW.isoformat(),"buyers_seen":1057,
        "capacity_verified":0,"terms_verified":0,"fully_activated":0,
        "allocation_ready":False,
    }
    scout={
        "schema_version":"empire.buyer_acquisition_scout.v1",
        "mode":"OBSERVE","execution_authority":"none",
        "outbound_sent":False,"database_write_performed":False,
        "actual_revenue":False,"generated_at":NOW.isoformat(),"candidate_count":11,
    }
    return supply,buyer,scout


def readiness(sources=None, *, intake=None):
    r=requirement(intake)
    return review_original_lead_readiness(
        *(sources or source_packets()),as_of=NOW,
        industry=r["industry"],country=r["country"],
        state=r["state"],city=r["city"],
    )


def plan(*,intake=None,sources=None,roof=None,quotes=None,cloud=None):
    return plan_commercial_fulfilment(
        requirement(intake),readiness(sources,intake=intake),as_of=NOW,
        original_roof_project=roof,supplier_owner_quotes=quotes,
        hypothetical_cloud=cloud,
    )


def test_tampa_target_20_is_never_counted_as_delivered_or_reserved():
    req=requirement()
    assert req["status"]=="COMMERCIAL_REQUIREMENT_INCOMPLETE"
    assert req["requested_qualified_leads_target_not_inventory"]==20
    assert req["verified_deliverable_lead_count"] is None
    assert req["source_customer_order_authenticated"] is False
    assert req["tenant_scope_verified"] is False
    assert "CONTRACTED_BUDGET_AND_ACCEPTED_LEAD_PRICE" in req["required_owner_questions"]
    assert "EXACT_SERVICE_ZIP_TERRITORY" in req["required_owner_questions"]
    assert "CONSENT_COMPLIANCE_PROOF_ORIGINAL_OWNER" in req["required_owner_questions"]
    assert req["source_entered_zip_codes"]==[]
    assert req["source_entered_unit_price_minor"] is None
    assert req["procurement_authorized"] is False
    assert req["marketing_budget_authorized"] is False


def test_idempotent_research_tickets_same_revision_replay_is_not_two_tasks():
    a=requirement()
    b=requirement()
    assert a["requirement_revision_sha256"]==b["requirement_revision_sha256"]
    tickets_a=prepare_owner_handoffs(a); tickets_b=prepare_owner_handoffs(b)
    assert len(tickets_a)==8
    assert [t["idempotency_key"] for t in tickets_a]==[
        t["idempotency_key"] for t in tickets_b]
    assert len({t["idempotency_key"] for t in tickets_a})==8
    assert all(t["status"]=="PREPARED_NOT_DELIVERED" and
               t["task_dispatched"] is False and
               t["replay_protection_persisted"] is False and
               t["source_tenant_authentication_verified"] is False
               for t in tickets_a)


def test_changed_customer_quantity_gets_new_draft_revision_not_duplicate():
    original=tampa_roofing_founder_example()
    newer=deepcopy(original)
    newer["requested_qualified_leads"]=30
    assert requirement(original)["requirement_revision_sha256"]!=(
        requirement(newer)["requirement_revision_sha256"])


def test_no_verified_tampa_specific_inventory_can_be_inferred_from_56_roof_records():
    s=readiness()
    assert s["source_lead_supply_status"]=="FRESH_RESEARCH_COUNTS_NOT_DELIVERABLE_INVENTORY"
    assert s["global_immediately_sellable_inventory"]==0
    assert s["original_source_roofing_research_records_not_leads"]==56
    assert s["canonical_selected_records_not_accepted_consumer_leads"]==175
    assert s["original_buyer_records_reviewed_not_approved"]==1057
    assert s["verified_global_buyer_capacity_count"]==0
    assert s["buyer_identity_candidates_not_committed_buyers"]==11
    assert s["verified_tampa_eligible_leads"] is None
    assert s["available_to_commit_tampa_units"] is None
    assert s["zero_source_sellable_records_proves_no_regional_demand"] is False
    assert s["territory_match_proven"] is False


def test_lead_snapshot_stale_does_not_get_zero_filled_or_called_current():
    a,b,c=source_packets()
    a["generated_at"]=(NOW-timedelta(days=5)).isoformat()
    s=readiness((a,b,c))
    assert s["source_lead_supply_status"]=="OWNER_SOURCE_STALE_OR_AUTHORITY_HOLD"
    assert s["global_immediately_sellable_inventory"] is None
    assert s["original_source_roofing_research_records_not_leads"] is None


@pytest.mark.parametrize("index,key,value",[
    (0,"immediately_sellable_inventory",True),
    (0,"immediately_sellable_inventory",-3),
    (0,"canonical_empiredb_writes",True),
    (0,"buyer_outreach_authorized",True),
    (0,"territory_matching_performed",True),
    (1,"capacity_verified",True),
    (1,"capacity_verified",-1),
    (1,"allocation_ready",True),
    (1,"payment_action",True),
    (2,"outbound_sent",True),
    (2,"database_write_performed",True),
    (2,"actual_revenue",True),
])
def test_owner_forged_inventory_capacity_or_outreach_blocked(index,key,value):
    sources=list(source_packets())
    sources[index][key]=value
    s=readiness(tuple(sources))
    status={
        0:"source_lead_supply_status",1:"source_buyer_capacity_status",
        2:"source_buyer_scout_status",
    }[index]
    assert s[status]=="OWNER_SOURCE_STALE_OR_AUTHORITY_HOLD"


@pytest.mark.parametrize("key,value",[
    ("requested_qualified_leads",True),
    ("requested_qualified_leads",0),
    ("requested_qualified_leads",-20),
    ("company_authorization_owner_receipt",{"verified":True}),
    ("permission_proof_owner_receipt","approved"),
    ("buyer_capacity_verified_units",20),
    ("price_per_accepted_lead_minor",25.5),
    ("price_per_accepted_lead_minor",True),
    ("currency","EUR"),
    ("exclusivity","guaranteed_exclusive"),
    ("accepted_event_types",["raw_scraped_social_user"]),
    ("delivery_deadline","2010-05-01T00:00:00+00:00"),
    ("zip_codes",["private_tampa_address"]),
    ("service_types",["Roof Repair 123"]),
])
def test_false_commercial_commitment_or_invalid_terms_rejected(key,value):
    x=tampa_roofing_founder_example();x[key]=value
    with pytest.raises(ValueError):
        requirement(x)


def test_cross_industry_hvac_customer_intent_contract_supported():
    x=tampa_roofing_founder_example()
    x.update(country="US",state="AZ",city="Phoenix",industry="hvac",
             requested_qualified_leads=30,
             service_types=["hvac_replacement"])
    req=requirement(x)
    assert req["industry"]=="hvac"
    assert req["city"]=="Phoenix"
    assert req["requested_qualified_leads_target_not_inventory"]==30
    assert "equipment_system" in req["material_category_research_scopes"]
    assert req["source_customer_order_authenticated"] is False


def test_uk_agency_customer_with_explicit_gbp_still_requires_buyer_proof():
    x=tampa_roofing_founder_example()
    x.update(country="GB",state="LON",city="London",industry="agency",
             currency="GBP",zip_codes=["SW1A 1AA"],
             requested_qualified_leads=12,service_types=["b2b_marketing"])
    req=requirement(x)
    assert req["country"]=="GB"
    assert req["currency"]=="GBP"
    assert req["tenant_scope_verified"] is False


def test_roof_materials_plan_never_contains_estimated_unmeasured_bom_or_quote():
    p=plan()
    assert p["status"]=="INSUFFICIENT_EVIDENCE_NOT_READY_TO_PROMISE_OR_FULFIL"
    assert p["customer_requested_qualified_leads"]==20
    assert p["verified_market_and_customer_eligible_leads"] is None
    assert p["verified_fulfilment_gap_units"] is None
    assert p["unproven_target_units_pending_review"]==20
    assert p["source_roofing_research_records_not_deliverable_leads"]==56
    assert p["current_source_global_immediately_sellable_inventory"]==0
    rfq=p["supplier_sourcing_preflight"]
    assert rfq["status"]=="PRELIMINARY_RFQ_REQUIREMENTS_NO_PURCHASE_READY_BOM"
    assert "roof_covering_system" in rfq["materials_to_scope_not_purchase_quantities"]
    assert "underlayment_waterproofing" in rfq["materials_to_scope_not_purchase_quantities"]
    assert rfq["source_owner_quote_count"]==0
    assert rfq["confirmed_comparable_landed_quote_minor"] is None
    assert rfq["material_quantities_verified"] is False
    assert rfq["purchase_orders_issued"] is False
    assert p["prepared_owner_ticket_count"]==8
    assert p["owner_handoff_delivery_receipts"]==0
    assert p["outbound_sent"] is False
    assert p["customer_commitment_authorized"] is False


def roof_scope():
    return {
        "project_ref_sha256":H("test_project"),
        "roof_measurement_ref_sha256":H("test_measurement"),
        "measured_area_m2":190,"roof_pitch_ratio":0.3,
        "system_spec_ref_sha256":H("test_spec"),
        "location_code_reviewed":False,"source_owner_authenticated":False,
    }


def quote(project="test_project",quote="one",material=100000,freight=12000,tax=2000):
    return {
        "source_owner":"existing_procurement_supply_intelligence",
        "quote_ref_sha256":H(quote),
        "supplier_ref_sha256":H("supplier_"+quote),
        "project_ref_sha256":H(project),
        "observed_at":NOW.isoformat(),"currency":"USD",
        "source_quoted_material_minor":material,
        "source_quoted_freight_minor":freight,
        "source_quoted_tax_minor":tax,"expected_delivery_days":7,
        "independent_supplier_acceptance_authenticated":False,
        "purchase_authorized":False,
    }


def test_owner_reported_supplier_quotes_ordered_but_not_authenticated_landed_cost():
    rfq=plan(roof=roof_scope(),
             quotes=[quote(quote="expensive",material=125000),quote(quote="low")])[
                 "supplier_sourcing_preflight"]
    assert rfq["source_owner_quote_count"]==2
    assert rfq["supplier_owner_claimed_quotes"][0][
        "source_reported_landed_cost_minor_unverified"]==114000
    assert rfq["confirmed_comparable_landed_quote_minor"] is None
    assert rfq["sourcing_ready_for_purchase"] is False
    assert rfq["original_measurements_independently_authenticated"] is False


@pytest.mark.parametrize("change,value",[
    ("currency","GBP"),("purchase_authorized",True),
    ("independent_supplier_acceptance_authenticated",True),
    ("project_ref_sha256",H("different_project")),
    ("source_quoted_material_minor",-4),
    ("source_quoted_material_minor",2400.5),
    ("expected_delivery_days",366),
    ("observed_at",(NOW-timedelta(days=35)).isoformat()),
])
def test_forged_quotes_wrong_project_cost_currency_staleness_refused(change,value):
    q=quote();q[change]=value
    with pytest.raises(ValueError):
        plan(roof=roof_scope(),quotes=[q])


def test_replayed_supplier_quote_identity_dedupes_by_hard_rejection():
    with pytest.raises(ValueError):
        plan(roof=roof_scope(),quotes=[quote(),deepcopy(quote())])


def test_uk_public_procurement_is_not_tampa_supplier_quote():
    q=quote();q["source_owner"]="gb_find_a_tender_ocds"
    with pytest.raises(ValueError):
        plan(roof=roof_scope(),quotes=[q])


def test_cloud_default_blocks_economic_allocation_when_no_cost_terms():
    cloud=plan()["cloud_scenario_capacity_review"]
    assert cloud["status"]=="CLOUD_SOURCE_ECONOMICS_AND_CAPACITY_MISSING"
    assert cloud["scenario_ir"] is None
    assert cloud["optimizer_executed"] is False
    assert cloud["original_profit_prediction_registered"] is False
    assert cloud["lead_allocation_or_marketing_spend_authorized"] is False
    assert cloud["verified_tampa_selling_inventory"] is None


def assumptions():
    return {
        "scenarios":[
            {"scenario_key":"research_base","probability":0.5,
             "evidence_refs":["scenario:owner_hypothesis_base"]},
            {"scenario_key":"research_downside","probability":0.5,
             "evidence_refs":["scenario:owner_hypothesis_downside"]},
        ],
        "actions":[{
            "action_key":"research_only_quote_comparison",
            "evidence_refs":["research:unverified_materials"],
            "capacity_group":"research_action",
            "scenario_values_cents":{"research_base":2000,"research_downside":-500},
            "action_cost_cents":100,
        }],
        "hypothetical_budget_minor":1000,
        "assumed_research_action_capacity":1,
        "risk_aversion":0.5,
        "original_assumptions_unverified":True,
    }


def test_existing_cloud_compiler_can_only_produce_shadow_research_ir():
    out=plan(cloud=assumptions())
    cloud=out["cloud_scenario_capacity_review"]
    assert cloud["status"]=="HYPOTHETICAL_RESEARCH_CLOUD_IR_NOT_ALLOCATION"
    assert cloud["existing_cloud_compiler_reused"] is True
    assert cloud["scenario_ir"]["schema_version"]=="empire.optimization.problem.v2"
    assert cloud["scenario_ir"]["source_schema_version"]=="empire.predictive_cloud.scenario_optimization.v1"
    assert cloud["scenario_ir"]["status"]=="AVAILABLE"
    assert cloud["scenario_ir"]["execution_authority"]=="none"
    assert cloud["scenario_probabilities_empirically_calibrated"] is False
    assert cloud["shadow_capacity_is_consent_verified_lead_delivery"] is False
    assert cloud["outcome_forecast_scenario_values_authenticated"] is False
    assert cloud["optimizer_executed"] is False
    assert cloud["payment_or_material_purchase_authorized"] is False


@pytest.mark.parametrize("key,value",[
    ("hypothetical_budget_minor",True),
    ("hypothetical_budget_minor",-100),
    ("assumed_research_action_capacity",-1),
    ("original_assumptions_unverified",False),
])
def test_cloud_cannot_pretend_unknown_budget_capacity_or_source_truth(key,value):
    src=assumptions();src[key]=value
    with pytest.raises(ValueError):
        plan(cloud=src)


def test_cloud_non_research_action_cannot_be_compiled_as_lead_delivery():
    src=assumptions();src["actions"][0]["capacity_group"]="lead_delivery"
    with pytest.raises(ValueError):
        plan(cloud=src)
