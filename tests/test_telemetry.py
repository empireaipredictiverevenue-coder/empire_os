import json

import pytest

from empire_os.telemetry import (
    JsonlTelemetrySink,
    NullTelemetrySink,
    TraceContext,
    emit_event,
    new_trace_context,
    parse_traceparent,
    typed_decision_attributes,
)


def test_trace_context_round_trips_w3c_traceparent():
    trace = new_trace_context()
    parsed = parse_traceparent(trace.to_traceparent())
    assert parsed.trace_id == trace.trace_id
    assert parsed.span_id == trace.span_id
    assert parsed.sampled is True


def test_child_span_preserves_trace_and_parent():
    parent = new_trace_context()
    child = parent.child()
    assert child.trace_id == parent.trace_id
    assert child.parent_span_id == parent.span_id
    assert child.span_id != parent.span_id


def test_all_zero_trace_identifier_is_rejected():
    with pytest.raises(ValueError, match="all zeros"):
        TraceContext(
            trace_id="0" * 32,
            span_id="1" * 16,
        ).validate()


def test_jsonl_sink_redacts_secrets(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    trace = new_trace_context()
    emit_event(
        JsonlTelemetrySink(path),
        name="ai.typed_decision",
        trace=trace,
        attributes={
            "task": "reply_classification",
            "api_key": "should-never-land",
            "nested": {"authorization": "Bearer abc"},
        },
        observed_at="2026-09-25T10:00:00+00:00",
    )
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["attributes"]["task"] == "reply_classification"
    assert row["attributes"]["api_key"] == "[REDACTED]"
    assert row["attributes"]["nested"]["authorization"] == "[REDACTED]"
    assert row["traceparent"].startswith("00-")


def test_null_sink_validates_without_network_or_mutation():
    event = emit_event(
        NullTelemetrySink(),
        name="empire.test",
        trace=new_trace_context(),
        attributes={"revenue_mutation": False},
    )
    assert event.attributes["revenue_mutation"] is False


def test_typed_decision_attributes_never_claim_execution_authority():
    attrs = typed_decision_attributes(
        provider_key="laya",
        model_key="convaiinnovations/laya",
        task_key="reply_classification",
        label="positive",
        confidence=0.91,
        latency_ms=12.5,
        shadow_only=True,
        risk_class="low",
    )
    assert attrs["execution_authority"] == "none"
    assert attrs["ai.shadow_only"] is True
