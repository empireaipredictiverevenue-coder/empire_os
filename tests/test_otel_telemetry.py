import base64
import json

import pytest

import empire_os.otel_telemetry as module
from empire_os.otel_telemetry import (
    OtlpSettings,
    ResilientTelemetrySink,
    _otel_attributes,
    build_resilient_telemetry_sink,
    langfuse_otlp_settings_from_env,
)
from empire_os.telemetry import (
    JsonlTelemetrySink,
    TelemetryEvent,
    new_trace_context,
)


def event():
    return TelemetryEvent(
        name="ai.typed_decision",
        trace=new_trace_context(),
        attributes={
            "ai.provider": "laya_http",
            "nested": {"status": "shadow"},
            "execution_authority": "none",
        },
        observed_at="2026-09-25T10:30:00+00:00",
    )


def test_langfuse_settings_are_v4_otlp_http_and_do_not_expose_keys():
    settings = langfuse_otlp_settings_from_env({
        "LANGFUSE_PUBLIC_KEY": "pk-test",
        "LANGFUSE_SECRET_KEY": "sk-test",
        "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
        "EMPIRE_ENVIRONMENT": "production",
    })
    assert settings is not None
    assert settings.endpoint == (
        "https://cloud.langfuse.com/api/public/otel/v1/traces"
    )
    expected = base64.b64encode(b"pk-test:sk-test").decode("ascii")
    assert settings.headers["Authorization"] == f"Basic {expected}"
    assert settings.headers["x-langfuse-ingestion-version"] == "4"
    rendered = repr(settings)
    assert "pk-test" not in rendered
    assert "sk-test" not in rendered
    assert "Authorization" not in rendered


def test_missing_langfuse_credentials_disables_remote_export():
    settings = langfuse_otlp_settings_from_env({})
    assert settings is None


def test_otlp_settings_reject_non_http_endpoint():
    with pytest.raises(ValueError, match="http"):
        OtlpSettings(
            endpoint="file:///tmp/traces",
            headers={},
        ).validate()


def test_otel_attributes_serialize_nested_values_and_keep_no_authority():
    attrs = _otel_attributes(event())
    assert attrs["ai.provider"] == "laya_http"
    assert json.loads(attrs["nested"]) == {"status": "shadow"}
    assert attrs["empire.execution_authority"] == "none"


class FailingRemote:
    def emit(self, _event):
        raise RuntimeError("backend unavailable")


def test_remote_failure_never_blocks_local_evidence(tmp_path):
    path = tmp_path / "events.jsonl"
    sink = ResilientTelemetrySink(
        local_sink=JsonlTelemetrySink(path),
        remote_sink=FailingRemote(),
    )
    sink.emit(event())

    assert path.exists()
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["name"] == "ai.typed_decision"
    assert sink.remote_failures == 1
    assert sink.last_remote_error == "RuntimeError"


def test_factory_stays_local_when_credentials_are_absent(tmp_path):
    sink = build_resilient_telemetry_sink(
        local_path=tmp_path / "events.jsonl",
        env={},
    )
    assert sink.remote_sink is None
    sink.emit(event())
    assert (tmp_path / "events.jsonl").exists()


def test_factory_falls_back_local_when_otel_package_is_unavailable(
    monkeypatch,
    tmp_path,
):
    class Unavailable:
        def __init__(self, _settings):
            raise module.OpenTelemetryUnavailable("missing")

    monkeypatch.setattr(module, "OpenTelemetryEventSink", Unavailable)
    sink = build_resilient_telemetry_sink(
        local_path=tmp_path / "events.jsonl",
        env={
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
        },
    )
    assert sink.remote_sink is None
    sink.emit(event())
    assert (tmp_path / "events.jsonl").exists()


class FailingLocal:
    def emit(self, _event):
        raise OSError("disk unavailable")


def test_local_failure_also_never_blocks_business_flow():
    sink = ResilientTelemetrySink(
        local_sink=FailingLocal(),
        remote_sink=None,
    )
    sink.emit(event())
    assert sink.local_failures == 1
    assert sink.last_local_error == "OSError"
