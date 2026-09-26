import pytest

from empire_os.typed_decision_provider import (
    DisabledTypedDecisionProvider,
    TypedDecisionRequest,
    TypedDecisionResult,
    review_typed_decision_result,
)


def request(risk="low"):
    return TypedDecisionRequest(
        task_key="reply_classification",
        decision_schema_ref="schema:reply:v1",
        state_ref="state:1",
        state={"text_ref": "message:1"},
        allowed_labels=("positive", "negative", "unsubscribe"),
        risk_class=risk,
    )


def result(confidence=.9):
    return TypedDecisionResult(
        provider_key="jev",
        model_key="system-one",
        task_key="reply_classification",
        decision_schema_ref="schema:reply:v1",
        state_ref="state:1",
        label="positive",
        confidence=confidence,
        latency_ms=150,
        source_ref="shadow:1",
    )


def test_disabled_provider_fails_closed():
    with pytest.raises(RuntimeError, match="not_activated"):
        DisabledTypedDecisionProvider().evaluate(request())


def test_result_review_never_controls_live_route():
    reviewed = review_typed_decision_result(
        request=request(),
        result=result(.9),
        confidence_threshold=.8,
    )
    assert reviewed["requires_escalation"] is False
    assert reviewed["controls_live_route"] is False
    assert reviewed["execution_performed"] is False


def test_low_confidence_escalates():
    reviewed = review_typed_decision_result(
        request=request(),
        result=result(.55),
        confidence_threshold=.8,
    )
    assert reviewed["requires_escalation"] is True


def test_high_risk_always_escalates_even_high_confidence():
    reviewed = review_typed_decision_result(
        request=request("high"),
        result=result(.99),
        confidence_threshold=.8,
    )
    assert reviewed["requires_escalation"] is True


def test_disallowed_label_rejected():
    bad = TypedDecisionResult(
        provider_key="jev",
        model_key="system-one",
        task_key="reply_classification",
        decision_schema_ref="schema:reply:v1",
        state_ref="state:1",
        label="send_money",
        confidence=.99,
        latency_ms=100,
        source_ref="shadow:2",
    )
    with pytest.raises(ValueError, match="label not allowed"):
        review_typed_decision_result(
            request=request(),
            result=bad,
            confidence_threshold=.8,
        )


def test_label_criteria_must_match_allowed_labels():
    bad = TypedDecisionRequest(
        task_key="reply_classification",
        decision_schema_ref="schema:reply:v1",
        state_ref="state:criteria",
        state={"text_ref": "message:1"},
        allowed_labels=("positive", "negative"),
        label_criteria={"positive": "interest"},
    )
    with pytest.raises(ValueError, match="exactly match"):
        bad.validate()
