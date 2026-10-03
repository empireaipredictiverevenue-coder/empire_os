import io
import json
from types import SimpleNamespace
from unittest.mock import patch

from empire_os.coder.llama_cpp_provider import (
    LlamaCppProvider,
)
from empire_os.llm_gateway import LLMGateway


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_gateway_resolves_llamacpp_provider():
    gateway = LLMGateway()

    client = gateway._client(
        "llamacpp",
        "qwen2.5-coder:1.5b",
        30,
    )

    assert isinstance(
        client,
        LlamaCppProvider,
    )
    assert (
        client.model
        == "qwen2.5-coder:1.5b"
    )
    assert (
        client.base_url
        == "http://127.0.0.1:11435"
    )


def test_gateway_accepts_llama_cpp_alias():
    client = LLMGateway()._client(
        "llama_cpp",
        "qwen2.5-coder:1.5b",
        30,
    )

    assert isinstance(
        client,
        LlamaCppProvider,
    )


def test_llamacpp_chat_openai_endpoint():
    body = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": "EMPIRE_OK"
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 4,
                "completion_tokens": 2,
            },
        }
    ).encode()

    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["body"] = json.loads(
            req.data.decode("utf-8")
        )
        return FakeResponse(body)

    provider = LlamaCppProvider(
        model="qwen2.5-coder:1.5b",
    )

    with patch(
        "empire_os.coder.llama_cpp_provider.request.urlopen",
        side_effect=fake_urlopen,
    ):
        result = provider.chat(
            [
                {
                    "role": "user",
                    "content": "Reply EMPIRE_OK",
                }
            ],
            system="Internal test.",
            temperature=0.0,
            max_tokens=16,
        )

    assert result == "EMPIRE_OK"
    assert (
        seen["url"]
        == "http://127.0.0.1:11435/v1/chat/completions"
    )
    assert (
        seen["body"]["model"]
        == "qwen2.5-coder:1.5b"
    )
    assert (
        seen["body"]["max_tokens"]
        == 16
    )


def test_llamacpp_transport_failure_fails_closed():
    provider = LlamaCppProvider()

    with patch(
        "empire_os.coder.llama_cpp_provider.request.urlopen",
        side_effect=OSError("down"),
    ):
        result = provider.chat(
            [
                {
                    "role": "user",
                    "content": "test",
                }
            ]
        )

    payload = json.loads(result)

    assert payload["error"].startswith(
        "llama_cpp_request_failed:"
    )


def test_gateway_passes_max_tokens_to_llamacpp():
    gateway = LLMGateway()

    spec = SimpleNamespace(
        provider="llamacpp",
        model="qwen2.5-coder:1.5b",
    )

    decision = SimpleNamespace(
        model=spec,
        route="ROUTE_NONREASONING",
        score=1.0,
        reasoning_gain=0.0,
        estimated_cost=0.0,
    )

    captured = {}

    class FakeClient:
        model = "qwen2.5-coder:1.5b"

        def chat(self, **kwargs):
            captured.update(kwargs)
            return "OK"

    gateway.route = lambda *args, **kwargs: decision
    gateway._client = (
        lambda provider, model, timeout:
        FakeClient()
    )
    gateway._receipt = (
        lambda **kwargs: None
    )

    result = gateway.chat(
        [
            {
                "role": "user",
                "content": "test",
            }
        ],
        max_tokens=37,
    )

    assert result == "OK"
    assert captured["max_tokens"] == 37
