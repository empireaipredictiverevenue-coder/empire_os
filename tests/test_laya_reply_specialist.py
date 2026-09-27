from empire_os.laya_reply_specialist import (
    LayaReplySpecialistPolicy,
    observed_laya_benchmark,
    review_laya_reply_specialist,
)
from empire_os.typed_decision_provider import (
    TypedDecisionRequest,
    TypedDecisionResult,
)


LABELS = (
    "positive",
    "question",
    "objection",
    "later",
    "negative",
    "unsubscribe",
    "other",
)


def request(*, risk_class="low"):
    return TypedDecisionRequest(
        task_key="reply_classification",
        decision_schema_ref="schema:reply:v2",
        state_ref="gmail:message:1",
        state={"body": "example"},
        allowed_labels=LABELS,
        risk_class=risk_class,
    )


def result(label, confidence):
    return TypedDecisionResult(
        provider_key="laya_http",
        model_key="convaiinnovations/laya:onnx",
        task_key="reply_classification",
        decision_schema_ref="schema:reply:v2",
        state_ref="gmail:message:1",
        label=label,
        confidence=confidence,
        latency_ms=670.29,
        source_ref="laya:http:shadow:gmail:message:1",
        shadow_only=True,
        execution_authority="none",
    )


def test_high_confidence_unsubscribe_is_specialist_shadow_candidate():
    review = review_laya_reply_specialist(
        request=request(),
        result=result("unsubscribe", 0.9914),
    )
    assert review["accepted_for_shadow_analysis"] is True
    assert review["requires_escalation"] is False
    assert review["controls_live_route"] is False
    assert review["may_send_outbound"] is False
    assert review["may_mutate_contact_state"] is False


def test_high_confidence_negative_is_specialist_shadow_candidate():
    review = review_laya_reply_specialist(
        request=request(),
        result=result("negative", 0.8977),
    )
    assert review["accepted_for_shadow_analysis"] is True


def test_positive_is_escalated_even_when_confident():
    review = review_laya_reply_specialist(
        request=request(),
        result=result("positive", 0.99),
    )
    assert review["accepted_for_shadow_analysis"] is False
    assert review["reason"] == "label_outside_observed_specialist_lane"


def test_low_confidence_unsubscribe_is_escalated():
    review = review_laya_reply_specialist(
        request=request(),
        result=result("unsubscribe", 0.70),
    )
    assert review["requires_escalation"] is True
    assert review["reason"] == "below_specialist_confidence_threshold"


def test_high_risk_always_escalates():
    review = review_laya_reply_specialist(
        request=request(risk_class="high"),
        result=result("unsubscribe", 0.99),
    )
    assert review["requires_escalation"] is True
    assert review["reason"] == "risk_requires_escalation"


def test_observed_benchmark_snapshot_matches_live_evidence():
    evidence = observed_laya_benchmark()
    assert evidence["cases"] == 6
    assert evidence["raw_accuracy"] == 0.6667
    assert evidence["safe_accuracy"] == 1.0
    assert evidence["unsafe_accepts"] == 0
    assert evidence["escalation_rate"] == 0.6667
    assert evidence["latency_ms_p50"] == 670.29
    assert evidence["status"] == "shadow_specialist_only"
    assert evidence["production_authority"] == "none"


def test_policy_threshold_is_not_silently_lowered():
    policy = LayaReplySpecialistPolicy()
    assert policy.confidence_threshold == 0.85
    assert policy.accepted_labels == frozenset({"negative", "unsubscribe"})
