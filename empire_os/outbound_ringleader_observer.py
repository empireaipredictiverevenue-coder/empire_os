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
from empire_os.outbound_telemetry_probe import probe_loopback_health
from empire_os.outbound_observer_heartbeat import (
    DEFAULT_OBSERVER_HEARTBEAT_PATH,
    write_observer_heartbeat,
)
from empire_os.outbound_estate_reconciliation import reconcile_sender_estate
from empire_os.outbound_evidence_bundle import (
    DEFAULT_EVIDENCE_BUNDLE_PATH,
    load_evidence_bundle,
    project_bundle_to_ringleader,
)
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



def merge_observer_context(
    supplied: Mapping[str, Any] | None,
    bundle_projection: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge evidence-derived context underneath explicit runtime safety context."""

    explicit = dict(supplied or {})
    if explicit.get("mutation_authorized") is True:
        raise RuntimeError("observe_context_cannot_authorize_mutation")

    projected_wrapper = dict(bundle_projection or {})
    if projected_wrapper.get("mutation_authorized") is True:
        raise RuntimeError("evidence_projection_cannot_authorize_mutation")
    projected = projected_wrapper.get("context")
    projected = dict(projected) if isinstance(projected, Mapping) else {}

    merged = dict(projected)
    for key, value in explicit.items():
        if (
            key in {"authentication", "placement", "deliverability"}
            and isinstance(value, Mapping)
            and isinstance(merged.get(key), Mapping)
        ):
            merged[key] = {**dict(merged[key]), **dict(value)}
        elif (
            key == "open_source_evidence"
            and isinstance(value, Mapping)
            and isinstance(merged.get(key), Mapping)
        ):
            merged[key] = {**dict(merged[key]), **dict(value)}
        else:
            merged[key] = value

    merged["mutation_authorized"] = False
    return merged


def build_observer_telemetry_context(
    supplied: Mapping[str, Any],
    *,
    now: datetime,
    evidence_bundle: Mapping[str, Any] | None = None,
    telemetry_probe=None,
) -> dict[str, Any] | None:
    policy = supplied.get("telemetry_policy")
    if not isinstance(policy, Mapping):
        return None

    required_sources = [
        str(value).strip()
        for value in policy.get("required_sources") or []
        if str(value or "").strip()
    ]
    if not required_sources:
        return None

    external = supplied.get("telemetry_heartbeats")
    heartbeats = [
        dict(row)
        for row in external or []
        if isinstance(row, Mapping)
    ]
    heartbeats.append({
        "source": "provider_metrics",
        "observed_at": now.isoformat(),
        "success": True,
        "coverage": True,
        "details": {
            "windows": ["1d", "7d", "30d"],
            "observer": "outbound_ringleader_observer",
        },
    })

    known_sources = {
        str(row.get("source") or row.get("source_key") or "").strip()
        for row in heartbeats
        if isinstance(row, Mapping)
    }
    probe = telemetry_probe
    if (
        "provider_event_ingest" in required_sources
        and "provider_event_ingest" not in known_sources
        and probe is not None
    ):
        heartbeats.append(
            probe(
                "provider_event_ingest",
                "http://127.0.0.1:8097/health",
                now=now,
            )
        )

    if isinstance(evidence_bundle, Mapping):
        generated_at = evidence_bundle.get("generated_at")
        if generated_at:
            heartbeats.append({
                "source": "evidence_bundle",
                "observed_at": generated_at,
                "success": evidence_bundle.get("status") in {"CURRENT", "STALE"},
                "coverage": evidence_bundle.get("status") == "CURRENT",
                "details": {
                    "status": evidence_bundle.get("status"),
                    "signature_status": evidence_bundle.get("signature_status"),
                },
            })

    return {
        "now": now.isoformat(),
        "required_sources": required_sources,
        "critical_sources": list(policy.get("critical_sources") or []),
        "default_max_age_minutes": int(
            policy.get("default_max_age_minutes") or 30
        ),
        "source_max_age_minutes": dict(
            policy.get("source_max_age_minutes") or {}
        ),
        "heartbeats": heartbeats,
    }


def observe_once(
    provider: DeliverabilityMetricsProvider,
    *,
    scope_key: str,
    context: Mapping[str, Any] | None = None,
    evidence_bundle: Mapping[str, Any] | None = None,
    estate_inventory: Mapping[str, Any] | None = None,
    telemetry_probe=None,
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

    bundle_projection = (
        project_bundle_to_ringleader(evidence_bundle)
        if isinstance(evidence_bundle, Mapping)
        else {"context": {}, "warnings": [], "mutation_authorized": False}
    )
    supplied = merge_observer_context(context, bundle_projection)

    estate_reconciliation = None
    if isinstance(estate_inventory, Mapping):
        estate_reconciliation = reconcile_sender_estate(
            transports=estate_inventory.get("transports") or [],
            domains=estate_inventory.get("domains") or [],
            mailboxes=estate_inventory.get("mailboxes") or [],
            pools=estate_inventory.get("pools") or [],
            pool_members=estate_inventory.get("pool_members") or [],
            capacity_events=estate_inventory.get("capacity_events") or [],
            seed_mailboxes=estate_inventory.get("seed_mailboxes") or [],
            now=now,
        )

    telemetry_context = build_observer_telemetry_context(
        supplied,
        now=now,
        evidence_bundle=evidence_bundle,
        telemetry_probe=telemetry_probe,
    )

    ringleader_context = {
        **supplied,
        "evaluation_scope": "FLEET",
        "deliverability": {
            **dict(supplied.get("deliverability") or {}),
            "health": health["overall_health"],
        },
    }
    if telemetry_context is not None:
        ringleader_context["telemetry_sla"] = telemetry_context
    if estate_reconciliation is not None:
        ringleader_context["sender_estate_reconciliation"] = estate_reconciliation
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
        "evidence_bundle": {
            "status": (
                str(evidence_bundle.get("status"))
                if isinstance(evidence_bundle, Mapping)
                else "UNCONFIGURED"
            ),
            "warnings": (
                list(evidence_bundle.get("warnings") or [])
                if isinstance(evidence_bundle, Mapping)
                else []
            ),
        },
        "ringleader": decision,
        "telemetry_context": telemetry_context,
        "sender_estate_reconciliation": estate_reconciliation,
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

    evidence_bundle_path = Path(
        os.getenv(
            "EMPIRE_OUTBOUND_EVIDENCE_BUNDLE_PATH",
            str(DEFAULT_EVIDENCE_BUNDLE_PATH),
        )
    )
    bundle_hmac_key = os.getenv(
        "EMPIRE_OUTBOUND_EVIDENCE_BUNDLE_HMAC_KEY",
        "",
    )
    require_signed_bundle = _truthy(
        os.getenv("EMPIRE_OUTBOUND_REQUIRE_SIGNED_EVIDENCE_BUNDLE")
    )
    evidence_bundle = load_evidence_bundle(
        evidence_bundle_path,
        hmac_key=bundle_hmac_key or None,
        require_signature=require_signed_bundle,
    )

    reader = configured_deliverability_repository_from_env()
    writer = configured_deliverability_writer_from_env()
    require_persistence = _truthy(
        os.getenv("EMPIRE_OUTBOUND_REQUIRE_PERSISTENCE")
    )
    if require_persistence and (reader is None or writer is None):
        raise RuntimeError("ringleader_persistence_required_but_unconfigured")

    cycle_now = datetime.now(timezone.utc)

    estate_inventory = None
    enable_estate_reconciliation = _truthy(
        os.getenv("EMPIRE_OUTBOUND_ENABLE_ESTATE_RECONCILIATION")
    )
    if enable_estate_reconciliation:
        if reader is None:
            raise RuntimeError(
                "estate_reconciliation_requires_empiredb_reader"
            )
        estate_inventory = reader.sender_estate_inventory(
            capacity_date=cycle_now.date().isoformat()
        )

    result = observe_once(
        ResendMetricsProvider(),
        scope_key=scope_key,
        context=context,
        evidence_bundle=evidence_bundle,
        estate_inventory=estate_inventory,
        telemetry_probe=probe_loopback_health,
        reader=reader,
        writer=writer,
        source=telemetry_source,
        now=cycle_now,
    )

    heartbeat_path = Path(
        os.getenv(
            "EMPIRE_OUTBOUND_OBSERVER_HEARTBEAT_PATH",
            str(DEFAULT_OBSERVER_HEARTBEAT_PATH),
        )
    )
    write_observer_heartbeat(
        result,
        path=heartbeat_path,
        now=cycle_now,
    )

    print(json.dumps(result, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
