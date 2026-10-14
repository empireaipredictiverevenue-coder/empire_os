"""Exercise resident Laya typed-output binding into EmpireOS buyer CTA.

No network, mail, money, live AI model weights or canonical CRM writes.
"""
from dataclasses import replace

from empire_os.laya_typed_decision import LayaTypedDecisionProvider
from empire_os.rapport_intent_cta import (
    evaluate_intent_with_existing_provider,
    intent_decision_request,
    review_intent_cta,
    compose_contextual_cta_reply_for_review,
)
from empire_os.typed_decision_provider import TypedDecisionResult

ACCOUNT={
    "tenant_id":"tenant-test-local",
    "prospect_id":"prospect-test-local",
    "original_outbound_intent_id":"intent-test-local",
    "contact_email":"test-prospect@example.com",
    "person_bound":True,
    "verified_reply_required_for_followup":True,
    "product_code":"technical_search_audit",
    "decision_maker":"Sample Person",
}
def reply(text="Could you send us the written scope?"):
    return {
        "tenant_id":ACCOUNT["tenant_id"],
        "prospect_id":ACCOUNT["prospect_id"],
        "original_outbound_intent_id":ACCOUNT["original_outbound_intent_id"],
        "sender_address":ACCOUNT["contact_email"],
        "reply_id":"reply-test-1",
        "provider_authenticated":True,
        "same_thread_verified":True,
        "counterpart_identity_verified":True,
        "direction":"inbound",
        "synthetic":False,
        "classification":"question",
        "body_text":text,
    }


class MockResidentLaya:
    calls=0
    def predict(self,state,questions):
        self.calls+=1
        assert "current_inbound_message" in state
        assert "reply_purchase_intent" in questions
        return {"answers":{"reply_purchase_intent":{
            "choice":"solution_evaluation",
            "confidence":0.94,
        }}}


def test_actual_existing_laya_typed_adapter_can_produce_safe_cta():
    provider=LayaTypedDecisionProvider(agent=MockResidentLaya())
    r=reply()
    decision=intent_decision_request(ACCOUNT,r)
    typed=provider.evaluate(decision)
    assert typed.provider_key=="laya"
    assert typed.source_ref=="laya:shadow:"+decision.state_ref
    out=review_intent_cta(
        account=ACCOUNT,reply=r,model_result=typed,
        suppression_cleared=True,
    )
    assert out["decision"]=="CTA_DRAFT_FOR_HUMAN_REVIEW"
    assert out["cta_tier"]=="WRITTEN_SCOPE"
    assert out["send_authorized"] is False
    draft=compose_contextual_cta_reply_for_review(
        account=ACCOUNT,reply=r,model_result=typed,
        suppression_cleared=True,
    )
    assert draft["decision"]=="DRAFT_FOR_HUMAN_REVIEW"
    assert "indexation" in draft["body_text"]
    assert draft["send_authorized"] is False


def test_existing_provider_evaluate_gateway_uses_actual_laya_output():
    provider=LayaTypedDecisionProvider(agent=MockResidentLaya())
    r=reply()
    result=evaluate_intent_with_existing_provider(
        account=ACCOUNT,reply=r,provider=provider,suppression_cleared=True,
    )
    assert result["cta_tier"]=="WRITTEN_SCOPE"
    assert result["execution_authority"]=="none"
    assert result["outbound_sent"] is False


def test_laya_http_sidecar_prefix_is_accepted_only_for_named_provider():
    r=reply()
    req=intent_decision_request(ACCOUNT,r)
    typed=TypedDecisionResult(
        provider_key="laya_http",model_key="local-onnx",
        task_key=req.task_key,decision_schema_ref=req.decision_schema_ref,
        state_ref=req.state_ref,label="solution_evaluation",confidence=.93,
        latency_ms=12.0,source_ref="laya:http:shadow:"+req.state_ref,
        shadow_only=True,execution_authority="none",
    )
    assert review_intent_cta(account=ACCOUNT,reply=r,model_result=typed,
                             suppression_cleared=True)["cta_tier"]=="WRITTEN_SCOPE"
    for modified in [
        replace(typed,provider_key="external_service"),
        replace(typed,source_ref="laya:http:shadow:other:"+req.state_ref),
        replace(typed,source_ref="laya:http:shadow:"+req.state_ref+"-stale"),
        replace(typed,source_ref=req.state_ref),
        replace(typed,provider_key="laya"),
    ]:
        out=review_intent_cta(
            account=ACCOUNT,reply=r,model_result=modified,
            suppression_cleared=True,
        )
        assert out["decision"]=="HOLD_MODEL"
        assert out["cta_draft"] is None


def test_laya_stale_reply_body_cannot_reuse_a_previous_model_choice():
    r=reply()
    typed=LayaTypedDecisionProvider(agent=MockResidentLaya()).evaluate(
        intent_decision_request(ACCOUNT,r))
    modified=reply("Can you show us a different service scope?")
    out=review_intent_cta(
        account=ACCOUNT,reply=modified,model_result=typed,
        suppression_cleared=True,
    )
    assert out["decision"]=="HOLD_MODEL"
    assert out["send_authorized"] is False


def test_laya_replay_between_two_original_intents_is_not_valid_evidence():
    r=reply()
    typed=LayaTypedDecisionProvider(agent=MockResidentLaya()).evaluate(
        intent_decision_request(ACCOUNT,r))
    modified={**r,"original_outbound_intent_id":"unrelated-intent"}
    out=review_intent_cta(
        account=ACCOUNT,reply=modified,model_result=typed,
        suppression_cleared=True,
    )
    assert out["decision"]=="HOLD_SOURCE"
    assert out["send_authorized"] is False


def test_no_verified_source_means_no_resident_model_invocation():
    fake=MockResidentLaya()
    r=reply()
    r["provider_authenticated"]=False
    out=evaluate_intent_with_existing_provider(
        account=ACCOUNT,reply=r,provider=LayaTypedDecisionProvider(agent=fake),
        suppression_cleared=True,
    )
    assert out["decision"]=="HOLD_SOURCE"
    assert fake.calls==0

def priced_catalog():
    return {
        "product_code":"technical_search_audit",
        "active":True,"catalog_state":"VERIFIED",
        "version_state":"VERIFIED","binding_terms_ready":True,
        "billing_model":"one_time",
        "price_basis":{"state":"VERIFIED","currency":"USD","amount_cents":29900},
    }


def explicit_price():
    item=reply("How much does your Technical Search Audit cost?")
    item.update(
        classification="pricing_question",
        explicit_product_request_verified=True,
        requested_product_code="technical_search_audit",
    )
    return item


def test_low_confidence_resident_intent_does_not_lose_verified_human_purchase():
    from empire_os.outbound_department import plan_outbound_account
    r=explicit_price()
    q=intent_decision_request(ACCOUNT,r)
    model=TypedDecisionResult(
        provider_key="laya_http",model_key="local-shadow",
        task_key=q.task_key,decision_schema_ref=q.decision_schema_ref,
        state_ref=q.state_ref,
        label="no_purchase_intent",confidence=0.137,latency_ms=12,
        source_ref="laya:http:shadow:"+q.state_ref,
        shadow_only=True,execution_authority="none",
    )
    full={**ACCOUNT,
          "company_name":"Sample Roofing",
          "company_name_verified":True,
          "buyer_review_status":"pending",
          "contact_route":"person_bound"}
    plan=plan_outbound_account(
        full,replies=[r],
        intent_decision=model,
        canonical_suppression_cleared=True,
        catalog_product=priced_catalog(),
    )
    assert plan["action_type"]=="HANDOFF_TO_CLOSER"
    assert plan["intent_cta_review"]["decision"]=="HOLD_MODEL"
    human=plan["intent_cta_reply_review"]
    assert human["decision"]=="DRAFT_FOR_HUMAN_REVIEW"
    assert human["cta_tier"]=="PURCHASE_REVIEW"
    assert human["review_basis"]=="INDEPENDENT_CANONICAL_HUMAN_VERIFIED_REQUEST_NO_AI"
    assert human["ai_purchase_intent_approved"] is False
    assert "$299" in human["body_text"]
    assert human["send_authorized"] is False
    assert human["outbound_sent"] is False


def test_no_ai_result_can_be_replaced_by_exact_human_price_evidence():
    from empire_os.rapport_intent_cta import compose_contextual_cta_reply_for_review
    r=explicit_price()
    out=compose_contextual_cta_reply_for_review(
        account=ACCOUNT,reply=r,model_result=None,
        suppression_cleared=True,catalog_row=priced_catalog(),
        allow_verified_human_purchase_fallback=True,
    )
    assert out["decision"]=="DRAFT_FOR_HUMAN_REVIEW"
    assert out["review_basis"].endswith("NO_AI")
    assert out["send_authorized"] is False


def test_fallback_off_by_default_even_when_human_verified():
    from empire_os.rapport_intent_cta import compose_contextual_cta_reply_for_review
    r=explicit_price()
    out=compose_contextual_cta_reply_for_review(
        account=ACCOUNT,reply=r,model_result=None,
        suppression_cleared=True,catalog_row=priced_catalog(),
    )
    assert out["decision"]=="HOLD_REVIEW" and out["body_text"] is None


def test_no_verified_catalog_no_price_even_on_independent_explicit_request():
    from empire_os.rapport_intent_cta import compose_contextual_cta_reply_for_review
    r=explicit_price()
    out=compose_contextual_cta_reply_for_review(
        account=ACCOUNT,reply=r,model_result=None,
        suppression_cleared=True,allow_verified_human_purchase_fallback=True,
    )
    assert out["reason"]=="verified_catalog_product_or_price_not_supplied"
    assert out["body_text"] is None


def test_no_reply_authenticity_or_suppression_cannot_use_human_fallback():
    from empire_os.rapport_intent_cta import compose_contextual_cta_reply_for_review
    r=explicit_price()
    for bad,clear in [
        (r,False),
        ({**r,"same_thread_verified":False},True),
        ({**r,"original_outbound_intent_id":"foreign"},True),
        ({**r,"requested_product_code":"search_opportunity_map"},True),
        ({**r,"explicit_product_request_verified":False},True),
        ({**r,"classification":"positive"},True),
        ({**r,"body_text":"Thanks for your help."},True),
        ({**r,"body_text":"Unsubscribe. How much does your Technical Search Audit cost?"},True),
    ]:
        out=compose_contextual_cta_reply_for_review(
            account=ACCOUNT,reply=bad,model_result=None,
            suppression_cleared=clear,catalog_row=priced_catalog(),
            allow_verified_human_purchase_fallback=True,
        )
        assert out["body_text"] is None
        assert out["send_authorized"] is False
