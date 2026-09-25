import pytest

from empire_os.laya_typed_decision import (
    LayaTypedDecisionError,
    LayaTypedDecisionProvider,
)
from empire_os.typed_decision_provider import (
    TypedDecisionRequest,
    review_typed_decision_result,
)


def request(*, risk_class="low"):
    return TypedDecisionRequest(
        task_key="reply_classification",
        decision_schema_ref="schema:reply:v2",
        state_ref="gmail:message:1",
        state={
            "subject": "Re: capacity",
            "body": "Send the one-page example.",
        },
        allowed_labels=(
            "positive",
            "question",
            "objection",
            "later",
            "negative",
            "unsubscribe",
            "other",
        ),
        risk_class=risk_class,
        instructions="Classify the buyer reply by commercial intent.",
        label_criteria={
            "positive": "explicit interest or request to continue",
            "question": "asks for information without clear buying intent",
            "objection": "raises a concern or blocking condition",
            "later": "asks to revisit at a future time",
            "negative": "declines without asking to unsubscribe",
            "unsubscribe": "asks to stop future contact",
            "other": "none of the other labels fit",
        },
    )


class FakeLaya:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def predict(self, state, questions):
        self.calls.append((state, questions))
        return {
            "answers": {
                "reply_classification": self.answer,
            }
        }


def test_laya_adapter_maps_empire_choice_schema_and_stays_shadow_only():
    agent = FakeLaya({
        "choice": "positive",
        "confidence": 0.93,
        "probabilities": {
            "positive": 0.93,
            "question": 0.04,
            "objection": 0.01,
            "later": 0.01,
            "negative": 0.005,
            "unsubscribe": 0.003,
            "other": 0.002,
        },
    })
    provider = LayaTypedDecisionProvider(agent=agent)

    result = provider.evaluate(request())

    assert result.provider_key == "laya"
    assert result.label == "positive"
    assert result.confidence == pytest.approx(0.93)
    assert result.shadow_only is True
    assert result.execution_authority == "none"

    state, questions = agent.calls[0]
    assert state["body"] == "Send the one-page example."
    choice = questions["reply_classification"]
    assert choice["type"] == "choice"
    assert choice["criteria"]["unsubscribe"] == "asks to stop future contact"


def test_laya_adapter_accepts_probability_when_confidence_missing():
    agent = FakeLaya({
        "choice": "later",
        "probabilities": {
            "later": 0.81,
            "positive": 0.19,
        },
    })
    result = LayaTypedDecisionProvider(agent=agent).evaluate(request())
    assert result.label == "later"
    assert result.confidence == pytest.approx(0.81)


def test_laya_adapter_rejects_disallowed_label():
    agent = FakeLaya({
        "choice": "send_money",
        "confidence": 0.99,
    })
    with pytest.raises(LayaTypedDecisionError, match="disallowed"):
        LayaTypedDecisionProvider(agent=agent).evaluate(request())


def test_laya_adapter_rejects_more_than_twenty_choice_labels():
    labels = tuple(f"label_{i}" for i in range(21))
    req = TypedDecisionRequest(
        task_key="too_many",
        decision_schema_ref="schema:many:v1",
        state_ref="state:many",
        state={"body": "x"},
        allowed_labels=labels,
        label_criteria={label: label for label in labels},
    )
    with pytest.raises(LayaTypedDecisionError, match="20 labels"):
        LayaTypedDecisionProvider(
            agent=FakeLaya({"choice": "label_0", "confidence": 0.9})
        ).evaluate(req)


def test_laya_high_risk_result_still_escalates_under_empire_policy():
    agent = FakeLaya({
        "choice": "positive",
        "confidence": 0.99,
    })
    req = request(risk_class="high")
    result = LayaTypedDecisionProvider(agent=agent).evaluate(req)
    reviewed = review_typed_decision_result(
        request=req,
        result=result,
        confidence_threshold=0.80,
    )
    assert reviewed["requires_escalation"] is True
    assert reviewed["controls_live_route"] is False
    assert reviewed["execution_performed"] is False
