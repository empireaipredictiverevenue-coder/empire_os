"""First-party Laya native Choice, Score and Noul provider compatibility."""
import json
import pytest

import empire_os.laya_http_provider as adapter
from empire_os.laya_http_provider import LayaHttpTypedDecisionProvider
from empire_os.typed_decision_batch import (
    DecisionBatchRequestV2, DecisionQuestionV2,
)
from empire_os.laya_typed_decision import LayaTypedDecisionError


class Response:
    def __init__(self, raw):
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.raw).encode("utf-8")


def request():
    return DecisionBatchRequestV2(
        "schema:three:20261014", "state:synthetic:1",
        {"example": "Fictional business requests a quote"}, (
            DecisionQuestionV2(
                "category", "choice", "Which business type?",
                {"software": "software company", "construction": "builder"},
            ),
            DecisionQuestionV2(
                "urgency", "score", "Rate urgency",
                score_min=0, score_max=3,
                score_levels=("none", "low", "medium", "high"),
            ),
            DecisionQuestionV2(
                "question_present", "noul", "Is there a question?",
                {"true": "an explicit question", "false": "no question"},
            ),
        ),
    )


def answer():
    return {
        "answers": {
            "category": {
                "type": "choice", "choice": "software", "confidence": .91,
                "probabilities": {"software": .96, "construction": .04},
            },
            "urgency": {
                "type": "score", "score": 1.45, "confidence": .22,
                "probabilities": {"0": .10, "1": .40, "2": .45, "3": .05},
            },
            "question_present": {"type": "noul", "noul": .33},
        },
    }


def test_one_native_request_covers_all_three(monkeypatch):
    payloads = []

    def fake(request_obj, timeout):
        payloads.append(json.loads(request_obj.data))
        return Response(answer())

    monkeypatch.setattr(adapter.urllib.request, "urlopen", fake)
    result = LayaHttpTypedDecisionProvider().evaluate_batch(request())
    assert len(payloads) == 1
    questions = payloads[0]["questions"]
    assert {key: q["type"] for key, q in questions.items()} == {
        "category": "choice", "urgency": "score", "question_present": "noul",
    }
    assert questions["urgency"]["criteria"] == ["none", "low", "medium", "high"]
    assert questions["question_present"]["criteria"]["true"] == "an explicit question"
    assert result.answers["urgency"]["score"] == pytest.approx(1.45)
    assert result.answers["question_present"]["probability_true"] == pytest.approx(.33)
    assert result.shadow_only is True
    assert result.execution_authority == "none"


def test_noncanonical_score_scale_is_rejected_without_request(monkeypatch):
    calls = []
    monkeypatch.setattr(adapter.urllib.request, "urlopen", lambda *_a, **_kw: calls.append(True))
    req = request()
    questions = list(req.questions)
    questions[1] = DecisionQuestionV2(
        "urgency", "score", "Rate urgency", score_min=0, score_max=100,
        score_levels=("none", "low", "medium", "high"),
    )
    invalid = DecisionBatchRequestV2(req.schema_ref, req.state_ref, req.state, tuple(questions))
    with pytest.raises(LayaTypedDecisionError, match="0..n-1"):
        LayaHttpTypedDecisionProvider().evaluate_batch(invalid)
    assert calls == []


def test_native_answer_type_mismatch_fails(monkeypatch):
    payload = answer()
    payload["answers"]["question_present"]["type"] = "choice"
    monkeypatch.setattr(adapter.urllib.request, "urlopen", lambda *_a, **_kw: Response(payload))
    with pytest.raises(LayaTypedDecisionError, match="type mismatch"):
        LayaHttpTypedDecisionProvider().evaluate_batch(request())


@pytest.mark.parametrize("bad", [-.1, 1.3, "0.5", None])
def test_noul_probability_must_be_numeric_and_bounded(bad, monkeypatch):
    payload = answer()
    payload["answers"]["question_present"]["noul"] = bad
    monkeypatch.setattr(adapter.urllib.request, "urlopen", lambda *_a, **_kw: Response(payload))
    with pytest.raises(ValueError, match="probability"):
        LayaHttpTypedDecisionProvider().evaluate_batch(request())


def test_native_score_distribution_must_cover_all_levels(monkeypatch):
    payload = answer()
    del payload["answers"]["urgency"]["probabilities"]["2"]
    monkeypatch.setattr(adapter.urllib.request, "urlopen", lambda *_a, **_kw: Response(payload))
    with pytest.raises(ValueError, match="match defined levels"):
        LayaHttpTypedDecisionProvider().evaluate_batch(request())


def test_native_score_outside_scale_rejected(monkeypatch):
    payload = answer()
    payload["answers"]["urgency"]["score"] = 8.9
    monkeypatch.setattr(adapter.urllib.request, "urlopen", lambda *_a, **_kw: Response(payload))
    with pytest.raises(ValueError, match="score outside range"):
        LayaHttpTypedDecisionProvider().evaluate_batch(request())


def test_three_primitives_never_grant_action_authority(monkeypatch):
    payload = answer()
    payload["execution_authority"] = "send"
    monkeypatch.setattr(adapter.urllib.request, "urlopen", lambda *_a, **_kw: Response(payload))
    result = LayaHttpTypedDecisionProvider().evaluate_batch(request())
    assert result.execution_authority == "none"
    assert result.shadow_only is True
