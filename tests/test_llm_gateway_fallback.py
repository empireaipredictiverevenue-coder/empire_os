import json
from types import SimpleNamespace

from empire_os.llm_gateway import LLMGateway


def decision(
    model_id,
    provider,
):
    return SimpleNamespace(
        model=SimpleNamespace(
            model_id=model_id,
            provider=provider,
            model=model_id,
        ),
        route="ROUTE_NONREASONING",
        score=1.0,
        reasoning_gain=0.0,
        estimated_cost=0.0,
    )


class HardFail:
    model = "bad"

    def chat(self, **kwargs):
        return json.dumps({
            "error":
                "zen_failed HTTP 403 "
                "FreeTierError"
        })


class TransientFail:
    model = "transient"

    def chat(self, **kwargs):
        return json.dumps({
            "error":
                "HTTP Error 503: "
                "Service Unavailable"
        })


class Good:
    model = "good"

    def chat(self, **kwargs):
        return "EMPIRE_FALLBACK_OK"


def test_hard_failure_opens_provider_circuit(
    monkeypatch,
):
    monkeypatch.setenv(
        "EMPIRE_LLM_RETRIES",
        "0",
    )

    gateway = LLMGateway()

    calls = []

    def fake_route(*args, **kwargs):
        calls.append(kwargs)

        blocked = (
            kwargs.get(
                "excluded_providers"
            )
            or set()
        )

        if "opencode" not in blocked:
            return decision(
                "bad",
                "opencode",
            )

        return decision(
            "good",
            "llamacpp",
        )

    gateway.route = fake_route

    gateway._client = (
        lambda provider, model, timeout:
        HardFail()
        if provider == "opencode"
        else Good()
    )

    gateway._receipt = (
        lambda **kwargs: None
    )

    result = gateway.chat([
        {
            "role": "user",
            "content": "test",
        }
    ])

    assert result == "EMPIRE_FALLBACK_OK"
    assert len(calls) == 2

    assert (
        "opencode"
        in gateway._runtime_blocked_providers
    )


def test_transient_failure_only_excludes_model(
    monkeypatch,
):
    monkeypatch.setenv(
        "EMPIRE_LLM_RETRIES",
        "0",
    )

    gateway = LLMGateway()

    def fake_route(*args, **kwargs):
        excluded = (
            kwargs.get(
                "excluded_model_ids"
            )
            or set()
        )

        if "transient" not in excluded:
            return decision(
                "transient",
                "gemini",
            )

        return decision(
            "good",
            "llamacpp",
        )

    gateway.route = fake_route

    gateway._client = (
        lambda provider, model, timeout:
        TransientFail()
        if provider == "gemini"
        else Good()
    )

    gateway._receipt = (
        lambda **kwargs: None
    )

    result = gateway.chat([
        {
            "role": "user",
            "content": "test",
        }
    ])

    assert result == "EMPIRE_FALLBACK_OK"

    assert (
        "gemini"
        not in gateway._runtime_blocked_providers
    )
