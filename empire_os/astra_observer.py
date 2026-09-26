"""Read-only Phase 4 Astra observer runtime.

Fetches the bounded Phase 3F outcome projection, builds deterministic
calibration, optionally evaluates a fully explicit operational snapshot,
and writes a local observation artifact. No commercial mutation occurs.
"""
from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any, Callable, Mapping

from empire_os.astra import AstraSnapshot, build_operating_board
from empire_os.astra_feedback import build_outcome_calibration
from empire_os.astra_freshness import validate_astra_operational_freshness
from empire_os.astra_evidence import (
    astra_policy_bindings_from_env,
    build_astra_evidence,
)
from empire_os.outcome_role_transport import PostgresOutcomeRpc


class AstraObserverError(RuntimeError):
    pass


def bounded_feedback_limit(value: Any, *, default: int = 100) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, 1000))


def parse_operational_snapshot(raw: str | None) -> AstraSnapshot | None:
    """Parse a complete observed Astra snapshot.

    Partial snapshots are rejected because dataclass defaults would otherwise
    turn missing observations into invented zero/false values.
    """
    if raw is None or not str(raw).strip():
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AstraObserverError("invalid operational snapshot JSON") from exc
    if not isinstance(payload, dict):
        raise AstraObserverError("operational snapshot must be a JSON object")

    required = {field.name for field in fields(AstraSnapshot)}
    supplied = set(payload)
    missing = sorted(required - supplied)
    extra = sorted(supplied - required)
    if missing or extra:
        raise AstraObserverError(
            "operational snapshot must provide exactly AstraSnapshot fields; "
            f"missing={missing}; extra={extra}"
        )
    snapshot = AstraSnapshot(**payload)
    if str(snapshot.execution_mode).strip().lower() not in {"observe", "dry_run"}:
        raise AstraObserverError("operational snapshot must remain OBSERVE/DRY_RUN")
    return snapshot


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def run_observer_cycle(
    *,
    dsn: str,
    mode: str = "OBSERVE",
    feedback_limit: int = 100,
    min_samples: int = 20,
    min_conversions: int = 5,
    operational_snapshot_json: str | None = None,
    operational_bindings: Mapping[str, Any] | None = None,
    output_path: str | Path = "runtime/astra/latest.json",
    operational_evidence_max_age_seconds: int = 21600,
    now_utc: Any | None = None,
    rpc_factory: Callable[..., Any] = PostgresOutcomeRpc,
) -> dict[str, Any]:
    """Run one bounded read-only Astra observation cycle."""
    normalized_mode = str(mode or "OBSERVE").strip().upper()
    if normalized_mode != "OBSERVE":
        raise AstraObserverError("Phase 4 Astra observer supports OBSERVE only")

    clean_dsn = str(dsn or "").strip()
    if not clean_dsn:
        raise AstraObserverError("EMPIRE_ASTRA_OBSERVER_DSN is required")

    limit = bounded_feedback_limit(feedback_limit)
    rpc = rpc_factory(clean_dsn, "empire_astra_observer")
    rows = rpc("get_commercial_outcome_feedback", {"p_limit": limit})
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        raise AstraObserverError("outcome feedback projection must return a list")

    calibration = build_outcome_calibration(
        rows,
        min_samples=max(int(min_samples), 1),
        min_conversions=max(int(min_conversions), 1),
    )
    snapshot = parse_operational_snapshot(operational_snapshot_json)
    evidence_payload: dict[str, Any] | None = None

    if snapshot is None:
        raw_operational = rpc("get_astra_operational_evidence", {})
        if raw_operational is None:
            raw_operational = {}
        if not isinstance(raw_operational, Mapping):
            raise AstraObserverError(
                "operational evidence projection must return an object"
            )
        if not raw_operational:
            evidence = build_astra_evidence(
                actual_revenue_cents=calibration.actual_revenue_cents,
                operational_row=raw_operational,
                bindings=(
                    operational_bindings
                    if operational_bindings is not None
                    else astra_policy_bindings_from_env()
                ),
            )
            evidence_payload = {
                "available": evidence.available,
                "missing": list(evidence.missing),
                "observed": dict(evidence.observed),
                "sources": dict(evidence.sources),
            }
            snapshot = evidence.snapshot
        else:
            freshness = validate_astra_operational_freshness(
                raw_operational,
                now=now_utc,
                max_age_seconds=max(int(operational_evidence_max_age_seconds), 1),
            )
            if not freshness.fresh:
                evidence_payload = {
                    "available": False,
                    "missing": [],
                    "observed": {},
                    "sources": {},
                    "freshness": {
                        "fresh": freshness.fresh,
                        "observed_at": freshness.observed_at,
                        "age_seconds": freshness.age_seconds,
                        "reason": freshness.reason,
                    },
                }
                snapshot = None
            else:
                evidence = build_astra_evidence(
                    actual_revenue_cents=calibration.actual_revenue_cents,
                    operational_row=raw_operational,
                    bindings=(
                        operational_bindings
                        if operational_bindings is not None
                        else astra_policy_bindings_from_env()
                    ),
                )
                evidence_payload = {
                    "available": evidence.available,
                    "missing": list(evidence.missing),
                    "observed": dict(evidence.observed),
                    "sources": dict(evidence.sources),
                    "freshness": {
                        "fresh": freshness.fresh,
                        "observed_at": freshness.observed_at,
                        "age_seconds": freshness.age_seconds,
                        "reason": freshness.reason,
                    },
                }
                snapshot = evidence.snapshot


    if snapshot is None:
        missing = list((evidence_payload or {}).get("missing") or [])
        freshness_reason = (
            ((evidence_payload or {}).get("freshness") or {}).get("reason")
        )
        unavailable_reason = (
            freshness_reason
            if freshness_reason in {
                "operational_evidence_stale",
                "operational_evidence_from_future",
            }
            else "operational_evidence_incomplete"
        )
        decision: dict[str, Any] = {
            "available": False,
            "reason": unavailable_reason,
            "missing": missing,
        }
        operating_board: dict[str, Any] = {
            "available": False,
            "reason": unavailable_reason,
            "missing": missing,
        }
    else:
        board = build_operating_board(
            snapshot,
            negative_margin_orders=calibration.negative_margin_orders,
            calibration_ready=calibration.calibration_ready,
            gross_margin_rate=calibration.gross_margin_rate,
        )
        source = (
            "explicit_operational_snapshot"
            if operational_snapshot_json
            else "canonical_operational_evidence"
        )
        decision = {
            "available": True,
            "source": source,
            "result": board.primary.as_dict(),
        }
        operating_board = {
            "available": True,
            "source": source,
            "result": board.as_dict(),
        }

    payload: dict[str, Any] = {
        "ok": True,
        "mode": "OBSERVE",
        "feedback_limit": limit,
        "feedback_rows": len(rows),
        "calibration": calibration.as_dict(),
        "operational_evidence": evidence_payload,
        "decision": decision,
        "operating_board": operating_board,
        "side_effects": "none",
    }
    atomic_write_json(Path(output_path), payload)
    return payload
