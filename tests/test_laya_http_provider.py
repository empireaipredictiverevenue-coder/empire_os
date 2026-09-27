import io
import json

import pytest

import empire_os.laya_http_provider as module
from empire_os.laya_http_provider import LayaHttpTypedDecisionProvider
from empire_os.laya_typed_decision import LayaTypedDecisionError
from empire_os.typed_decision_provider import TypedDecisionRequest


def request():
    return TypedDecisionRequest(
        task_key="reply_classification",
        decision_schema_ref="schema:reply:v2",
        state_ref="gmail:message:1",
        state={"body": "Send the details."},
        allowed_labels=("positive", "negative", "unsubscribe"),
        instructions="Classify the reply.",
        label_criteria={
            "positive": "interest or request to continue",
            "negative": "declines",
            "unsubscribe": "asks to stop contact",
        },
    )


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_http_provider_maps_jev_compatible_choice(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data.decode("utf-8"))
        seen["timeout"] = timeout
        return FakeResponse({
            "answers": {
                "reply_classification": {
                    "choice": "positive",
                    "probabilities": {
                        "positive": 0.91,
                        "negative": 0.05,
                        "unsubscribe": 0.04,
                    },
                }
            },
            "usage": {"input_tokens": 20, "output_tokens": 3},
        })

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    result = LayaHttpTypedDecisionProvider().evaluate(request())

    assert seen["url"] == "http://127.0.0.1:8769/v1/systemone"
    assert seen["body"]["state"]["body"] == "Send the details."
    assert seen["body"]["questions"]["reply_classification"]["type"] == "choice"
    assert result.label == "positive"
    assert result.confidence == pytest.approx(0.91)
    assert result.shadow_only is True
    assert result.execution_authority == "none"


def test_http_provider_rejects_disallowed_label(monkeypatch):
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse({
            "answers": {
                "reply_classification": {
                    "choice": "send_money",
                    "confidence": 0.99,
                }
            }
        }),
    )
    with pytest.raises(LayaTypedDecisionError, match="disallowed"):
        LayaHttpTypedDecisionProvider().evaluate(request())


def test_http_provider_fails_closed_on_transport_error(monkeypatch):
    def fail(*_args, **_kwargs):
        raise module.urllib.error.URLError("down")

    monkeypatch.setattr(module.urllib.request, "urlopen", fail)
    with pytest.raises(LayaTypedDecisionError, match="request failed"):
        LayaHttpTypedDecisionProvider().evaluate(request())
