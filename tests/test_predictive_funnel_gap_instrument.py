"""Commercial funnel source observations cannot invent lost sales or cause."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json
import pytest

from empire_os.commercial_funnel import normalize_funnel_payload
from empire_os.predictive_funnel_gap_instrument import (
    review_commercial_funnel_gap_source,
    review_commercial_funnel_gap_runtime,
)

NOW=datetime(2026,10,20,12,tzinfo=timezone.utc)


def raw():
    return {
        "schema_version":"empire.founder_commercial_funnel.v1",
        "generated_at":(NOW-timedelta(hours=1)).isoformat(),
        "counts":{
            "prospect_acquisitions":493,"buyer_reviews":34,
            "buyer_reviews_approved":32,"outbound_intents":31,
            "outbound_delivered":25,"commercial_replies":0,
            "closer_cases":0,"commercial_terms_reviews":0,
            "commercial_terms_approved":0,"payment_requests":0,
            "verified_payment_evidence":0,"fulfilment_orders":0,
            "fulfilled_orders":0,"recognized_revenue_events":0,
        },
        "outbound_status_counts":{"delivered":25},
        "reply_classification_counts":{},
        "recognized_revenue_cents":0,"realized_margin_cents":0,
        "actual_revenue":False,
    }


def sample():
    return normalize_funnel_payload(raw())


def inspect(packet=None,*,as_of=NOW):
    return review_commercial_funnel_gap_source(
        packet if packet is not None else sample(),as_of=as_of,
    )


def test_fresh_original_owner_stage_is_an_observation_not_a_sales_loss():
    result=inspect()
    assert result["status"]=="FOUNDER_FUNNEL_AGGREGATE_STAGE_RESEARCH_REVIEWED"
    assert result["source_owner_stage"]=="outbound_delivered"
    assert result["source_reported_stage_counts"]["outbound_delivered"]==25
    assert result["source_reported_stage_counts"]["commercial_replies"]==0
    assert result["stagnation_hypothesis_code"]=="DELIVERED_OUTBOUND_WITH_NO_REPLIES_RECORDED_IN_SOURCE"
    assert result["stage_counts_allow_conversion_fractions"] is False
    assert result["stage_counts_share_a_verified_purchase_cohort"] is False
    assert result["observed_zero_replies_proves_no_industry_buying_demand"] is False
    assert result["derived_revenue_lost_minor"] is None
    assert result["recognized_profit_by_cohort_minor"] is None
    assert result["root_cause_established"] is False
    assert result["source_revenue_total_can_be_attributed_to_proposed_gap"] is False
    assert result["outbound_sent"] is False
    assert "@" not in json.dumps(result)


def test_source_staleness_holds_counts_unknown_not_zero():
    x=inspect(as_of=NOW+timedelta(days=5))
    assert x["status"]=="FOUNDER_FUNNEL_SOURCE_STALE_HOLD"
    assert x["source_age_hours"]>48
    assert x["source_reported_stage_counts"] is None
    assert x["stagnation_hypothesis_code"] is None
    assert x["derived_revenue_lost_minor"] is None


def test_terms_without_payment_is_not_a_proven_revenue_gap():
    r=raw()
    r["counts"]["commercial_replies"]=2
    r["counts"]["commercial_terms_approved"]=1
    data=normalize_funnel_payload(r)
    result=inspect(data)
    assert result["stagnation_hypothesis_code"]=="APPROVED_TERMS_WITH_NO_VERIFIED_PAYMENT_IN_SOURCE"
    assert result["independent_buyer_purchase_authenticated"] is False
    assert result["derived_revenue_lost_minor"] is None


def test_raw_claimed_replies_need_real_terms_verification():
    x=raw()
    x["counts"]["commercial_replies"]=2
    y=inspect(normalize_funnel_payload(x))
    assert y["stagnation_hypothesis_code"]=="REPLIES_WITH_NO_APPROVED_TERMS_RECORDED_IN_SOURCE"
    assert y["next_action"]=="VERIFY_ORIGINAL_BUYING_ROLE_FIT_AND_COMMERCIAL_TERMS"
    assert y["root_cause_established"] is False


def test_independent_stage_counts_are_not_converted_to_funnel_ratio():
    data=sample()
    data["counts"]["prospect_acquisitions"]=1
    data["counts"]["outbound_delivered"]=5000
    result=inspect(data)
    assert result["status"]=="FOUNDER_FUNNEL_AGGREGATE_STAGE_RESEARCH_REVIEWED"
    assert result["stage_counts_allow_conversion_fractions"] is False
    assert "conversion_rate" not in json.dumps(result)


@pytest.mark.parametrize("key,bad",[
    ("commercial_replies",True),
    ("outbound_delivered",-1),
    ("prospect_acquisitions",100_000_001),
    ("buyer_reviews",1.5),
    ("payment_requests","3"),
])
def test_untrusted_bounded_counts_holds(key,bad):
    data=sample()
    data["counts"][key]=bad
    x=inspect(data)
    assert x["status"]=="FOUNDER_FUNNEL_COUNTS_HOLD"
    assert x["source_reported_stage_counts"] is None


def test_source_reconciles_original_existing_owner_stage_algorithm():
    data=sample()
    data["current_stage"]="recognized_revenue"
    assert inspect(data)["status"]=="FOUNDER_FUNNEL_STAGE_CONFLICT_HOLD"


def test_source_revenue_flag_never_proves_same_cohort_outcome():
    raw_data=raw()
    raw_data["counts"]["recognized_revenue_events"]=3
    raw_data["recognized_revenue_cents"]=100000
    raw_data["realized_margin_cents"]=50000
    raw_data["actual_revenue"]=True
    packet=normalize_funnel_payload(raw_data)
    out=inspect(packet)
    assert out["source_owner_stage"]=="recognized_revenue"
    assert out["derived_revenue_lost_minor"] is None
    assert out["recognized_profit_by_cohort_minor"] is None
    assert out["independent_buyer_purchase_authenticated"] is False


def test_private_file_not_read_when_source_unavailable(tmp_path):
    path=tmp_path/"runtime/commercial_funnel/latest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(sample()))
    (path.parent/"private_buyer_contacts.json").write_text("PRIVATE_PERSON")
    out=review_commercial_funnel_gap_runtime(tmp_path,as_of=NOW)
    assert out["status"]=="FOUNDER_FUNNEL_AGGREGATE_STAGE_RESEARCH_REVIEWED"
    assert "PRIVATE_PERSON" not in json.dumps(out)
    path.unlink()
    assert review_commercial_funnel_gap_runtime(tmp_path,as_of=NOW)[
        "status"]=="FOUNDER_FUNNEL_SOURCE_MISSING"
