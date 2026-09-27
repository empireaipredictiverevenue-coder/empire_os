"""Runtime capability evidence for mutating execution-plane workers."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


DEFAULT_PATH = Path(
    "/srv/empire_os/runtime/execution_plane/builder_capabilities.json"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty() -> dict[str, Any]:
    return {
        "schema_version": "empire.builder-capabilities.v1",
        "workers": {},
        "execution_authority": "none",
        "commercial_authority": False,
        "production_deploy_authority": False,
    }


def read_builder_capabilities(
    path: str | Path = DEFAULT_PATH,
) -> dict[str, Any]:
    target = Path(path)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    return raw if isinstance(raw, dict) else _empty()


def record_builder_capability(
    worker: str,
    capability: str,
    *,
    ready: bool,
    reason: str,
    model: str | None = None,
    evidence: dict[str, Any] | None = None,
    path: str | Path = DEFAULT_PATH,
) -> dict[str, Any]:
    key = str(worker or "").strip()
    cap = str(capability or "").strip()
    if not key or not cap:
        raise ValueError("worker and capability required")

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = read_builder_capabilities(target)
    workers = payload.setdefault("workers", {})
    worker_row = workers.setdefault(key, {})
    worker_row[cap] = {
        "ready": bool(ready),
        "reason": str(reason or "unknown")[:500],
        "model": str(model).strip() if model else None,
        "observed_at": _now(),
        "evidence": dict(evidence or {}),
        "execution_authority": "none",
    }
    payload["updated_at"] = _now()
    payload["execution_authority"] = "none"
    payload["commercial_authority"] = False
    payload["production_deploy_authority"] = False

    tmp = target.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)
    return payload


def builder_capability_ready(
    worker: str,
    capability: str,
    *,
    path: str | Path = DEFAULT_PATH,
) -> bool:
    payload = read_builder_capabilities(path)
    row = (
        (payload.get("workers") or {})
        .get(str(worker or "").strip(), {})
        .get(str(capability or "").strip(), {})
    )
    return bool(isinstance(row, dict) and row.get("ready") is True)


def builder_capability_snapshot(
    path: str | Path = DEFAULT_PATH,
) -> dict[str, Any]:
    return read_builder_capabilities(path)
