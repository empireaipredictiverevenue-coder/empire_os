"""Consumer / business product, app, service and value research: synthetic only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import pytest

from empire_os.pain_solution_engine import SOLUTION_MAP
from empire_os.predictive_customer_value_demand import (
    build_cross_market_customer_value_research_blueprint,
    compare_monthly_customer_value_scenario,
    review_customer_value_observations,
    review_existing_community_needs,
    review_existing_community_needs_runtime,
)

NOW = datetime(2026, 10, 19, 20, 45, tzinfo=timezone.utc)


def digest(s):
    return sha256(s.encode()).hexdigest()


def row(source_type="public_problem", seq=1, kind="app", job="save_admin_time",
        audience="consumer", market="united_kingdom"):
    return {
        "audience":audience,"market_key":market,"item_type":kind,
        "job_key":job,"source_type":source_type,
        "source_observed_at":(NOW-timedelta(days=2)).isoformat(),
        "origin_sha256":digest("origin"+str(seq)),
        "content_sha256":digest("content"+str(seq)),
        "reuse_scope":"INTERNAL_AGGREGATE_RESEARCH_ONLY",
    }


def review(events):
    return review_customer_value_observations(events,as_of=NOW)


def source():
    return {
        "schema_version":"empire.community_intent.v2",
        "mode":"OBSERVE", "execution_authority":"none",
        "observed_at":(NOW-timedelta(hours=1)).isoformat(),
        "pain_solution_briefs":[{
            "pain_point": pain,
            "offer_key": config["offer_key"],
            "products":list(config["products"]),
            "observed_mentions":7, "high_intent_mentions":1,
            "evidence_strength":"thin","execution_authority":"none",
            "secret_author":"alice@example.com",
            "evidence_urls":["https://reddit.com/individual-id"],
        } for pain, config in SOLUTION_MAP.items()],
    }


def scenario(**changes):
    example={
        "currency":"GBP", "minutes_before_month":900,
        "minutes_after_month":660, "cash_before_month_minor":8000,
        "cash_after_month_minor":5500,
        "solution_cost_month_minor":1500,
        "time_value_per_hour_minor":1000,
    }
    example.update(changes)
    return example


def test_four_purchase_classes_and_two_audiences_separate():
    items = [
        row("public_problem",1,"app","save_admin_time","consumer"),
        row("public_comparison",2,"app","save_admin_time","consumer"),
        row("buyer_purchase_claim",3,"app","save_admin_time","consumer"),
        row("catalog_listing",4,"product","home_maintenance","consumer"),
        row("public_problem",5,"service","roofing_help","business","united_states"),
        row("first_party_receipt_claim",6,"data_product","market_analysis","business","united_states"),
    ]
    r=review(items)
    assert r["cluster_count"]==4
    assert r["distinct_observation_receipts"]==6
    assert r["market_demand_verified"] is False
    assert r["transactions_authenticated"] is False
    assert r["covers_purchase_categories"]==["product","app","service","data_product"]
    apps=next(c for c in r["research_clusters"] if c["item_type"]=="app")
    assert apps["purchase_claim_receipts"]==1
    assert apps["verified_purchase_count"] is None
    assert apps["paying_demand_or_spend_authenticated"] is False
    assert apps["research_triage_is_purchase_probability"] is False
    assert apps["next_action"]=="VERIFY_FIRST_PARTY_PURCHASES_RETURNS_AND_UNIT_ECONOMICS"
    assert digest("origin1") not in json.dumps(r)
    assert digest("content1") not in json.dumps(r)
    assert all("content_sha256" not in item for item in r["research_clusters"])


def test_same_origin_republished_does_not_multiply_buyers_or_purchase_claim():
    events=[
        row("public_problem",1),
        row("public_comparison",1),
        row("buyer_purchase_claim",2),
        row("first_party_receipt_claim",2),
    ]
    r=review(events)
    assert r["distinct_observation_receipts"]==2
    assert r["deduplicated_event_count"]==2
    assert r["research_clusters"][0]["purchase_claim_receipts"]==1
    assert r["cross_segment_source_origins_are_independent_people"] is False


def test_marketing_catalogue_and_search_interest_not_purchase():
    r=review([
        row("seller_marketing",1,kind="product"),
        row("catalog_listing",2,kind="product"),
        row("public_search",3,kind="product"),
    ])
    x=r["research_clusters"][0]
    assert x["purchase_claim_receipts"]==0
    assert x["verified_sold_units"] is None
    assert x["market_share_estimate"] is None
    assert x["next_action"]=="FIND_INDEPENDENT_PROBLEM_AND_PURCHASE_EVIDENCE"


@pytest.mark.parametrize("field,value",[
    ("reuse_scope","PERMISSION_TO_SEND"),
    ("source_type","verified_purchase"),
    ("market_key","bob@email"),
    ("audience","unknown"),
    ("item_type","credit_card"),
    ("origin_sha256","forged"),
    ("source_observed_at","2026-10-19T12:00:00"),
    ("source_observed_at",(NOW+timedelta(minutes=1)).isoformat()),
    ("source_observed_at",(NOW-timedelta(days=91)).isoformat()),
])
def test_untrusted_or_stale_event_fails_closed(field,value):
    bad=row();bad[field]=value
    with pytest.raises(ValueError):
        review([bad])


def test_extra_personal_content_field_cannot_be_ingested():
    bad=row()
    bad["private_email"]="person@example.org"
    with pytest.raises(ValueError):
        review([bad])


def test_monetary_scenario_cash_time_and_subscription_not_double_counted():
    outcome=compare_monthly_customer_value_scenario(scenario())
    assert outcome["monthly_minutes_saved_scenario"]==240
    assert outcome["monthly_net_cash_delta_minor_scenario"]==1000
    assert outcome["monthly_time_valued_minor_scenario"]==4000
    assert outcome["monthly_combined_illustrative_minor_scenario"]==5000
    assert outcome["solution_cost_counted_once"] is True
    assert outcome["customer_savings_independently_measured"] is False
    assert outcome["customer_roi_verified"] is False
    assert outcome["income_or_profit_realized"] is False
    assert outcome["forecast_probability"] is None


def test_scenario_harm_and_unknown_valuations_not_turned_into_benefit():
    loss=compare_monthly_customer_value_scenario(scenario(
        minutes_before_month=100,minutes_after_month=200,
        cash_before_month_minor=0,cash_after_month_minor=2000,
        solution_cost_month_minor=500,
        time_value_per_hour_minor=None))
    assert loss["monthly_minutes_saved_scenario"]==-100
    assert loss["monthly_net_cash_delta_minor_scenario"]==-2500
    assert loss["monthly_time_valued_minor_scenario"] is None
    assert loss["monthly_combined_illustrative_minor_scenario"] is None
    unknown=compare_monthly_customer_value_scenario(scenario(
        cash_after_month_minor=None))
    assert unknown["monthly_net_cash_delta_minor_scenario"] is None
    assert unknown["monthly_combined_illustrative_minor_scenario"] is None


@pytest.mark.parametrize("patch",[
    {"solution_cost_month_minor":-1},
    {"minutes_before_month":True},
    {"time_value_per_hour_minor":float("nan")},
    {"currency":"BTC"},
    {"minutes_after_month":1000001},
])
def test_scenario_rejects_malformed_false_precision(patch):
    with pytest.raises(ValueError):
        compare_monthly_customer_value_scenario(scenario(**patch))


def test_existing_community_aggregate_outputs_no_authors_and_no_actual_buying():
    r=review_existing_community_needs(source(),as_of=NOW)
    assert r["status"]=="EXISTING_COMMUNITY_NEEDS_RESEARCH_BRIDGED"
    assert r["research_theme_count"]==len(SOLUTION_MAP)
    assert r["coverage_of_all_products_apps_services_verified"] is False
    assert r["independent_purchase_data_connected"] is False
    assert r["time_or_money_benefit_verified"] is False
    assert r["prospective_quant_issuance_authorized"] is False
    assert r["outbound_sent"] is False
    assert "alice@example.com" not in json.dumps(r)
    assert "https://reddit.com" not in json.dumps(r)
    assert all(set(h["product_category_research_plan"]) ==
               {"app","product","service","data_product"} for h in r["hypotheses"])


@pytest.mark.parametrize("mutation",[
    lambda s:s.update(execution_authority="send"),
    lambda s:s.update(schema_version="empire.fake.v1"),
    lambda s:s["pain_solution_briefs"][0].update(offer_key="hijacked"),
    lambda s:s["pain_solution_briefs"][0].update(products=["fake"]),
    lambda s:s["pain_solution_briefs"][0].update(high_intent_mentions=200),
    lambda s:s["pain_solution_briefs"].append(deepcopy(s["pain_solution_briefs"][0])),
    lambda s:s.update(observed_at=(NOW+timedelta(days=1)).isoformat()),
])
def test_aggregate_tampering_holds(mutation):
    s=source();mutation(s)
    with pytest.raises(ValueError):
        review_existing_community_needs(s,as_of=NOW)


def test_only_aggregate_runtime_source_read_no_private_records(tmp_path):
    s=source()
    p=tmp_path/"runtime/community_intent/latest.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(s))
    (p.parent/"observations.json").write_text("DO_NOT_READ_PRIVATE_TEXT")
    report=review_existing_community_needs_runtime(tmp_path,as_of=NOW)
    assert report["research_theme_count"]==len(SOLUTION_MAP)
    assert not (p.parent/"customer_value_latest.json").exists()
    p.unlink()
    with pytest.raises(ValueError):
        review_existing_community_needs_runtime(tmp_path,as_of=NOW)


def test_cross_market_blueprint_covers_everyday_and_b2b_but_has_no_claimed_demand():
    p=build_cross_market_customer_value_research_blueprint()
    assert p["status"]=="CROSS_MARKET_RESEARCH_BLUEPRINT_ONLY"
    assert p["research_question_count"]==20
    assert p["market_count"]==2
    assert set(q["audience"] for q in p["questions"])=={"consumer","business"}
    assert {c for q in p["questions"] for c in q["eligible_purchase_types"]}=={
        "product","app","service","data_product"}
    assert p["buyer_data_or_spend_observed"] is False
    assert p["research_questions_are_detected_market_needs"] is False
    assert p["real_world_search_executed"] is False
    assert p["outbound_sent"] is False
    assert p["database_writes"] is False
    assert all(q["savings_measured"] is False for q in p["questions"])
    assert any(q["job_to_be_done"]=="avoid_subscription_waste" for q in p["questions"])
    assert any(q["job_to_be_done"]=="reduce_manual_work" for q in p["questions"])


@pytest.mark.parametrize("markets", [
    (),
    ("united_kingdom","united_kingdom"),
    ("person@email",),
    ("united_kingdom",)*5,
    ["united_states"],
])
def test_blueprint_invalid_research_scope_rejected(markets):
    with pytest.raises(ValueError):
        build_cross_market_customer_value_research_blueprint(markets)
