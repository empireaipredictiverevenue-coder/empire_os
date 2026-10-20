"""Non-Tampa commercial requests must drive the same governed cross-owner paths.

All upstream snapshot fixtures are synthetic; outputs are explicitly research
counts and no legitimate customer order, inventory or margin is fabricated.
"""
from copy import deepcopy
import json

import pytest

from test_predictive_commercial_requirements_fulfilment import (
    NOW,source_packets,
)
from empire_os.predictive_commercial_requirements import (
    review_commercial_requirement,tampa_roofing_founder_example,
)
from empire_os.predictive_commercial_supply_readiness import review_original_lead_readiness
from empire_os.predictive_commercial_fulfilment import plan_commercial_fulfilment


def run(*,country,state,city,industry,target,currency,postal=None,source=None):
    raw=tampa_roofing_founder_example()
    raw.update(
        country=country,state=state,city=city,industry=industry,
        currency=currency,zip_codes=list(postal or []),
        requested_qualified_leads=target,
        service_types=["original_service_scope"],
    )
    req=review_commercial_requirement(raw,as_of=NOW)
    research=review_original_lead_readiness(
        *(source or source_packets()),as_of=NOW,
        industry=industry,country=country,state=state,city=city,
    )
    decision=plan_commercial_fulfilment(req,research,as_of=NOW)
    return req,research,decision


@pytest.mark.parametrize("country,state,city,industry,target,currency,postal,known",[
    ("US","AZ","Phoenix","hvac",30,"USD",["85001"],34),
    ("US","TX","Austin","solar",25,"USD",["78701"],9),
    ("US","NY","New York","construction",12,"USD",["10001"],None),
    ("US","CA","Los Angeles","insurance",40,"USD",["90001"],None),
    ("GB","LON","London","agency",15,"GBP",["SW1A 1AA"],None),
    ("CA","ON","Toronto","professional_services",8,"CAD",["M5V 2T6"],None),
    ("AU","NSW","Sydney","software",22,"AUD",["2000"],None),
    ("DE","BE","Berlin","data_brokerage",18,"EUR",["10115"],None),
    ("IN","KA","Bengaluru","other",60,"INR",["560001"],None),
])
def test_customer_industry_country_market_and_quantity_drive_research(
    country,state,city,industry,target,currency,postal,known,
):
    req,supply,plan=run(country=country,state=state,city=city,industry=industry,
                        target=target,currency=currency,postal=postal)
    assert req["industry"]==industry and plan["industry"]==industry
    assert req["country"]==country and plan["country"]==country
    assert req["city"]==city and plan["city"]==city
    assert plan["customer_requested_qualified_leads"]==target
    assert req["source_instruction_kind"]=="FOUNDER_OR_CUSTOMER_UNVERIFIED_REQUIREMENT_DRAFT"
    assert supply["research_target_industry"]==industry
    assert supply["research_target_market_country"]==country
    assert supply["source_target_industry_research_records_not_leads"]==known
    assert plan["source_target_industry_research_records_not_deliverable_leads"]==known
    assert plan["source_roofing_research_records_not_deliverable_leads"] is None
    assert supply["original_source_roofing_research_records_not_leads"] is None
    assert supply["verified_target_market_eligible_leads"] is None
    assert supply["verified_target_market_available_inventory"] is None
    assert plan["verified_target_market_inventory_units"] is None
    assert plan["verified_market_and_customer_eligible_leads"] is None
    assert plan["requested_target_is_verified_available"] is False
    assert plan["verified_fulfilment_gap_units"] is None
    assert plan["forecasted_recoverable_margin_minor"] is None
    assert plan["owner_handoff_delivery_receipts"]==0
    assert all(t["target_city"]==city and t["target_industry"]==industry
               and not t["task_dispatched"] for t in plan["owner_handoffs_prepared_not_dispatched"])
    assert plan["cloud_scenario_capacity_review"]["verified_target_market_selling_inventory"] is None
    assert plan["database_writes"] is False and plan["outbound_sent"] is False


@pytest.mark.parametrize("industry,expected",[
    ("roofing","roof_covering_system"),
    ("hvac","equipment_system"),
    ("solar","pv_module_system"),
    ("construction","project_specific_material_specification"),
])
def test_material_procurement_scope_tracks_industry(industry,expected):
    req,_,plan=run(country="US",state="TX",city="Houston",
                   industry=industry,target=4,currency="USD")
    scope=plan["supplier_sourcing_preflight"]
    assert expected in scope["materials_to_scope_not_purchase_quantities"]
    assert scope["status"]=="PRELIMINARY_RFQ_REQUIREMENTS_NO_PURCHASE_READY_BOM"
    assert req["physical_material_procurement_applicable"] is True
    assert scope["sourcing_ready_for_purchase"] is False
    assert scope["source_owner_quote_count"]==0


@pytest.mark.parametrize("industry",[
    "insurance","agency","data_brokerage","professional_services","software",
])
def test_non_material_industries_do_not_create_phantom_roof_supplier_needs(industry):
    req,_,plan=run(country="US",state="CA",city="Sacramento",
                   industry=industry,target=7,currency="USD")
    scope=plan["supplier_sourcing_preflight"]
    assert req["physical_material_procurement_applicable"] is False
    assert scope["status"]=="NOT_APPLICABLE_NO_PHYSICAL_MATERIALS_REQUEST"
    assert scope["materials_to_scope_not_purchase_quantities"]==[]
    assert scope["purchase_orders_issued"] is False
    assert "PROJECT_MEASUREMENTS_MATERIALS_AND_CODE_SPEC" not in req["required_owner_questions"]


def test_readiness_refuses_to_join_new_market_and_old_industry():
    req,readiness,_=run(country="US",state="TX",city="Houston",
                        industry="solar",target=25,currency="USD")
    incorrect=deepcopy(readiness)
    incorrect["research_target_market_city"]="Tampa"
    with pytest.raises(ValueError,match="market/industry mismatched"):
        plan_commercial_fulfilment(req,incorrect,as_of=NOW)
    incorrect=deepcopy(readiness)
    incorrect["research_target_industry"]="roofing"
    with pytest.raises(ValueError,match="market/industry mismatched"):
        plan_commercial_fulfilment(req,incorrect,as_of=NOW)


def test_request_changes_deduplicate_by_full_market_not_shared_lead_target():
    a,*_=run(country="US",state="AZ",city="Phoenix",industry="hvac",target=30,currency="USD")
    b,*_=run(country="US",state="FL",city="Tampa",industry="roofing",target=30,currency="USD")
    c,*_=run(country="GB",state="LON",city="London",industry="agency",target=30,currency="GBP")
    assert len({a["draft_idempotency_key"],b["draft_idempotency_key"],c["draft_idempotency_key"]})==3


@pytest.mark.parametrize("change,value",[
    ("country","ZZ"),("currency","FAKE"),("state","!!"),("city","123 street"),
    ("zip_codes",["PRIVATE_STREET_ADDRESS"]),
    ("requested_qualified_leads",True),
])
def test_unverified_localities_and_false_lead_quantities_rejected(change,value):
    raw=tampa_roofing_founder_example()
    raw[change]=value
    with pytest.raises(ValueError):
        review_commercial_requirement(raw,as_of=NOW)


def test_cross_sector_research_absence_does_not_corrupt_global_readiness():
    sources=list(source_packets())
    sources[0]["observed_supply_by_vertical_not_buyer_mapped"].pop("solar")
    req,supply,plan=run(country="US",state="TX",city="Houston",
                        industry="solar",target=25,currency="USD",source=tuple(sources))
    assert supply["source_lead_supply_status"]=="FRESH_RESEARCH_COUNTS_NOT_DELIVERABLE_INVENTORY"
    assert supply["source_target_industry_bucket_present"] is False
    assert supply["source_target_industry_research_records_not_leads"] is None
    assert supply["global_immediately_sellable_inventory"]==0
    assert plan["verified_market_and_customer_eligible_leads"] is None
