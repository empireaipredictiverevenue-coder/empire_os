#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from empire_os.otel_telemetry import build_resilient_telemetry_sink
from empire_os.telemetry import emit_event, new_trace_context


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PATH = ROOT / "runtime/telemetry/observability_smoke.jsonl"


def main() -> int:
    sink = build_resilient_telemetry_sink(local_path=LOCAL_PATH)
    event = emit_event(
        sink,
        name="foundation.observability_smoke",
        trace=new_trace_context(),
        attributes={
            "component": "observability",
            "remote_configured": sink.remote_sink is not None,
            "execution_authority": "none",
            "revenue_mutation": False,
            "payment_action": False,
            "outbound_action": False,
        },
    )

    flushed = None
    remote = sink.remote_sink
    if remote is not None and callable(getattr(remote, "force_flush", None)):
        try:
            flushed = bool(remote.force_flush())
        except Exception:
            sink.remote_failures += 1
            sink.last_remote_error = "ForceFlushError"
            flushed = False

    print(json.dumps({
        "schema_version": "empire.observability-smoke.v1",
        "event_name": event.name,
        "trace_id": event.trace.trace_id,
        "local_path": str(LOCAL_PATH),
        "local_written": LOCAL_PATH.exists(),
        "remote_configured": remote is not None,
        "remote_flush": flushed,
        "local_failures": sink.local_failures,
        "remote_failures": sink.remote_failures,
        "execution_authority": "none",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
