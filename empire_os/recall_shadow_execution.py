"""One-time materialized execution gate for Recall SHADOW joins."""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from empire_os.recall_shadow_activation import RecallShadowActivationPacket
from empire_os.recall_shadow_activation_store import activation_plan_sha256
from empire_os.recall_shadow_join import execute_recall_shadow_join


def _load_record(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("SHADOW activation record missing") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("SHADOW activation record unreadable") from exc
    if not isinstance(raw, dict):
        raise ValueError("SHADOW activation record invalid")
    if raw.get("schema_version") != "empire.recall_shadow_activation.v1":
        raise ValueError("unsupported SHADOW activation schema")
    return raw


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    tmp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    finally:
        if tmp.exists():
            tmp.unlink()


def validate_materialized_shadow_execution(
    *,
    packet: RecallShadowActivationPacket,
    activation_root: str | Path,
) -> tuple[Path, dict[str, Any]]:
    path = Path(activation_root) / f"{packet.bot_plan.meeting_id}.json"
    record = _load_record(path)
    if record.get("plan_sha256") != activation_plan_sha256(packet):
        raise ValueError("materialized SHADOW activation fingerprint mismatch")
    if record.get("meeting_id") != packet.bot_plan.meeting_id:
        raise ValueError("materialized SHADOW activation meeting mismatch")
    if record.get("avatar_id") != packet.bot_plan.avatar_id:
        raise ValueError("materialized SHADOW activation avatar mismatch")
    if record.get("region") != packet.join_request.region:
        raise ValueError("materialized SHADOW activation region mismatch")
    if record.get("approval_evidence_ref") != (
        packet.join_request.authorization.approval_evidence_ref
    ):
        raise ValueError("materialized SHADOW activation approval mismatch")
    if record.get("execution_state") != "prepared":
        raise ValueError(
            "materialized SHADOW activation is not executable from prepared state"
        )
    if record.get("live_join_performed") is not False:
        raise ValueError("materialized SHADOW activation already joined")
    if record.get("provider_api_call_started") is not False:
        raise ValueError("materialized SHADOW provider call already started")
    if str(record.get("execution_authority") or "").lower() != "none":
        raise ValueError("materialized SHADOW record grants forbidden authority")
    return path, record


def execute_materialized_recall_shadow_activation(
    *,
    packet: RecallShadowActivationPacket,
    activation_root: str | Path,
    api_key: str,
    transport=None,
    sleeper: Callable[[float], None] | None = None,
    now: datetime | None = None,
    timeout_s: float = 20.0,
    max_attempts: int = 10,
) -> dict[str, Any]:
    path, record = validate_materialized_shadow_execution(
        packet=packet,
        activation_root=activation_root,
    )

    in_flight = {
        **record,
        "execution_state": "in_flight",
        "provider_api_call_started": True,
        "provider_api_call_performed": False,
        "live_join_performed": False,
        "provider_bot_id": None,
        "provider_status": None,
    }
    _atomic_json(path, in_flight)

    kwargs: dict[str, Any] = {
        "request": packet.join_request,
        "api_key": api_key,
        "transport": transport,
        "now": now,
        "timeout_s": timeout_s,
        "max_attempts": max_attempts,
    }
    if sleeper is not None:
        kwargs["sleeper"] = sleeper

    try:
        result = execute_recall_shadow_join(**kwargs)
    except Exception:
        failed = {
            **in_flight,
            "execution_state": "reconciliation_required",
            "provider_api_call_performed": True,
            "live_join_performed": False,
        }
        _atomic_json(path, failed)
        raise

    completed = {
        **in_flight,
        "execution_state": "completed",
        "provider_api_call_performed": True,
        "live_join_performed": bool(result.get("live_join_performed")),
        "provider_bot_id": result.get("bot_id"),
        "provider_status": result.get("provider_status"),
    }
    _atomic_json(path, completed)
    return {
        **result,
        "activation_plan_sha256": record["plan_sha256"],
        "execution_state": "completed",
        "deduplication_enforced": True,
    }
