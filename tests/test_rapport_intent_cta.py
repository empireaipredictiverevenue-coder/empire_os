"""Authenticated reply + sovereign typed AI proposal -> no-send CTA contract."""
from __future__ import annotations
from copy import deepcopy
from math import nan
import pytest

from empire_os.rapport_intent_cta import (
    LABELS, intent_decision_request, review_intent_cta,
)
from empire_os.typed_decision_provider import TypedDecisionResult
from empire_os.outbound_department import plan_outbound_account
from scripts.review_search_first_sale_rapport import PROSPECTS,review_candidate

A={
    "tenant_id":"tenant-test-1","prospect_id":"prospect-test-1",
    "original_outbound_intent_id":"intent-test-1",
    "contact_email":"brian@gogreencoast.com",
    "company_name":"Green Coast Roofing & Solar",
    "company_name_verified":True,
    "decision_maker":"Brian Sujevich",
    "buyer_review_status":"pending",
    "contact_route":"person_bound","person_bound":True,
    "verified_reply_required_for_followup":True,
    "product_code":"technical_search_audit",
}
def reply(body="Thanks for the note.",classification="positive"):
    return {
        "tenant_id":A["tenant_id"],
        "prospect_id":A["prospect_id"],
        "original_outbound_intent_id":A["original_outbound_intent_id"],
        "sender_address":A["contact_email"],
        "reply_id":"canonical-inbound-1",
        "provider_authenticated":True,
        "same_thread_verified":True,
        "counterpart_identity_verified":True,
        "direction":"inbound",
        "synthetic":False,
        "body_text":body,
        "classification":classification,
        "explicit_product_request_verified":False,
        "requested_product_code":None,
    }


def model(label, r, *, conf=.96):
    request=intent_decision_request(A,r)
    return TypedDecisionResult(
        provider_key="empire_existing_typed_ai",
        model_key="local-shadow-evaluator",
        task_key=request.task_key,
        decision_schema_ref=request.decision_schema_ref,
        state_ref=request.state_ref,
        label=label,
        confidence=conf,
        latency_ms=8.0,
        source_ref=request.state_ref,
        shadow_only=True,
        execution_authority="none",
    )


@pytest.mark.parametrize("label,body,tier",[
    ("problem_discovery","We need help understanding which services customers look for.","DISCOVERY_QUESTION"),
    ("solution_evaluation","Could you send us the written scope of what you would check?","WRITTEN_SCOPE"),
])
def test_verified_observed_signal_and_model_yield_proportionate_review_cta(label,body,tier):
    r=reply(body)
    result=review_intent_cta(account=A,reply=r,
                             model_result=model(label,r),
                             suppression_cleared=True)
    assert result["decision"]=="CTA_DRAFT_FOR_HUMAN_REVIEW"
    assert result["cta_tier"]==tier
    assert result["cta_draft"]
    assert result["review_eligible"] is True
    assert result["human_closer_review_required"] is True
    assert result["send_authorized"] is False
    assert result["outbound_sent"] is False
    assert result["financial_action"] is False
    assert "http" not in result["cta_draft"]


def test_explicit_product_and_independent_exact_request_yield_purchase_cta_review():
    r=reply("How much does your Technical Search Audit cost?",
            "pricing_question")
    r.update(explicit_product_request_verified=True,
             requested_product_code="technical_search_audit")
    result=review_intent_cta(
        account=A,reply=r,
        model_result=model("explicit_product_purchase_request",r),
        suppression_cleared=True,
    )
    assert result["decision"]=="CTA_DRAFT_FOR_HUMAN_REVIEW"
    assert result["cta_tier"]=="PURCHASE_REVIEW"
    assert result["related_product_code"]=="technical_search_audit"
    assert "secure checkout" in result["cta_draft"]
    assert result["catalog_and_terms_review_required"] is True
    assert result["send_authorized"] is False
    assert "https://" not in result["cta_draft"]


def test_vague_positive_reply_stays_no_pitch():
    r=reply("Thanks. That's interesting.")
    result=review_intent_cta(
        account=A,reply=r,model_result=model("problem_discovery",r),
        suppression_cleared=True,
    )
    assert result["decision"]=="HOLD_CORROBORATION"
    assert result["cta_draft"] is None


@pytest.mark.parametrize("body",[
    "Thanks for sharing. On Mon, 12 October 2026 wrote:\nHow much is the Technical Search Audit?",
    "Thanks, that helps.\n> Send me the price for the Technical Search Audit.",
    "Not interested in the Technical Search Audit, thanks.",
    "We need help but not right now.",
])
def test_quoted_context_rejection_or_negative_overrides_buy_model(body):
    r=reply(body)
    r.update(explicit_product_request_verified=True,
             requested_product_code="technical_search_audit")
    result=review_intent_cta(
        account=A,reply=r,
        model_result=model("explicit_product_purchase_request",r),
        suppression_cleared=True,
    )
    assert result["review_eligible"] is False
    assert result["cta_draft"] is None


@pytest.mark.parametrize("field,wrong",[
    ("tenant_id","another-tenant"),("prospect_id","wrong-prospect"),
    ("original_outbound_intent_id","wrong-intent"),
    ("sender_address","other@company.com"),
    ("direction","outbound"),("synthetic",True),
    ("provider_authenticated",False),
    ("same_thread_verified",False),
    ("counterpart_identity_verified",False),
    ("reply_id",None),
])
def test_unauthenticated_mismatched_or_synthetic_evidence_holds(field,wrong):
    r=reply("Could you send us a written scope?")
    m=model("solution_evaluation",r)
    r[field]=wrong
    result=review_intent_cta(account=A,reply=r,model_result=m,
                             suppression_cleared=True)
    assert result["decision"]=="HOLD_SOURCE"
    assert result["send_authorized"] is False


def test_unchecked_suppression_never_causes_cta():
    r=reply("How does this work?")
    result=review_intent_cta(account=A,reply=r,
                             model_result=model("solution_evaluation",r))
    assert result["decision"]=="HOLD_SUPPRESSION"
    assert result["cta_draft"] is None


def test_no_model_returns_hold_even_when_text_looks_commercial():
    r=reply("Please send me a scope?")
    result=review_intent_cta(account=A,reply=r,
                             model_result=None,suppression_cleared=True)
    assert result["decision"]=="HOLD_MODEL"


@pytest.mark.parametrize("corrupt",[
    {"confidence":.52},
    {"confidence":nan},
    {"confidence":True},
    {"source_ref":"canonical:reply:other"},
    {"state_ref":"canonical:reply:other"},
    {"execution_authority":"send"},
    {"shadow_only":False},
    {"label":"unknown"},
    {"provider_key":""},
])
def test_low_confidence_invalid_or_unbound_model_cannot_approve(corrupt):
    r=reply("Could you send us the written scope?")
    m=model("solution_evaluation",r)
    m=TypedDecisionResult(**{**m.__dict__,**corrupt})
    out=review_intent_cta(
        account=A,reply=r,model_result=m,suppression_cleared=True,
    )
    assert out["decision"]=="HOLD_MODEL"
    assert out["send_authorized"] is False


def test_model_result_bound_to_exact_inbound_text_not_stale_changed_message():
    r=reply("Could you send us the written scope?")
    m=model("solution_evaluation",r)
    r["body_text"]="Could you show the scope for a different issue?"
    result=review_intent_cta(account=A,reply=r,
                             model_result=m,suppression_cleared=True)
    assert result["decision"]=="HOLD_MODEL"


def test_explicit_purchase_model_without_exact_product_verified_holds():
    r=reply("How much does the Technical Search Audit cost?",
            "pricing_question")
    out=review_intent_cta(account=A,reply=r,
        model_result=model("explicit_product_purchase_request",r),
        suppression_cleared=True)
    assert out["decision"]=="HOLD_PRODUCT_BINDING"
    r["explicit_product_request_verified"]=True
    r["requested_product_code"]="search_opportunity_map"
    out=review_intent_cta(account=A,reply=r,
        model_result=model("explicit_product_purchase_request",r),
        suppression_cleared=True)
    assert out["decision"]=="HOLD_PRODUCT_BINDING"


def test_no_intent_label_is_not_a_cta():
    r=reply()
    out=review_intent_cta(account=A,reply=r,
        model_result=model("no_purchase_intent",r),suppression_cleared=True)
    assert out["decision"]=="WAIT" and out["cta_draft"] is None


def test_original_outbound_planner_now_surfaces_a_review_cta_without_send():
    r=reply("Could you send us the written scope you have in mind?")
    m=model("solution_evaluation",r)
    p=plan_outbound_account(A,replies=[r],intent_decision=m,
                            canonical_suppression_cleared=True)
    assert p["action_type"]=="HANDOFF_TO_CLOSER"
    assert p["relationship_stage"]=="CONVERSATION"
    assert p["intent_cta_review"]["cta_tier"]=="WRITTEN_SCOPE"
    assert p["execution_authority"]=="none"
    assert p["cta_allowed"] is False
    assert p["intent_cta_review"]["send_authorized"] is False


def test_planner_suppression_and_latest_unverified_reply_win():
    r=reply("Can you send us a scope?")
    m=model("solution_evaluation",r)
    p=plan_outbound_account(
        A,replies=[r],intent_decision=m,
        suppressions=[{"status":"suppressed"}],
        canonical_suppression_cleared=True,
    )
    assert p["action_type"]=="SUPPRESS"
    q=deepcopy(r)
    q["reply_id"]="new-unverified-reply"
    q["provider_authenticated"]=False
    p=plan_outbound_account(
        A,replies=[r,q],intent_decision=m,
        canonical_suppression_cleared=True,
    )
    assert p["action_type"]=="WAIT"


def test_prior_unsubscribe_cannot_be_overridden_by_a_later_positive():
    r=reply("Can you send the scope?")
    p=plan_outbound_account(
        A,replies=[
            {"classification":"unsubscribe","reply_id":"old-opt-out"},r
        ],intent_decision=model("solution_evaluation",r),
        canonical_suppression_cleared=True,
    )
    assert p["action_type"]=="SUPPRESS"


def test_existing_three_prospect_adapter_surfaces_intent_review_without_fabricating_id():
    r=reply("Can you send us the written scope?")
    m=model("solution_evaluation",r)
    # Research-only prospect: no canonical IDs. Never self-promote.
    out=review_candidate(PROSPECTS[0],replies=[r],
        model_decision=m,canonical_suppression_cleared=True)
    assert out["intent_cta_review"]["decision"]=="HOLD_SOURCE"
    assert out["send_authorized"] is False
    # Once the *caller* supplies already canonical-verified IDs, the review
    # can become eligible. No real prospect IDs are created by this test.
    candidate={**PROSPECTS[0],
        "tenant_id":A["tenant_id"],"prospect_id":A["prospect_id"],
        "original_outbound_intent_id":A["original_outbound_intent_id"]}
    out=review_candidate(candidate,replies=[r],
        model_decision=m,canonical_suppression_cleared=True)
    assert out["intent_cta_review"]["cta_tier"]=="WRITTEN_SCOPE"
    assert out["send_authorized"] is False


def test_no_automated_nurture_or_money_changed():
    r=reply("We need help understanding our local searches.")
    out=review_intent_cta(account=A,reply=r,
         model_result=model("problem_discovery",r),suppression_cleared=True)
    assert out["meeting_booked"] is False
    assert out["outbound_sent"] is False
    assert out["execution_authority"]=="none"
    assert out["financial_action"] is False

def test_ai_can_surface_human_discovery_when_basic_reply_classifier_says_other():
    r=reply("We need help understanding our new service-area searches.",
            classification="other")
    decision=model("problem_discovery",r)
    plan=plan_outbound_account(
        A,replies=[r],intent_decision=decision,
        canonical_suppression_cleared=True,
    )
    assert plan["action_type"]=="WAIT"
    assert plan["relationship_stage"]=="ENGAGED"
    assert plan["intent_cta_review"]["cta_tier"]=="DISCOVERY_QUESTION"
    assert plan["intent_cta_review"]["decision"]=="CTA_DRAFT_FOR_HUMAN_REVIEW"
    assert plan["intent_cta_review"]["send_authorized"] is False


def test_no_model_for_unclassified_reply_never_unlocks_cta():
    r=reply("We need help understanding local demand.",classification="other")
    plan=plan_outbound_account(
        A,replies=[r],canonical_suppression_cleared=True,
    )
    assert plan["action_type"]=="WAIT"
    assert plan["intent_cta_review"]["decision"]=="HOLD_MODEL"
    assert plan["intent_cta_review"]["cta_draft"] is None


@pytest.mark.parametrize("reply_classification",[
    "negative","later","unsubscribe","ooo","wrong_person",
])
def test_noncommercial_reply_stops_ai_cta(reply_classification):
    r=reply("We need help understanding local demand.",
            classification=reply_classification)
    m=model("problem_discovery",r)
    plan=plan_outbound_account(
        A,replies=[r],intent_decision=m,
        canonical_suppression_cleared=True,
    )
    assert plan["action_type"] in ("SUPPRESS","WAIT","RESEARCH")
    assert "intent_cta_review" not in plan or not plan["intent_cta_review"]["review_eligible"]

def test_supplied_resident_typed_provider_can_trigger_scoped_cta_review():
    from empire_os.rapport_intent_cta import evaluate_intent_with_existing_provider
    r=reply("Please send us the written scope.",classification="question")
    class FakeResident:
        def __init__(self):self.calls=[]
        def evaluate(self,req):
            self.calls.append(req)
            assert req.task_key=="reply_purchase_intent"
            assert req.state["product_code"]=="technical_search_audit"
            assert "written scope" in req.state["current_inbound_message"]
            return model("solution_evaluation",r)
    provider=FakeResident()
    out=evaluate_intent_with_existing_provider(
        account=A,reply=r,provider=provider,suppression_cleared=True)
    assert len(provider.calls)==1
    assert out["cta_tier"]=="WRITTEN_SCOPE"
    assert out["send_authorized"] is False


def test_no_authenticated_sender_or_suppression_means_no_model_call():
    from empire_os.rapport_intent_cta import evaluate_intent_with_existing_provider
    class MustNotCall:
        def evaluate(self,_):raise AssertionError("Model never should run")
    r=reply("Please send me the scope.")
    out=evaluate_intent_with_existing_provider(
        account=A,reply=r,provider=MustNotCall())
    assert out["decision"]=="HOLD_SUPPRESSION"
    r["sender_address"]="fake@another-tenant.example"
    out=evaluate_intent_with_existing_provider(
        account=A,reply=r,provider=MustNotCall(),suppression_cleared=True)
    assert out["decision"]=="HOLD_SOURCE"


def test_resident_inference_exception_redacted_and_no_retry():
    from empire_os.rapport_intent_cta import evaluate_intent_with_existing_provider
    r=reply("Please send the scope.")
    class Provider:
        calls=0
        def evaluate(self,request):
            self.calls+=1
            raise RuntimeError("SECRET_UNTRUSTED_PROVIDER_DIAGNOSTIC")
    provider=Provider()
    out=evaluate_intent_with_existing_provider(
        account=A,reply=r,provider=provider,suppression_cleared=True)
    assert out["decision"]=="HOLD_MODEL"
    assert provider.calls==1
    assert "SECRET" not in str(out)
