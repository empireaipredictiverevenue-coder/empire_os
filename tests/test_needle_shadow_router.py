import json

import pytest

from empire_os.needle_shadow_router import (
    DEFAULT_EMPIRE_ROUTER_FACTS,
    NeedleRouteRequest,
    NeedleRouterError,
    NeedleShadowRouter,
    NeedleToolSchema,
)
from empire_os.telemetry import JsonlTelemetrySink, new_trace_context


def tools():
    return (
        NeedleToolSchema(
            name="classify_reply",
            description="Classify a buyer reply into Empire reply classes.",
            parameters={
                "type": "object",
                "properties": {
                    "message_ref": {"type": "string"},
                },
                "required": ["message_ref"],
            },
        ),
        NeedleToolSchema(
            name="build_copy_brief",
            description="Build a drafting-only outreach brief from observed evidence.",
            parameters={
                "type": "object",
                "properties": {
                    "account_ref": {"type": "string"},
                },
                "required": ["account_ref"],
            },
        ),
    )


class FakeNeedle:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        return self.payload


def request(threshold=0.75):
    return NeedleRouteRequest(
        query="Buyer replied: yes, send the one-page example.",
        state_ref="gmail:message:1",
        tools=tools(),
        confidence_threshold=threshold,
    )


def test_shadow_router_selects_declared_tool_without_execution(tmp_path):
    path = tmp_path / "needle.jsonl"
    agent = FakeNeedle({
        "function_calls": [{
            "name": "classify_reply",
            "arguments": {"message_ref": "gmail:message:1"},
        }],
        "reasoning": "reply classification needed",
        "confidence": 0.91,
    })
    trace = new_trace_context()
    router = NeedleShadowRouter(
        agent=agent,
        telemetry_sink=JsonlTelemetrySink(path),
    )

    result = router.route(request(), trace=trace)

    assert result.tool_name == "classify_reply"
    assert result.arguments == {"message_ref": "gmail:message:1"}
    assert result.confidence == pytest.approx(0.91)
    assert result.requires_escalation is False
    assert result.shadow_only is True
    assert result.execution_authority == "none"
    assert result.tool_executed is False
    assert agent.calls == [{
        "text": "Buyer replied: yes, send the one-page example.",
        "max_new_tokens": 256,
    }]

    event = json.loads(path.read_text(encoding="utf-8"))
    assert event["trace"]["trace_id"] == trace.trace_id
    assert event["attributes"]["ai.tool.name"] == "classify_reply"
    assert event["attributes"]["tool_executed"] is False


def test_empty_call_escalates_instead_of_guessing():
    router = NeedleShadowRouter(agent=FakeNeedle({
        "function_calls": [],
        "confidence": 0.96,
    }))
    result = router.route(request())
    assert result.tool_name is None
    assert result.requires_escalation is True


def test_low_confidence_route_escalates():
    router = NeedleShadowRouter(agent=FakeNeedle({
        "function_calls": [{
            "name": "build_copy_brief",
            "arguments": {"account_ref": "acct:1"},
        }],
        "confidence": 0.41,
    }))
    result = router.route(request(threshold=0.8))
    assert result.tool_name == "build_copy_brief"
    assert result.requires_escalation is True


def test_undeclared_tool_is_rejected():
    router = NeedleShadowRouter(agent=FakeNeedle({
        "function_calls": [{
            "name": "send_money",
            "arguments": {},
        }],
        "confidence": 0.99,
    }))
    with pytest.raises(NeedleRouterError, match="undeclared"):
        router.route(request())


def test_multiple_tool_calls_fail_closed():
    router = NeedleShadowRouter(agent=FakeNeedle({
        "function_calls": [
            {"name": "classify_reply", "arguments": {}},
            {"name": "build_copy_brief", "arguments": {}},
        ],
        "confidence": 0.90,
    }))
    with pytest.raises(NeedleRouterError, match="at most one"):
        router.route(request())


def test_tool_schema_requires_object_parameters():
    with pytest.raises(ValueError, match="object schema"):
        NeedleToolSchema(
            name="bad",
            description="bad schema",
            parameters={"type": "string"},
        ).validate()


def test_default_router_policy_prioritizes_reply_analysis():
    lower = DEFAULT_EMPIRE_ROUTER_FACTS.lower()
    assert "buyer email or reply" in lower
    assert "classify_reply" in lower
    assert "explicitly asks" in lower
    assert "return no function call" in lower
    assert "never execute tools" in lower
