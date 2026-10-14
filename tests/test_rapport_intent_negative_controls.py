"""Synthetic buying-intent safety smoke-test fixture.

This file is not a live provider evaluation.
"""
from pathlib import Path
import json

from empire_os.rapport_intent_cta import (
    _corroborates, _buyer_text, LABELS,
)
from empire_os.typed_decision_eval import evaluate_provider_outputs

CASES=Path(__file__).resolve().parents[1] / "benchmarks/rapport_intent_cases.jsonl"


def test_synthetic_cases_coverage_and_no_unsafe_positive_purchase():
    rows=[json.loads(v) for v in CASES.read_text().splitlines() if v.strip()]
    assert len(rows)>=40
    assert {r["expected_label"] for r in rows}==set(LABELS)
    assert len({r["case_id"] for r in rows})==len(rows)
    assert all(r["synthetic"] is True for r in rows)
    false_accepts=[]
    for r in rows:
        if (r["expected_label"]!="explicit_product_purchase_request"
            and _corroborates(
                "explicit_product_purchase_request",
                _buyer_text(r["body_text"]), r["product_code"],
            )):
            false_accepts.append(r["case_id"])
    assert not false_accepts, false_accepts


def test_high_confidence_purchase_model_and_human_fallback_cannot_promote_negative_controls():
    from empire_os.rapport_intent_cta import (
        intent_decision_request, review_intent_cta,
        review_verified_purchase_without_ai,
    )
    from empire_os.typed_decision_provider import TypedDecisionResult

    rows=[json.loads(v) for v in CASES.read_text().splitlines() if v.strip()]
    account={
        "tenant_id":"tenant-fixture","prospect_id":"prospect-fixture",
        "original_outbound_intent_id":"sent-fixture",
        "contact_email":"fictional@example.com","product_code":"technical_search_audit",
        "person_bound":True,"verified_reply_required_for_followup":True,
    }
    for case in rows:
        if case["expected_label"]=="explicit_product_purchase_request":
            continue
        reply={
            "tenant_id":account["tenant_id"],"prospect_id":account["prospect_id"],
            "original_outbound_intent_id":account["original_outbound_intent_id"],
            "reply_id":case["case_id"],"sender_address":account["contact_email"],
            "direction":"inbound","synthetic":False,"provider_authenticated":True,
            "same_thread_verified":True,"counterpart_identity_verified":True,
            "body_text":case["body_text"],"classification":"pricing_question",
            "explicit_product_request_verified":True,
            "requested_product_code":account["product_code"],
        }
        req=intent_decision_request(account,reply)
        impossible_model=TypedDecisionResult(
            provider_key="offline-test",model_key="synthetic-not-a-model",
            task_key=req.task_key,decision_schema_ref=req.decision_schema_ref,
            state_ref=req.state_ref,label="explicit_product_purchase_request",
            confidence=.999,latency_ms=1,source_ref=req.state_ref,
            shadow_only=True,execution_authority="none",
        )
        ai=review_intent_cta(account=account,reply=reply,
                             model_result=impossible_model,
                             suppression_cleared=True)
        human=review_verified_purchase_without_ai(
            account=account,reply=reply,suppression_cleared=True)
        assert ai["decision"]!="CTA_DRAFT_FOR_HUMAN_REVIEW",case["case_id"]
        assert human["review_eligible"] is False,case["case_id"]


def test_existing_eval_engine_accepts_synthetic_gold_corpus_not_a_live_score():
    rows=[json.loads(v) for v in CASES.read_text().splitlines() if v.strip()]
    observations=[
        {
            "case_id":r["case_id"],"task_key":"reply_purchase_intent",
            "provider_key":"synthetic_fixture","model_key":"oracle_not_model",
            "ground_truth":r["expected_label"],"predicted":r["expected_label"],
            "confidence":0.99,"latency_ms":0.0,"input_tokens":None,
            "cost_cents":None,"source_ref":"synthetic:"+r["case_id"],
        }
        for r in rows
    ]
    report=evaluate_provider_outputs(observations,minimum_samples=40)
    assert report["available"] is True
    assert report["sample_count"]==len(rows)
    assert report["provider_activation"] is False
    assert report["production_routing"] is False
