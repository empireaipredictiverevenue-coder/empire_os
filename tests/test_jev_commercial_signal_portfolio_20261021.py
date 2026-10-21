"""Commercial intent portfolio must NEVER promote a social observation to buyer."""
import json
from pathlib import Path

import pytest

from empire_os.jev_commercial_signal_portfolio import review_existing_intent_signals
from empire_os.typed_decision_provider import TypedDecisionResult


def row(num, text, *, first_party=False, url=None, source="reddit_intent", status="unresolved"):
    return {
        "source":source,"status":status,"execution_authority":"none",
        "entity_id":None,"prospect_id":None,
        "last_seen_at":f"2026-10-21T15:{num:02}:00+00:00",
        "raw":{"community_intent":{
            "source":"reddit","niche":"roofing",
            "title":"Commercial demand discussion",
            "text":text,
            "url":url or f"https://reddit.com/r/roofing/test-{num}",
            "first_party_verified":first_party,
        }},
    }


def inputs():
    return {
        "owner":row(1, "I own a roofing company. We need 3 more qualified appointments per week and are actively looking for a specialist."),
        "vendor":row(2, "We help contractors automate their follow up. Book a demo."),
        "job":row(3, "Where should I take my career? I want to land a sales job."),
    }


class LocalModel:
    def __init__(self, label="REVIEW_BUYER_CAPACITY", fail=False, provider="laya_http", shadow=True):
        self.label,self.fail,self.provider,self.shadow=label,fail,provider,shadow
        self.requests=[]

    def evaluate(self,request):
        assert set(request.state)=={
            "niche","channel","actor_class","deterministic_lane","contradictions",
            "identity_verified","buyer_capacity_verified","source_review_only",
        }
        assert request.state["identity_verified"] is False
        assert request.state["buyer_capacity_verified"] is False
        assert "http" not in json.dumps(request.state)
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("model timed out")
        return TypedDecisionResult(
            provider_key=self.provider,model_key="local-laya-fixture",
            task_key=request.task_key,decision_schema_ref=request.decision_schema_ref,
            state_ref=request.state_ref,label=self.label,confidence=.95,
            latency_ms=4.0,source_ref="local:shadow:synthetic",
            shadow_only=self.shadow,execution_authority="none",
        )


def test_actor_and_jev_rank_buyer_vs_vendor_and_job_seeker():
    out=review_existing_intent_signals(inputs())
    assert out["signals_selected_for_review"]==3
    assert out["lane_counts"]["REVIEW_IDENTITY"]==1
    assert out["lane_counts"]["DISCARD"]==2
    assert out["identity_promotions"]==0
    assert out["outreach_sent"]==0
    assert out["canonical_prospects_created"]==0
    assert out["database_writes"] is False
    assert "I own" not in json.dumps(out)
    assert "reddit.com" not in json.dumps(out)


def test_fake_first_party_verified_on_social_payload_is_stripped():
    source={"social":row(1,"I own a roofing company and need qualified appointments immediately. I am actively looking for a specialist.",first_party=True)}
    out=review_existing_intent_signals(source)
    assert out["items"][0]["identity_verified"] is False
    assert out["items"][0]["deterministic_review_lane"]!="REVIEW_BUYER_CAPACITY"
    assert out["identity_promotions"]==0


def test_local_shadow_can_only_suggest_not_approve_buyer():
    model=LocalModel()
    out=review_existing_intent_signals(inputs(),provider=model,model_call_budget=2)
    assert len(model.requests)==1
    target=next(x for x in out["items"] if x["deterministic_review_lane"]=="REVIEW_IDENTITY")
    assert target["shadow_status"]=="SHADOW_ESCALATE"
    assert target["proposed_model_lane"]=="REVIEW_BUYER_CAPACITY"
    assert target["deterministic_review_lane"]=="REVIEW_IDENTITY"
    assert out["buyer_capacity_verified"] is False
    assert out["outreach_sent"]==0


@pytest.mark.parametrize("model",[
    LocalModel(fail=True), LocalModel(provider="hosted_jev"),
    LocalModel(shadow=False), LocalModel(label="SEND_OUTREACH"),
])
def test_model_failure_external_route_or_invalid_decision_held(model):
    out=review_existing_intent_signals(inputs(),provider=model,model_call_budget=1)
    x=next(i for i in out["items"] if i["deterministic_review_lane"]=="REVIEW_IDENTITY")
    assert x["shadow_status"]=="SHADOW_UNAVAILABLE_HELD"
    assert x["deterministic_review_lane"]=="REVIEW_IDENTITY"
    assert out["canonical_prospects_created"]==0


def test_dedupe_source_link_across_multiple_signals():
    same_url="https://reddit.com/r/roofing/identical"
    data={
        "one":row(1,"I own a roofing company. We need more leads and I am looking for a specialist.",url=same_url),
        "two":row(2,"I own a roofing company. We need more leads and I am looking for a specialist.",url=same_url),
    }
    out=review_existing_intent_signals(data)
    assert out["signals_selected_for_review"]==2
    assert out["review_item_count"]==1
    assert out["duplicate_source_refs_collapsed"]==1


def test_late_untrusted_source_blocks_every_model_call():
    model=LocalModel()
    data=inputs()
    data["late"]=row(4,"I own a roofing company and need appointments.")
    data["late"]["entity_id"]="someone-created-a-prospect"
    with pytest.raises(ValueError):
        review_existing_intent_signals(data,provider=model,model_call_budget=2)
    assert not model.requests


def test_source_and_actor_fields_not_sent_to_model():
    model=LocalModel()
    data={"secret":row(1,"I own a roofing company. We need appointments and I'm looking for a specialist. Contact secret@example.com.")}
    out=review_existing_intent_signals(data,provider=model,model_call_budget=1)
    assert len(model.requests)==1
    public=json.dumps(out)
    assert "secret@example.com" not in public
    assert "Contact " not in public
    assert "secret@" not in json.dumps(model.requests[0].state)


def test_completed_or_other_source_records_are_not_reviewed():
    data={
        "completed":row(1,"I own a roofing company.",status="resolved"),
        "permit":row(2,"I own a roofing company.",source="permits_nyc"),
    }
    out=review_existing_intent_signals(data)
    assert out["review_item_count"]==0
    assert out["eligible_unresolved_signals"]==0
    assert out["outreach_sent"]==0


@pytest.mark.parametrize("kwargs",[
    {"model_call_budget":4},{"max_signals":0},
    {"max_signals":True},{"model_call_budget":-1},
    {"minimum_model_confidence":float("nan")},
])
def test_unbounded_portfolio_controls_are_rejected(kwargs):
    with pytest.raises(ValueError):
        review_existing_intent_signals(inputs(),**kwargs)


def test_private_safe_portfolio_summary_does_not_export_social_posts():
    from scripts.review_jev_commercial_signal_portfolio_20261021 import build_private_safe_summary
    model=LocalModel()
    receipt=build_private_safe_summary(inputs(),provider=model,model_budget=1)
    assert receipt["intent_signals_selected"]==3
    assert receipt["original_signal_record_count"]==3
    assert receipt["verified_buyer_enquiries"]==0
    assert receipt["external_paid_jev_api_called"] is False
    assert receipt["canonical_prospects_created"]==0
    assert receipt["outreach_sent"]==0
    assert receipt["db_writes"] is False
    assert len(receipt["local_model_reported_latency_ms"])==1
    result=json.dumps(receipt)
    assert "reddit.com" not in result
    assert "I own" not in result
    assert "signal_event_sha256" not in result
    assert "source_reference_sha256" not in result


def test_published_live_portfolio_contains_only_aggregate_canonical_evidence():
    from pathlib import Path
    saved=(Path(__file__).resolve().parents[1] /
           "docs/commercial/JEV_COMMERCIAL_INTENT_EXECUTIVE_REVIEW_20261021.json")
    receipt=json.loads(saved.read_text())
    assert receipt["status"]=="LIVE_ORIGINAL_SIGNAL_PORTFOLIO_SHADOW_REVIEW_ONLY"
    assert receipt["original_signal_record_count"]==374
    assert receipt["intent_signals_selected"]==35
    assert receipt["deterministic_review_lane_counts"]=={
        "DISCARD":1, "MONITOR":33,"REVIEW_IDENTITY":1,
    }
    assert receipt["local_shadow_attempts"]==1
    assert receipt["verified_buyer_enquiries"]==0
    assert receipt["external_paid_jev_api_called"] is False
    assert receipt["outreach_sent"]==0
    assert receipt["db_writes"] is False
    assert receipt["execution_authority"]=="none"
    body=saved.read_text()
    assert "reddit.com" not in body
    assert "linkedin.com" not in body
    assert "@" not in body
    assert "signal_event_sha256" not in body
    assert "first_party_verified" not in body
