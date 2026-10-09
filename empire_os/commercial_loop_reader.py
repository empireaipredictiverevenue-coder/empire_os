"""Fail-closed, read-only commercial-loop snapshot access contract."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CommercialLoopReadError(RuntimeError):
    pass


def read_commercial_loop(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CommercialLoopReadError(f"snapshot_unavailable:{type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise CommercialLoopReadError("snapshot_invalid:payload_not_object")
    if not isinstance(payload.get("stages"), list):
        raise CommercialLoopReadError("snapshot_invalid:stages_missing")
    if payload.get("mode") != "OBSERVE" or payload.get("execution_authority") != "none":
        raise CommercialLoopReadError("snapshot_invalid:unexpected_authority")
    return payload
