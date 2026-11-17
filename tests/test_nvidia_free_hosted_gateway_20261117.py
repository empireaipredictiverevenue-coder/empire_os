"""Security and compatibility tests for the existing NVIDIA model gateway.

No external API calls. A mocked free-price catalog and model response verify
the optional host-only OpenRouter route and its fail-closed controls.
"""
from __future__ import annotations
import io,json
import pytest
from scripts import nvidia_free_openrouter_relay_20261117 as relay


class Response:
    def __init__(self, payload):
        self.payload=json.dumps(payload).encode()
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,size=-1):return self.payload if size<0 else self.payload[:size]


def _synthetic_payload():
    return {
        "model":relay.GATEWAY_ALIAS,
        "stream":False,
        "max_tokens":8192,
        "messages":[{"role":"user","content":"Synthetic ontology_edges relation BUYER_DEMANDS_LANE"}],
        "tools":[{"type":"function","function":{"name":"run_sql","description":"Test"}}],
    }


def test_hosted_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("EMPIRE_NVIDIA_EVAL_FREE_HOSTED_ENABLED",raising=False)
    with pytest.raises(relay.HostedUnavailable):
        relay.send(_synthetic_payload())


def test_exact_model_and_zero_price_rechecked_for_each_call(monkeypatch):
    monkeypatch.setenv("EMPIRE_NVIDIA_EVAL_FREE_HOSTED_ENABLED","1")
    monkeypatch.setattr(relay,"existing_key",lambda:"test-only-fake-key")
    calls=[]
    def urlopen(request,timeout=5):
        calls.append(request)
        if request.full_url==relay.CATALOG:
            return Response({"data":[{
                "id":relay.REMOTE_MODEL,
                "pricing":{"prompt":"0","completion":"0"},
                "supported_parameters":["tools","response_format","structured_outputs"],
            }]})
        if request.full_url==relay.INFERENCE:
            payload=json.loads(request.data)
            assert payload["model"]==relay.REMOTE_MODEL
            assert payload["provider"]=={"allow_fallbacks":False}
            assert payload["tools"]==_synthetic_payload()["tools"]
            assert request.headers["Authorization"]=="Bearer test-only-fake-key"
            return Response({"model":relay.REMOTE_MODEL,"choices":[{"message":{"content":"test"}}]})
        raise RuntimeError("unapproved network destination")
    monkeypatch.setattr(relay,"urlopen",urlopen)
    result=json.loads(relay.send(_synthetic_payload()))
    assert result["model"]==relay.REMOTE_MODEL
    assert [req.full_url for req in calls]==[relay.CATALOG,relay.INFERENCE]


@pytest.mark.parametrize("price",["0.0000001","1",None])
def test_paid_or_ambiguous_price_is_rejected(monkeypatch,price):
    monkeypatch.setenv("EMPIRE_NVIDIA_EVAL_FREE_HOSTED_ENABLED","1")
    monkeypatch.setattr(relay,"existing_key",lambda:"test-only-fake-key")
    def urlopen(request,timeout=5):
        assert request.full_url==relay.CATALOG
        return Response({"data":[{
            "id":relay.REMOTE_MODEL,
            "pricing":{"prompt":price,"completion":"0"},
            "supported_parameters":["tools","response_format","structured_outputs"],
        }]})
    monkeypatch.setattr(relay,"urlopen",urlopen)
    with pytest.raises(relay.HostedUnavailable):
        relay.send(_synthetic_payload())


def test_wrong_model_streaming_and_token_overage_rejected(monkeypatch):
    monkeypatch.setenv("EMPIRE_NVIDIA_EVAL_FREE_HOSTED_ENABLED","1")
    for changed in (
        {"model":"paid/model"},
        {"stream":True},
        {"max_tokens":8193},
    ):
        payload=_synthetic_payload()
        payload.update(changed)
        with pytest.raises(relay.HostedUnavailable):
            relay.send(payload)
