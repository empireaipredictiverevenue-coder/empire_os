"""BLS monthly price-index source review and hypothetical cost scenario safety."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json

import pytest

from empire_os.predictive_bls_cost_index import (
    review_bls_cost_index_owner,
    propose_bls_hypothetical_material_cost_stress,
)
NOW=datetime(2026,10,20,12,tzinfo=timezone.utc)
SERIES="PCU327320327320"  # public BLS format; offline values below are FICTIONAL.
WAGE="CIU2010000000000I"  # synthetic fixture ID, not an authenticated catalog match.


def point(year,month,value,*,preliminary=False):
    return {
        "year":str(year),"period":f"M{month:02d}",
        "periodName":"Synthetic month",
        "value":str(value),
        "footnotes":[{"code":"P","text":"Preliminary"}] if preliminary else [],
    }


def owner(*,wage=False):
    m=[
        {
            "series_id":SERIES,"economic_role":"producer_output_price_index",
            "source_country":"US","geographic_scope":"national_or_series_defined",
            "frequency":"monthly","unit":"index_not_currency",
            "seasonal_adjustment":"not_seasonally_adjusted",
            "owner_category_reviewed":True,
        }
    ]
    s=[{"seriesID":SERIES,"data":[
        point(2026,8,110,preliminary=True),
        point(2025,8,100),
        point(2026,7,109),
    ]}]
    if wage:
        m.append({**m[0],"series_id":WAGE,"economic_role":"wage_related_index"})
        s.append({"seriesID":WAGE,"data":[
            point(2026,8,150),point(2025,8,148),
        ]})
    return {
        "schema_version":"empire.economic_sources.bls_owner_review.v1",
        "mode":"OBSERVE","execution_authority":"none",
        "source_publisher":"U.S. Bureau of Labor Statistics",
        "official_api_endpoint":"https://api.bls.gov/publicAPI/v2/timeseries/data/",
        "data_rights_scope":"INTERNAL_ECONOMIC_RESEARCH",
        "raw_job_supplier_quotes_included":False,
        "raw_personal_wage_records_included":False,
        "consumer_outreach_authorized":False,
        "price_quote_or_sale_verified":False,
        "generated_at":NOW.isoformat(),
        "approved_series_manifest":m,
        "bls_api_response":{
            "status":"REQUEST_SUCCEEDED","message":[],
            "Results":{"series":s},
        },
    }


def review(packet=None,*,now=NOW):
    return review_bls_cost_index_owner(packet if packet is not None else owner(),as_of=now)


def test_source_yoy_is_index_movement_and_not_job_level_cost():
    out=review()
    assert out["status"]=="BLS_OFFICIAL_INDEX_RESEARCH_REVIEWED"
    assert out["series_observation_count"]==1
    assert out["source_revision_sha256"] and len(out["source_revision_sha256"])==64
    card=out["series_research_cards"][0]
    assert card["original_public_series_id"]==SERIES
    assert card["latest_observed_month"]=="2026-08"
    assert card["latest_published_index_value_not_currency"]=="110"
    assert card["same_month_prior_year_index_value_not_currency"]=="100"
    assert card["year_over_year_index_change_pct_research_only"]==10.0
    assert card["any_source_preliminary_footnotes"] is True
    assert card["original_periods_examined"]==3
    assert card["scenario_value_applied_automatically"] is False
    assert out["index_is_a_specific_supplier_invoice"] is False
    assert out["national_index_is_exact_territory_price"] is False
    assert out["original_source_publisher_authenticated_independently"] is False
    assert out["realized_profit_verified"] is False
    assert out["external_fetch_or_paid_query_performed"] is False
    assert out["database_writes"] is False


def test_explicit_hypothetical_cost_pass_through_not_price_or_profit():
    out=propose_bls_hypothetical_material_cost_stress(
        review(),series_id=SERIES,assumed_cost_exposure_share=0.4,
        assumed_price_change_pass_through_fraction=0.75,
    )
    assert out["status"]=="HYPOTHETICAL_COST_STRESS_PROPOSAL_ONLY"
    assert out["hypothetical_fulfilment_cost_multiplier"]==1.03
    assert out["existing_twin_driver_type"]=="material_cost"
    assert out["economic_twin_recalculated"] is False
    assert out["scenario_revenue_or_profit_authenticated"] is False
    assert out["original_company_cost_baseline_authenticated"] is False
    assert out["cost_shock_applied_to_production"] is False
    assert out["database_writes"] is False


def test_wages_cannot_be_reinterpreted_as_material_cost_or_capacity():
    result=review(owner(wage=True))
    assert result["series_observation_count"]==2
    wage_card=next(x for x in result["series_research_cards"]
                   if x["original_public_series_id"]==WAGE)
    assert wage_card["proposed_existing_twin_driver"] is None
    assert wage_card["index_movement_is_verified_local_wage_change"] is False
    with pytest.raises(ValueError):
        propose_bls_hypothetical_material_cost_stress(
            result,series_id=WAGE,assumed_cost_exposure_share=0.2,
            assumed_price_change_pass_through_fraction=0.5,
        )


def test_absence_of_yoy_is_null_not_zero_growth():
    p=owner()
    p["bls_api_response"]["Results"]["series"][0]["data"]=[
        point(2026,8,109),point(2026,7,108),
    ]
    out=review(p)
    card=out["series_research_cards"][0]
    assert card["year_over_year_index_change_pct_research_only"] is None
    assert card["source_original_period_missing_yoy"] is True
    with pytest.raises(ValueError):
        propose_bls_hypothetical_material_cost_stress(
            out,series_id=SERIES,assumed_cost_exposure_share=1,
            assumed_price_change_pass_through_fraction=1,
        )


def test_negative_yoy_is_not_negative_price():
    p=owner()
    p["bls_api_response"]["Results"]["series"][0]["data"][0]["value"]="90"
    out=review(p)
    assert out["series_research_cards"][0]["year_over_year_index_change_pct_research_only"]==-10
    whatif=propose_bls_hypothetical_material_cost_stress(
        out,series_id=SERIES,assumed_cost_exposure_share=0.5,
        assumed_price_change_pass_through_fraction=1,
    )
    assert whatif["hypothetical_fulfilment_cost_multiplier"]==0.95


def test_data_revisions_change_source_fingerprint():
    p=owner()
    original=review(p)
    p["bls_api_response"]["Results"]["series"][0]["data"][0]["value"]="111"
    revised=review(p)
    assert original["source_revision_sha256"]!=revised["source_revision_sha256"]
    assert revised["series_research_cards"][0]["year_over_year_index_change_pct_research_only"]==11


def test_one_bls_series_duplicate_or_missing_is_held():
    p=owner()
    p["bls_api_response"]["Results"]["series"].append(
        deepcopy(p["bls_api_response"]["Results"]["series"][0]))
    assert review(p)["status"]=="BLS_API_SERIES_COVERAGE_HOLD"
    p=owner(wage=True)
    p["bls_api_response"]["Results"]["series"][1]["seriesID"]=SERIES
    assert review(p)["status"]=="BLS_SOURCE_VALUE_OR_PERIOD_HOLD"


@pytest.mark.parametrize("field,value",[
    ("source_publisher","Fake Data Dealer"),
    ("official_api_endpoint","https://evil.example.org/producer"),
    ("data_rights_scope","RAW_RESALE_ALLOWED"),
    ("raw_job_supplier_quotes_included",True),
    ("raw_personal_wage_records_included",True),
    ("consumer_outreach_authorized",True),
    ("price_quote_or_sale_verified",True),
    ("execution_authority","spend"),
    ("mode","ACT"),
])
def test_owner_cannot_spoof_external_authority(field,value):
    p=owner()
    p[field]=value
    result=review(p)
    assert result["status"]=="BLS_OWNER_SOURCE_CONTRACT_HOLD"
    assert result["series_observation_count"] is None


def test_stale_owner_snapshot_and_future_owner_clock_hold():
    p=owner()
    assert review(p,now=NOW+timedelta(days=5))["status"]=="BLS_SOURCE_STALE_OR_FUTURE_HOLD"
    p["generated_at"]=(NOW+timedelta(minutes=1)).isoformat()
    assert review(p)["status"]=="BLS_SOURCE_STALE_OR_FUTURE_HOLD"


@pytest.mark.parametrize("field,value",[
    ("series_id","id?bad"),
    ("series_id","private@company.example"),
    ("economic_role","invoice_price_paid"),
    ("unit","USD_per_hour"),
    ("source_country","GB"),
    ("frequency","annual"),
    ("owner_category_reviewed",False),
    ("geographic_scope","Little Rock actual quotes"),
])
def test_missing_original_owner_series_semantics_holds(field,value):
    p=owner()
    p["approved_series_manifest"][0][field]=value
    assert review(p)["status"]=="BLS_SOURCE_VALUE_OR_PERIOD_HOLD"


@pytest.mark.parametrize("value",[
    "-2","0","inf","NaN","$100","4,500","10000001","0.0000001",True,None,
])
def test_malformed_bls_index_must_not_enter_model(value):
    p=owner()
    p["bls_api_response"]["Results"]["series"][0]["data"][0]["value"]=value
    assert review(p)["status"]=="BLS_SOURCE_VALUE_OR_PERIOD_HOLD"


@pytest.mark.parametrize("year,month",[(2030,8),(2026,11),(2026,13),(2026,0)])
def test_future_or_impossible_period_never_promoted(year,month):
    p=owner()
    p["bls_api_response"]["Results"]["series"][0]["data"][0]["year"]=str(year)
    p["bls_api_response"]["Results"]["series"][0]["data"][0]["period"]=f"M{month:02}"
    assert review(p)["status"]=="BLS_SOURCE_VALUE_OR_PERIOD_HOLD"


def test_a_stale_bls_data_month_not_fixed_by_new_fetch_timestamp():
    p=owner()
    p["bls_api_response"]["Results"]["series"][0]["data"]=[
        point(2025,1,130),point(2024,1,110),
    ]
    assert review(p)["status"]=="BLS_SOURCE_VALUE_OR_PERIOD_HOLD"


def test_bls_api_success_with_warning_is_not_accepted():
    p=owner()
    p["bls_api_response"]["message"]=["Invalid Series for Series PCUX!"]
    assert review(p)["status"]=="BLS_API_OR_MANIFEST_HOLD"


@pytest.mark.parametrize("share,pass_through",[
    (1.01,1),(0.5,-0.1),(True,0.5),(0.5,float("nan")),
    (float("inf"),0.5),("1",0.5),
])
def test_hypothetical_assumptions_must_be_bounded_numeric(share,pass_through):
    with pytest.raises(ValueError):
        propose_bls_hypothetical_material_cost_stress(
            review(),series_id=SERIES,
            assumed_cost_exposure_share=share,
            assumed_price_change_pass_through_fraction=pass_through,
        )


def test_empty_input_unknown_not_zero_sources():
    x=review_bls_cost_index_owner(None,as_of=NOW)
    assert x["status"]=="BLS_OWNER_SOURCE_NOT_CONNECTED"
    assert x["series_observation_count"] is None
    assert x["series_research_cards"]==[]
    assert x["actual_material_or_labor_cost_authenticated"] is False


def twin():
    from test_predictive_market_economic_twin import market,driver
    from test_predictive_profitability_playbooks import pilot,plan
    from empire_os.predictive_market_economic_twin import review_market_economic_twin
    p=pilot()
    return review_market_economic_twin(
        p,plan(p),market(),[driver()],as_of=NOW,
    )


def test_source_revision_links_to_original_economic_twin_without_applying_shock():
    from empire_os.predictive_bls_cost_index import bind_bls_cost_stress_to_existing_twin
    bls=review()
    assumption=propose_bls_hypothetical_material_cost_stress(
        bls,series_id=SERIES,assumed_cost_exposure_share=0.4,
        assumed_price_change_pass_through_fraction=0.75,
    )
    result=bind_bls_cost_stress_to_existing_twin(bls,assumption,twin())
    assert result["status"]=="BLS_TO_MARKET_TWIN_RESEARCH_LINK_ONLY"
    assert result["original_bls_source_revision_sha256"]==bls["source_revision_sha256"]
    assert result["hypothetical_fulfilment_cost_multiplier"]==1.03
    assert result["bls_national_series_is_exact_market_geography"] is False
    assert result["source_cost_stress_executed"] is False
    assert result["original_customer_unit_cost_verified"] is False
    assert result["scenario_expected_profit_delta_computed_by_this_link"] is None
    assert result["execution_authority"]=="none"


def test_forged_source_stress_multiplier_cannot_be_promoted_into_twin():
    from empire_os.predictive_bls_cost_index import bind_bls_cost_stress_to_existing_twin
    bls=review()
    assumption=propose_bls_hypothetical_material_cost_stress(
        bls,series_id=SERIES,assumed_cost_exposure_share=0.4,
        assumed_price_change_pass_through_fraction=0.75,
    )
    assumption["hypothetical_fulfilment_cost_multiplier"]=3.0
    with pytest.raises(ValueError):
        bind_bls_cost_stress_to_existing_twin(bls,assumption,twin())


def test_stress_from_previous_bls_revision_cannot_link_to_new_revision():
    from empire_os.predictive_bls_cost_index import bind_bls_cost_stress_to_existing_twin
    old=review()
    assumption=propose_bls_hypothetical_material_cost_stress(
        old,series_id=SERIES,assumed_cost_exposure_share=0.4,
        assumed_price_change_pass_through_fraction=0.75,
    )
    packet=owner()
    packet["bls_api_response"]["Results"]["series"][0]["data"][0]["value"]="112"
    changed=review(packet)
    with pytest.raises(ValueError):
        bind_bls_cost_stress_to_existing_twin(changed,assumption,twin())


def test_twin_claiming_real_market_authentication_holds():
    from empire_os.predictive_bls_cost_index import bind_bls_cost_stress_to_existing_twin
    bls=review()
    assumption=propose_bls_hypothetical_material_cost_stress(
        bls,series_id=SERIES,assumed_cost_exposure_share=0.4,
        assumed_price_change_pass_through_fraction=0.75,
    )
    t=twin()
    t["source_market_conditions_authenticated"]=True
    with pytest.raises(ValueError):
        bind_bls_cost_stress_to_existing_twin(bls,assumption,t)
