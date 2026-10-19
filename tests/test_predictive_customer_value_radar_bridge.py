"""Live-origin Radar source coupling to falsifiable customer value hypotheses.

Fixture sources are constructed from the actual existing Radar builder.
No source crawler, private contact, probability, payment or DB mutation.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.pain_solution_engine import SOLUTION_MAP
from empire_os.opportunity_radar import build_opportunity_radar
from empire_os.predictive_customer_value_radar_bridge import (
    review_customer_value_radar_bridge,
    review_customer_value_radar_bridge_runtime,
)

NOW=datetime(2026,10,19,22,30,tzinfo=timezone.utc)
COMM_AT=(NOW-timedelta(minutes=2)).isoformat()
RADAR_AT=(NOW-timedelta(minutes=1)).isoformat()


def community():
    briefs=[]
    for pain, config in SOLUTION_MAP.items():
        active=pain in ("sales_conversion","search_visibility")
        briefs.append({
            "pain_point":pain, "offer_key":config["offer_key"],
            "products":list(config["products"]),
            "observed_mentions":5 if active else 2,
            "high_intent_mentions":2 if active else 0,
            "average_intent_score":62 if active else 10,
            "evidence_strength":"moderate" if active else "thin",
            "opportunity_event":"opportunity_candidate_created" if active else None,
            "next_actions":list(config["next_actions"]),
            "evidence_urls":["https://reddit.com/r/example/comments/1234/post/"] if active else [],
            "execution_authority":"none",
            "secret_author":"private.person@example.org",
        })
    return {
        "schema_version":"empire.community_intent.v2",
        "mode":"OBSERVE",
        "execution_authority":"none",
        "observed_at":COMM_AT,
        "pain_solution_briefs":briefs,
    }


def inputs():
    c=community()
    radar=build_opportunity_radar(
        market_gps=None, community_intent=c,
        competitor_market=None,
        generated_at=RADAR_AT,
    )
    return c,radar


def review(c=None,r=None):
    if c is None or r is None:
        c,r=inputs()
    return review_customer_value_radar_bridge(c,r,as_of=NOW)


def test_exact_source_revision_generates_prospective_value_hypotheses_only():
    result=review()
    assert result["status"]=="CUSTOMER_VALUE_TO_RADAR_RESEARCH_BRIDGED"
    assert result["source_identity_aligned"] is True
    assert result["source_revision_attested"] is False
    assert result["source_lag_seconds"]==60
    assert result["research_pain_count"]==len(SOLUTION_MAP)
    assert result["community_radar_candidate_count"]==2
    assert result["market_research_candidate_count"]==0
    assert result["consumer_product_research_blueprint_count"]==20
    assert {r["problem_key"] for r in result["research_cards"]}=={
        "sales_conversion","search_visibility",
    }
    assert all(r["proposed_comparison"]=="prospective_baseline_or_randomized_holdout"
               for r in result["research_cards"])
    assert all(r["original_value_baseline_measured"] is False for r in result["research_cards"])
    assert result["buyer_identity_authenticated"] is False
    assert result["market_demand_verified"] is False
    assert result["prospective_original_quant_registered"] is False
    assert result["verified_outcome_calibration_performed"] is False
    assert result["new_research_executed"] is False
    assert result["database_writes"] is False
    assert "private.person@example.org" not in json.dumps(result)
    assert "reddit.com" not in json.dumps(result)


def test_public_pain_without_radar_promotion_remains_research_only():
    c,r=inputs()
    assert not any(x.get("opportunity_key")=="community_pain:lead_generation"
                   for x in r["candidates"])
    result=review(c,r)
    assert result["research_pain_count"] > result["community_radar_candidate_count"]
    assert result["verified_product_purchase_count"] is None


@pytest.mark.parametrize("mutate,reason",[
    (lambda c,r: r.update(commercial_authority="send"),"UNTRUSTED_RADAR_AUTHORITY"),
    (lambda c,r: r["source_status"]["community_intent"].update(generated_at=NOW.isoformat()),"ORIGINAL_COMMUNITY_REVISION_NOT_BOUND"),
    (lambda c,r: r.update(candidate_count=77),"RADAR_CANDIDATE_COUNT_UNTRUSTED"),
    (lambda c,r: r["candidates"][0].update(revenue_inferred=True),"UNSUPPORTED_RADAR_BUYER_OR_FORECAST_CLAIM"),
    (lambda c,r: r["candidates"][0].update(opportunity_key="community_pain:automation_ops"),"RADAR_COMMUNITY_PROMOTION_DRIFT"),
    (lambda c,r: r["candidates"][0].update(products=["new_unverified_product"]),"RADAR_OFFER_OR_PUBLIC_PAIN_REVISION_DRIFT"),
    (lambda c,r: r["candidates"][0].update(offer_key="fake_offer"),"RADAR_OFFER_OR_PUBLIC_PAIN_REVISION_DRIFT"),
    (lambda c,r: r["candidates"][0].update(observed_mentions=1000000),"RADAR_OFFER_OR_PUBLIC_PAIN_REVISION_DRIFT"),
    (lambda c,r: r["candidates"][0].update(source="unapproved_source"),"COMMUNITY_SOURCE_OWNER_MISMATCH"),
])
def test_forged_or_mismatched_commercial_claims_fail_closed(mutate,reason):
    c,r=inputs();mutate(c,r)
    result=review(c,r)
    assert result["status"]=="SOURCE_EVIDENCE_HOLD"
    assert result["hold_code"]==reason
    assert result["research_cards"]==[]
    assert result["buyer_identity_authenticated"] is False
    assert result["outbound_sent"] is False


def test_community_radar_source_time_future_and_skew_hold():
    c,r=inputs()
    r["generated_at"]=(NOW+timedelta(minutes=1)).isoformat()
    assert review(c,r)["hold_code"]=="STALE_OR_FUTURE_RADAR"
    c,r=inputs()
    r["generated_at"]=(NOW-timedelta(hours=5)).isoformat()
    assert review(c,r)["hold_code"]=="COMMUNITY_RADAR_SOURCE_EPOCH_MISMATCH"
    c,r=inputs()
    c["observed_at"]=(NOW+timedelta(seconds=1)).isoformat()
    assert review(c,r)["status"]=="SOURCE_EVIDENCE_HOLD"


def test_radar_candidate_identity_duplicate_holds():
    c,r=inputs()
    r["candidates"].append(deepcopy(r["candidates"][0]))
    r["candidate_count"]+=1
    assert review(c,r)["hold_code"]=="DUPLICATE_OR_INVALID_RADAR_OPPORTUNITY"


def test_snapshot_runtime_reads_only_public_aggregates(tmp_path):
    c,r=inputs()
    for path,data in [
        ("runtime/community_intent/latest.json",c),
        ("runtime/opportunity_radar/latest.json",r),
    ]:
        p=tmp_path/path;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(data))
    (tmp_path/"runtime/community_intent/observations.json").write_text("DO_NOT_READ_RAW_TEXT")
    (tmp_path/"runtime/opportunity_radar/private_customer.json").write_text("DO_NOT_READ_PRIVATE_CUSTOMER")
    report=review_customer_value_radar_bridge_runtime(tmp_path,as_of=NOW)
    assert report["status"]=="CUSTOMER_VALUE_TO_RADAR_RESEARCH_BRIDGED"
    assert not (tmp_path/"runtime/customer_value_latest.json").exists()
    (tmp_path/"runtime/community_intent/latest.json").unlink()
    assert review_customer_value_radar_bridge_runtime(tmp_path,as_of=NOW)["hold_code"]=="UNAVAILABLE_COMMUNITY_SOURCE"


def test_no_prospective_registration_even_if_market_radar_ranked():
    c,r=inputs()
    for item in r["candidates"]:
        item["observed_priority_score"]=100
    report=review(c,r)
    assert report["prospective_original_quant_registered"] is False
    assert all(item["quant_ready"] is False for item in report["research_cards"])


def test_source_revision_fingerprint_changes_after_new_valid_snapshot():
    c,r=inputs()
    first=review(c,r)
    later=(NOW-timedelta(seconds=20)).isoformat()
    r["generated_at"]=later
    second=review(c,r)
    assert second["status"]=="CUSTOMER_VALUE_TO_RADAR_RESEARCH_BRIDGED"
    assert first["research_cards"][0]["source_revision_fingerprint"] != second["research_cards"][0]["source_revision_fingerprint"]
