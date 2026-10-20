"""Exact source-qualified territory research for economic digital twins.

Uses the EXISTING Market Sweep producer to generate fixtures, not hand-crafted
market claims or production customer data.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.market_sweep_revenue_gps import normalize_market_sweep
from empire_os.predictive_market_evidence_binding import (
    review_revenue_gps_territory_evidence,
    review_revenue_gps_territory_evidence_runtime,
    bind_territory_research_to_market_twin,
)
from test_predictive_market_economic_twin import (
    market, driver,
)
from test_predictive_profitability_playbooks import (
    pilot, plan, NOW,
)
from empire_os.predictive_market_economic_twin import review_market_economic_twin


def snapshot(*,with_commerce=False):
    rows=[
        {"niche":"hvac","metro":"little rock, ar","prospect_count":9,
         "canonical_company_count":2,"acquisition_count":3,
         "qualification_count":2,
         "competitive_entity_count":1,"competitive_signal_count":3,
         "commercial_reply_count":1 if with_commerce else 0,
         "commercial_terms_count":1 if with_commerce else 0,
         "verified_payment_count":1 if with_commerce else 0,
         "recognized_revenue_event_count":1 if with_commerce else 0,
         "recognized_revenue_cents":1000 if with_commerce else 0,
         "realized_margin_cents":300 if with_commerce else 0},
        {"niche":"roofing","metro":"little rock, ar","prospect_count":5,
         "acquisition_count":2,"qualification_count":2,
         "canonical_company_count":1,"competitive_entity_count":0},
        {"niche":"general_contractor","metro":"nyc",
         "acquisition_count":47,"qualification_count":47,
         "prospect_count":47},
    ]
    s=normalize_market_sweep(
        {"markets":rows,"generated_at":(NOW-timedelta(minutes=5)).isoformat(),
         "window_days":7},
        catalog=[],
    )
    s["restricted_source_scope"]="RESTRICTED_AGGREGATES_ONLY"
    s["unverified_positive_classifications_present"]=0
    s["unverified_reply_records_present"]=0
    # The running producer reports these two explicit counters, while this
    # isolated feature branch's older producer fixture does not include them.
    # Supply 0 only in synthetic fixtures; production missing fields HOLD.
    for item in s["markets"]:
        item["unverified_reply_record_count"]=0
        item["unverified_positive_classification_count"]=0
    return s


def review(s=None):
    return review_revenue_gps_territory_evidence(
        s if s is not None else snapshot(),as_of=NOW,
    )


def test_current_market_producer_join_is_exact_and_does_not_prove_paid_demand():
    r=review()
    assert r["status"]=="TERRITORY_LEVEL_MARKET_RESEARCH_JOIN_READY"
    assert r["market_count"]==3
    assert r["reported_commercial_demand_market_count"]==0
    assert r["reported_competitor_research_market_count"]==2
    assert r["market_research_is_verified_buying_demand"] is False
    assert r["actual_delivery_capacity_verified"] is False
    assert r["product_unit_price_authenticated"] is False
    assert r["original_forecast_registered"] is False
    assert len(r["source_revision_fingerprint"])==64
    assert r["data_mutation"] is False
    cards={(x["market_niche_key"],x["market_geography_key"]):x
           for x in r["territory_research_cards"]}
    assert len(cards)==3
    assert ("hvac","little_rock_ar") in cards
    assert ("roofing","little_rock_ar") in cards
    assert ("general_contractor","nyc") in cards
    assert cards[("hvac","little_rock_ar")]["competitive_signal_research_count"]==3
    assert cards[("hvac","little_rock_ar")]["prospect_acquisition_research_count"]==3
    assert "NO_OBSERVED_COMMERCIAL_REPLY_TERMS_OR_PAYMENT_EVIDENCE" in (
        cards[("hvac","little_rock_ar")]["missing_proof"])
    assert cards[("hvac","little_rock_ar")]["research_owner_action"]==(
        "FIND_ORIGINAL_DIRECT_PURCHASER_DEMAND_AND_BUYBOX")
    assert all(c["independent_purchase_evidence_connected"] is False for c in cards.values())


def test_claimed_commercial_source_events_are_not_independently_verified():
    s=snapshot(with_commerce=True)
    out=review(s)
    assert out["status"]=="TERRITORY_LEVEL_MARKET_RESEARCH_JOIN_READY"
    assert out["reported_commercial_demand_market_count"]==1
    hvac=next(c for c in out["territory_research_cards"]
              if c["market_niche_key"]=="hvac")
    assert hvac["source_reported_commercial_replies_not_authenticated"]==1
    assert hvac["source_reported_commercial_terms_not_accepted"]==1
    assert hvac["source_reported_payment_event_count_not_independently_authenticated"]==1
    assert hvac["source_reported_recognized_revenue_event_count_not_attributed"]==1
    assert hvac["research_owner_action"]=="VERIFY_ORIGINAL_BUYER_TERMS_PRICE_AND_TERRITORY_CAPACITY"
    assert hvac["commercial_observations_are_unique_purchasers"] is False
    assert hvac["customer_accepted_price_authenticated"] is False
    assert out["revenue_recognized_by_this_bridge"] is False


def test_revision_tracks_real_changes_and_source_epoch():
    r=review()
    s=snapshot()
    s["markets"][0]["acquisition_count"]+=1
    assert review(s)["source_revision_fingerprint"]!=r["source_revision_fingerprint"]
    s=snapshot()
    s["generated_at"]=(NOW-timedelta(minutes=2)).isoformat()
    assert review(s)["source_revision_fingerprint"]!=r["source_revision_fingerprint"]


def test_geographic_market_twin_binding_is_exact_text_but_not_geo_authentication():
    s=review()
    p=pilot()
    m=market()
    m["geography_key"]="little_rock_ar"
    twin=review_market_economic_twin(
        p,plan(p),m,[driver()],as_of=NOW,
    )
    attached=bind_territory_research_to_market_twin(s,twin)
    assert attached["status"]=="EXACT_TEXT_TERRITORY_RESEARCH_LINK_ONLY"
    assert attached["research_territory_binding_present"] is True
    assert len(attached["market_source_revision_fingerprint"])==64
    assert attached["hypothetical_twin_pilot_design_sha256"]==p["design_revision_sha256"]
    assert attached["market_source_reported_commercial_replies_not_authenticated"]==0
    assert attached["source_market_metro_text_proves_jurisdiction"] is False
    assert attached["territory_data_is_paid_demand_or_capacity"] is False
    assert attached["hypothetical_twin_price_is_accepted_customer_price"] is False
    assert attached["economic_scenario_authentic"] is False
    assert attached["database_writes"] is False


def test_ambiguous_alias_geography_never_silently_joins():
    twin=review_market_economic_twin(
        pilot(),plan(),market(),[driver()],as_of=NOW,
    )
    assert twin["geography_key"]=="littlerock_ar"
    output=bind_territory_research_to_market_twin(review(),twin)
    assert output["status"]=="TWIN_TERRITORY_SOURCE_NOT_EXACTLY_MATCHED"
    assert output["research_territory_binding_present"] is False
    assert output["market_source_revision_fingerprint"] is None
    assert output["economic_scenario_authentic"] is False


def test_wrong_niche_does_not_match_even_with_same_location():
    p=pilot();m=market()
    m["geography_key"]="little_rock_ar"
    m["niche_key"]="air_duct"
    twin=review_market_economic_twin(p,plan(p),m,[driver()],as_of=NOW)
    out=bind_territory_research_to_market_twin(review(),twin)
    assert out["research_territory_binding_present"] is False


@pytest.mark.parametrize("change",[
    lambda s:s.update(execution_authority="auto_spend"),
    lambda s:s.update(outreach_enabled=True),
    lambda s:s.update(restricted_source_scope="PUBLIC_RESALE_ALLOWED"),
    lambda s:s.update(revenue_inferred=True),
    lambda s:s.update(buyer_intent_inferred=True),
])
def test_global_rights_and_premature_commercial_claims_fail_closed(change):
    s=snapshot();change(s)
    assert review(s)["hold_code"]=="UNTRUSTED_SOURCE_RIGHTS_OR_AUTHORITY"


@pytest.mark.parametrize("change,code",[
    (lambda s:s.update(market_count=999),"MISSING_OR_CONTRADICTORY_MARKET_COUNT"),
    (lambda s:s.update(commercial_demand_market_count=10),"GLOBAL_AND_TERRITORY_EVIDENCE_COUNTS_DRIFTED"),
    (lambda s:s.update(competitive_evidence_market_count=0),"GLOBAL_AND_TERRITORY_EVIDENCE_COUNTS_DRIFTED"),
    (lambda s:s.update(window_days=0),"INVALID_SOURCE_OBSERVATION_WINDOW"),
    (lambda s:s.update(verified_product_economics={"actual_revenue":True}),"SCENARIO_MISTAKEN_FOR_REAL_COST_OR_PRICE"),
    (lambda s:s.update(generated_at=(NOW+timedelta(minutes=1)).isoformat()),"STALE_OR_FUTURE_SOURCE_EPOCH"),
    (lambda s:s.update(generated_at=(NOW-timedelta(hours=9)).isoformat()),"STALE_OR_FUTURE_SOURCE_EPOCH"),
])
def test_global_source_count_clock_economics_contract(change,code):
    s=snapshot();change(s)
    r=review(s)
    assert r["status"]=="TERRITORY_RESEARCH_EVIDENCE_HOLD"
    assert r["hold_code"]==code
    assert r["territory_research_cards"]==[]


@pytest.mark.parametrize("field,value",[
    ("niche","phone@example.com"),
    ("metro","49 High Street, SW1"),
    ("metro","littlerock@private.example"),
    ("commercial_demand_evidence_count",1),
    ("commercial_demand_state","observed"),
    ("qualification_count",True),
    ("competitive_evidence_coverage_gap_count",100),
    ("competitor_pressure_is_model",False),
    ("competitor_pressure_basis","verified_market_share"),
    ("supply_gap_inferred",True),
    ("product_purchase_inferred",True),
    ("market_share_inferred",True),
    ("buyer_intent_inferred",True),
    ("research_priority_score",200),
    ("research_priority_score",float("nan")),
    ("unverified_positive_classification_count",1),
    ("realized_margin_cents",500),
    ("outreach_enabled",True),
])
def test_tampered_territory_claims_hold_without_promoting_buyers(field,value):
    s=snapshot()
    target=next(row for row in s["markets"] if row["niche"]=="hvac") if field=="competitor_pressure_is_model" else s["markets"][0]
    target[field]=value
    r=review(s)
    assert r["status"]=="TERRITORY_RESEARCH_EVIDENCE_HOLD"
    assert r["hold_code"]=="INVALID_OR_CONFLICTING_TERRITORY_SOURCE_ROWS"
    assert r["territory_research_cards"]==[]
    assert r["original_forecast_registered"] is False
    assert r["product_unit_price_authenticated"] is False


def test_duplicate_or_canonical_geographic_alias_collision_holds():
    s=snapshot()
    s["markets"].append(deepcopy(s["markets"][0]))
    s["market_count"]+=1
    assert review(s)["hold_code"]=="INVALID_OR_CONFLICTING_TERRITORY_SOURCE_ROWS"
    s=snapshot()
    alias=deepcopy(next(row for row in s["markets"] if row["niche"]=="hvac"))
    alias["metro"]="little rock ar"
    s["markets"].append(alias)
    s["market_count"]+=1
    assert review(s)["hold_code"]=="INVALID_OR_CONFLICTING_TERRITORY_SOURCE_ROWS"


def test_research_rank_has_no_verified_sales_interpretation():
    # 47 acquisitions genuinely generates a high *research* rank in the
    # existing producer, but no original buyer purchasing evidence.
    r=review(snapshot())
    assert r["territory_research_cards"][0]["market_niche_key"]=="general_contractor"
    assert r["territory_research_cards"][0]["research_priority_score_not_conversion_probability"]==80.0
    assert r["territory_research_cards"][0]["source_reported_payment_event_count_not_independently_authenticated"]==0
    assert r["market_research_is_verified_buying_demand"] is False
    assert r["live_economic_forecast_issuance_authorized"] is False


def test_only_owner_allowlisted_runtime_file_is_read(tmp_path):
    s=snapshot()
    dest=tmp_path/"runtime/market_sweeps/revenue_gps_latest.json"
    dest.parent.mkdir(parents=True)
    dest.write_text(json.dumps(s))
    secret=tmp_path/"runtime/market_sweeps/private_buyer_messages.json"
    secret.write_text("DO_NOT_READ_PRIVATE_CONTACT")
    review_live=review_revenue_gps_territory_evidence_runtime(tmp_path,as_of=NOW)
    assert review_live["market_count"]==3
    assert "DO_NOT_READ_PRIVATE_CONTACT" not in json.dumps(review_live)
    assert "@" not in json.dumps(review_live)
    assert not (tmp_path/"runtime/market_sweeps/territory_new_output.json").exists()
    dest.unlink()
    missing=review_revenue_gps_territory_evidence_runtime(tmp_path,as_of=NOW)
    assert missing["hold_code"]=="SOURCE_SNAPSHOT_UNAVAILABLE"


@pytest.mark.parametrize("field,value",[
    ("unverified_reply_records_present",1),
    ("unverified_positive_classifications_present",1),
    ("unverified_reply_records_present",None),
    ("unverified_positive_classifications_present",True),
])
def test_global_unverified_reply_intake_is_never_marked_commercial_demand(field,value):
    s=snapshot()
    s[field]=value
    r=review(s)
    assert r["status"]=="TERRITORY_RESEARCH_EVIDENCE_HOLD"
    assert r["hold_code"]=="UNVERIFIED_REPLIES_CANNOT_BE_MARKET_DEMAND"
    assert r["territory_research_cards"]==[]
    assert r["execution_authority"]=="none"


@pytest.mark.parametrize("field,value",[
    ("external_execution_authorized",True),
    ("mutation_authorized",True),
    ("recommended_next_action","start_paid_outbound"),
    ("niche","nonexistent_commercial_buyer"),
    ("evidence_refs",["private:contact@org.example"]),
    ("research_priority_score",True),
])
def test_owner_research_queue_never_grants_action_or_unbacked_territory(field,value):
    s=snapshot()
    s["research_queue"][0][field]=value
    r=review(s)
    assert r["status"]=="TERRITORY_RESEARCH_EVIDENCE_HOLD"
    assert r["hold_code"]=="UNTRUSTED_MARKET_RESEARCH_HANDOFF"
    assert r["market_count"] is None
    assert r["data_mutation"] is False


def test_owner_missing_handoff_does_not_invent_research_work():
    s=snapshot()
    s["research_queue"]=[]
    r=review(s)
    assert r["hold_code"]=="MARKET_RESEARCH_HANDOFF_COUNT_DRIFTED"


def test_economic_twin_cannot_self_certify_true_market_data():
    p=pilot()
    m=market()
    m["geography_key"]="little_rock_ar"
    twin=review_market_economic_twin(p,plan(p),m,[driver()],as_of=NOW)
    twin["source_market_conditions_authenticated"]=True
    with pytest.raises(ValueError):
        bind_territory_research_to_market_twin(review(),twin)


def test_unregistered_economics_cannot_be_upgraded_by_forging_registry_status():
    registry=review()
    registry["status"]="TERRITORY_LEVEL_COMMERCIAL_SALES_VERIFIED"
    p=pilot()
    m=market()
    m["geography_key"]="little_rock_ar"
    twin=review_market_economic_twin(p,plan(p),m,[driver()],as_of=NOW)
    with pytest.raises(ValueError):
        bind_territory_research_to_market_twin(registry,twin)


def test_research_queue_score_cannot_drift_from_original_market():
    s=snapshot()
    s["research_queue"][0]["research_priority_score"]=99
    out=review(s)
    assert out["hold_code"]=="UNTRUSTED_MARKET_RESEARCH_HANDOFF"
    assert out["territory_research_cards"]==[]


def test_research_queue_cannot_advance_without_approved_candidate():
    s=snapshot()
    s["research_queue"][0]["recommended_next_action"]="advance_existing_approved_buyer"
    out=review(s)
    assert out["hold_code"]=="UNTRUSTED_MARKET_RESEARCH_HANDOFF"
    assert out["outbound_sent"] is False


def test_missing_source_unverified_flags_do_not_default_to_zero():
    s=snapshot()
    s.pop("unverified_reply_records_present")
    assert review(s)["hold_code"]=="UNVERIFIED_REPLIES_CANNOT_BE_MARKET_DEMAND"
    s=snapshot()
    s["markets"][0].pop("unverified_reply_record_count")
    assert review(s)["hold_code"]=="INVALID_OR_CONFLICTING_TERRITORY_SOURCE_ROWS"
