"""Batch transport regression: local Laya may handle Choice only."""
import json
import pytest

import empire_os.laya_http_provider as adapter
from empire_os.laya_http_provider import LayaHttpTypedDecisionProvider
from empire_os.laya_typed_decision import LayaTypedDecisionError
from empire_os.typed_decision_batch import DecisionBatchRequestV2, DecisionQuestionV2


class Response:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.content).encode()


def batch(kind="choice"):
    q1 = DecisionQuestionV2(
        "industry", kind, "What industry?",
        {"roofing": "roofers", "software": "developers"} if kind == "choice" else (
            {"true": "Yes", "false": "No"} if kind == "noul" else {}
        ),
    )
    q2 = DecisionQuestionV2(
        "reply", "choice", "What reply type?",
        {"positive": "interested", "negative": "not interested"},
    )
    return DecisionBatchRequestV2("schema:gtm:2", "state:mock", {"data": "synthetic"}, (q1, q2))


def test_batched_choice_uses_one_shared_state_call(monkeypatch):
    seen = []

    def fake(req, timeout):
        seen.append(json.loads(req.data.decode()))
        return Response({
            "answers": {
                "industry": {
                    "choice": "roofing",
                    "probabilities": {"roofing": .8, "software": .2},
                },
                "reply": {
                    "choice": "positive",
                    "confidence": .65,
                },
            },
        })

    monkeypatch.setattr(adapter.urllib.request, "urlopen", fake)
    result = LayaHttpTypedDecisionProvider().evaluate_batch(batch())
    assert len(seen) == 1
    assert set(seen[0]["questions"]) == {"industry", "reply"}
    assert result.answers["industry"]["choice"] == "roofing"
    assert result.answers["industry"]["confidence"] == .8
    assert result.shadow_only is True
    assert result.execution_authority == "none"


@pytest.mark.parametrize("kind", ["score", "noul"])
def test_nonchoice_primitives_explicitly_held(kind, monkeypatch):
    calls = []
    monkeypatch.setattr(adapter.urllib.request, "urlopen", lambda *_args, **_kw: calls.append(True))
    with pytest.raises(LayaTypedDecisionError, match="choice only"):
        LayaHttpTypedDecisionProvider().evaluate_batch(batch(kind))
    assert calls == []


def test_disallowed_choice_from_sidecar_is_rejected(monkeypatch):
    monkeypatch.setattr(adapter.urllib.request, "urlopen", lambda *_a, **_kw: Response({
        "answers": {
            "industry": {"choice": "transfer_money", "confidence": 1},
            "reply": {"choice": "positive", "confidence": .95},
        },
    }))
    with pytest.raises(LayaTypedDecisionError, match="disallowed"):
        LayaHttpTypedDecisionProvider().evaluate_batch(batch())


def test_missing_answer_fails_closed(monkeypatch):
    monkeypatch.setattr(adapter.urllib.request, "urlopen", lambda *_a, **_kw: Response({
        "answers": {"industry": {"choice": "roofing", "confidence": .7}},
    }))
    with pytest.raises(LayaTypedDecisionError, match="answer missing"):
        LayaHttpTypedDecisionProvider().evaluate_batch(batch())


def test_bad_probability_distribution_fails_closed(monkeypatch):
    monkeypatch.setattr(adapter.urllib.request, "urlopen", lambda *_a, **_kw: Response({
        "answers": {
            "industry": {
                "choice": "roofing",
                "confidence": .9,
                "probabilities": {"roofing": .9, "software": .9},
            },
            "reply": {"choice": "positive", "confidence": .95},
        },
    }))
    with pytest.raises(ValueError, match="not normalized"):
        LayaHttpTypedDecisionProvider().evaluate_batch(batch())


def test_transport_failure_fails_closed(monkeypatch):
    def fail(*_args, **_kw):
        raise adapter.urllib.error.URLError("network fail")
    monkeypatch.setattr(adapter.urllib.request, "urlopen", fail)
    with pytest.raises(LayaTypedDecisionError, match="batch request failed"):
        LayaHttpTypedDecisionProvider().evaluate_batch(batch())
