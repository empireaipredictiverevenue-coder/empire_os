"""Safe reconciliation for ambiguous Recall SHADOW Create Bot outcomes."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Protocol
import urllib.parse
import urllib.request

from empire_os.recall_shadow_activation import RecallShadowActivationPacket
from empire_os.recall_shadow_activation_store import activation_plan_sha256


class RecallLookupTransport(Protocol):
    def get_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_s: float,
    ) -> tuple[int, Mapping[str, str], Mapping[str, Any]]:
        ...


class UrllibRecallLookupTransport:
    def get_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_s: float,
    ) -> tuple[int, Mapping[str, str], Mapping[str, Any]]:
        request = urllib.request.Request(
            url,
            headers=dict(headers),
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            raw = response.read().decode("utf-8")
            body = json.loads(raw) if raw else {}
            return response.status, dict(response.headers), body


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("SHADOW activation record missing") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("SHADOW activation record unreadable") from exc
    if not isinstance(value, dict):
        raise ValueError("SHADOW activation record invalid")
    return value


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


def reconcile_recall_shadow_activation(
    *,
    packet: RecallShadowActivationPacket,
    activation_root: str | Path,
    api_key: str,
    transport: RecallLookupTransport | None = None,
    timeout_s: float = 20.0,
) -> dict[str, Any]:
    path = Path(activation_root) / f"{packet.bot_plan.meeting_id}.json"
    record = _load(path)
    if record.get("schema_version") != "empire.recall_shadow_activation.v1":
        raise ValueError("unsupported SHADOW activation schema")
    if record.get("plan_sha256") != activation_plan_sha256(packet):
        raise ValueError("SHADOW reconciliation fingerprint mismatch")
    if record.get("execution_state") not in {
        "reconciliation_required",
        "in_flight",
    }:
        raise ValueError("SHADOW activation does not require reconciliation")

    clean_key = str(api_key or "").strip()
    if not clean_key:
        raise ValueError("Recall API key required")
    region = packet.join_request.region
    params = urllib.parse.urlencode({
        "metadata__empire_meeting_id": packet.bot_plan.meeting_id,
        "metadata__empire_avatar_id": packet.bot_plan.avatar_id,
        "metadata__empire_mode": "shadow",
        "metadata__execution_authority": "none",
    })
    url = f"https://{region}.recall.ai/api/v1/bot/?{params}"
    client = transport or UrllibRecallLookupTransport()
    status, _headers, body = client.get_json(
        url=url,
        headers={
            "Authorization": f"Token {clean_key}",
            "Accept": "application/json",
        },
        timeout_s=timeout_s,
    )
    if status != 200:
        raise RuntimeError(f"Recall List Bots failed with status {status}")

    raw_results = body.get("results")
    if not isinstance(raw_results, list):
        raise RuntimeError("Recall List Bots response missing results")
    matches = []
    for row in raw_results:
        if not isinstance(row, Mapping):
            continue
        metadata = row.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        if str(metadata.get("empire_meeting_id") or "") != packet.bot_plan.meeting_id:
            continue
        if str(metadata.get("empire_avatar_id") or "") != packet.bot_plan.avatar_id:
            continue
        if str(metadata.get("empire_mode") or "").lower() != "shadow":
            continue
        if str(metadata.get("execution_authority") or "").lower() != "none":
            continue
        matches.append(dict(row))

    if len(matches) == 1:
        bot_id = str(matches[0].get("id") or "").strip()
        if not bot_id:
            raise RuntimeError("reconciled Recall bot missing id")
        completed = {
            **record,
            "execution_state": "completed_reconciled",
            "provider_api_call_started": True,
            "provider_api_call_performed": True,
            "live_join_performed": True,
            "provider_bot_id": bot_id,
            "provider_status": 200,
        }
        _atomic_json(path, completed)
        return {
            "resolution": "bot_found",
            "bot_id": bot_id,
            "match_count": 1,
            "execution_state": "completed_reconciled",
            "deduplication_enforced": True,
            "provider_api_call_performed": False,
            "execution_authority": "none",
        }


    if not matches:
        unresolved = {
            **record,
            "execution_state": "reconciliation_no_bot_found",
            "provider_api_call_started": True,
            "provider_api_call_performed": True,
            "live_join_performed": False,
        }
        _atomic_json(path, unresolved)
        return {
            "resolution": "no_bot_found",
            "bot_id": None,
            "match_count": 0,
            "execution_state": "reconciliation_no_bot_found",
            "deduplication_enforced": True,
            "provider_api_call_performed": False,
            "execution_authority": "none",
        }

    conflict = {
        **record,
        "execution_state": "reconciliation_conflict",
        "provider_api_call_started": True,
        "provider_api_call_performed": True,
        "live_join_performed": False,
    }
    _atomic_json(path, conflict)
    return {
        "resolution": "multiple_bots_found",
        "bot_id": None,
        "match_count": len(matches),
        "execution_state": "reconciliation_conflict",
        "deduplication_enforced": True,
        "provider_api_call_performed": False,
        "execution_authority": "none",
    }
