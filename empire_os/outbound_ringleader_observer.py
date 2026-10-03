"""Continuous OBSERVE-only Ringleader deliverability cycle."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.outbound_deliverability_provider import (
    DeliverabilityMetricsProvider,
    ResendMetricsProvider,
    rolling_windows,
)
from empire_os.outbound_deliverability_ringleader import evaluate_ringleader
from empire_os.outbound_deliverability_service import (
    build_health_from_windows,
    metric_rows,
)
from empire_os.outbound_founder_alerts import build_founder_alert
from empire_os.outbound_postgres_repository import (
    configured_deliverability_repository_from_env,
    configured_deliverability_writer_from_env,
)
from empire_os.outbound_ringleader_runtime import (
    persist_provider_evidence,
    persist_ringleader_decision,
)


DEFAULT_CONTEXT_PATH = Path(
    "/srv/empire_os/runtime/outbound/ringleader_context.json"
)


def load_observer_context(path: Path = DEFAULT_CONTEXT_PATH) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, PermissionError, json.JSONDecodeError) as exc:
        raise RuntimeError("ringleader_context_unreadable") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("ringleader_context_must_be_object")
    if payload.get("mutation_authorized") is True:
        raise RuntimeError("observe_context_cannot_authorize_mutation")
    return payload


def observe_once(
    provider: DeliverabilityMetricsProvider,
    *,
    scope_key: str,
    context: Mapping[str, Any] | None = None,
    reader=None,
    writer=None,
    source: str = "resend",
    now: datetime | None = None,
) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    scope = str(scope_key or "").strip()
    if not scope:
        raise ValueError("scope_key_required")

    if (reader is None) != (writer is None):
        raise RuntimeError("reader_and_writer_must_be_configured_together")

    raw = rolling_windows(provider, now=now)
    health = build_health_from_windows(raw)

    supplied = dict(context or {})
    if supplied.get("mutation_authorized") is True:
        raise RuntimeError("observe_context_cannot_authorize_mutation")

    ringleader_context = {
        **supplied,
        "evaluation_scope": "FLEET",
        "deliverability": {
            **dict(supplied.get("deliverability") or {}),
            "health": health["overall_health"],
        },
    }
    decision = evaluate_ringleader(ringleader_context)
    if decision.get("mutation_authorized") is not False:
        raise RuntimeError("observer_must_remain_non_mutating")

    persistence: dict[str, Any] = {
        "configured": reader is not None and writer is not None,
        "observations": 0,
        "decision_id": None,
        "head_hash": None,
    }

    if reader is not None and writer is not None:
        persisted_count = 0
        head = reader.latest_evidence_head()

        # Persist only the 1d provider rows on each observer cycle. The 7d/30d
        # windows are derived read models, not duplicate raw evidence.
        for row in metric_rows(raw.get("1d") or {}):
            result = persist_provider_evidence(
                scope_key=scope,
                source=source,
                provider_payload=row,
                reader=reader,
                writer=writer,
                observed_at=now,
            )
            persisted_count += len(result["observations_persisted"])
            head = result["head_hash"]

        decision_result = persist_ringleader_decision(
            scope_key=scope,
            ringleader_context=ringleader_context,
            reader=reader,
            writer=writer,
            observed_at=now,
            previous_hash=head,
        )
        persistence = {
            "configured": True,
            "observations": persisted_count,
            "decision_id": decision_result["decision_id"],
            "head_hash": decision_result["head_hash"],
        }

    return {
        "mode": "OBSERVE",
        "scope_key": scope,
        "health": health,
        "ringleader": decision,
        "founder_alert": build_founder_alert(decision),
        "persistence": persistence,
        "mutation_authorized": False,
    }


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    mode = os.getenv("EMPIRE_OUTBOUND_RINGLEADER_MODE", "OBSERVE").strip().upper()
    if mode != "OBSERVE":
        raise RuntimeError("ringleader_observer_supports_observe_only")

    telemetry_source = os.getenv(
        "EMPIRE_OUTBOUND_TELEMETRY_SOURCE",
        "resend",
    ).strip().lower()
    if telemetry_source != "resend":
        raise RuntimeError("unsupported_ringleader_telemetry_source")

    scope_key = os.getenv("EMPIRE_OUTBOUND_SCOPE_KEY", "empire").strip()
    context_path = Path(
        os.getenv(
            "EMPIRE_OUTBOUND_RINGLEADER_CONTEXT_PATH",
            str(DEFAULT_CONTEXT_PATH),
        )
    )
    context = load_observer_context(context_path)

    reader = configured_deliverability_repository_from_env()
    writer = configured_deliverability_writer_from_env()
    require_persistence = _truthy(
        os.getenv("EMPIRE_OUTBOUND_REQUIRE_PERSISTENCE")
    )
    if require_persistence and (reader is None or writer is None):
        raise RuntimeError("ringleader_persistence_required_but_unconfigured")

    result = observe_once(
        ResendMetricsProvider(),
        scope_key=scope_key,
        context=context,
        reader=reader,
        writer=writer,
        source=telemetry_source,
    )
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
