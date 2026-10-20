"""Persistent route health and cooldowns for Empire Coder models."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProviderHealth:
    def __init__(self, path: Path, *, cooldown_seconds: int = 300) -> None:
        self.path = Path(path)
        self.cooldown_seconds = max(30, min(int(cooldown_seconds), 3600))

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"schema_version": "empire.coder_model_health.v1", "routes": {}}
        if not isinstance(value, dict):
            return {"schema_version": "empire.coder_model_health.v1", "routes": {}}
        value.setdefault("routes", {})
        return value

    def _save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _key(provider: str, model: str) -> str:
        return f"{provider}:{model}"

    def record_failure(self, provider: str, model: str, error: str) -> None:
        state = self._load()
        routes = state["routes"]
        key = self._key(provider, model)
        current = routes.get(key) if isinstance(routes.get(key), dict) else {}
        now = _now()
        # Historical failures must not impose an endless penalty after a
        # genuinely quiet recovery period. A healthy response resets the
        # count independently in record_success().
        previous_failure = current.get("last_failure_at")
        recent = False
        if isinstance(previous_failure, str):
            try:
                instant = datetime.fromisoformat(previous_failure.replace("Z", "+00:00"))
                if instant.tzinfo is not None:
                    recent = timedelta(0) <= now - instant <= timedelta(hours=1)
            except ValueError:
                pass
        failures = max(0, int(current.get("consecutive_failures") or 0)) + 1 if recent else 1
        # Repeated *transport timeouts* need progressively longer, capped
        # cooling. Do not escalate for an invalid patch/schema or other
        # deterministic task error; those require their own repair path.
        timeout = "timeout" in str(error).lower() or "timed out" in str(error).lower()
        cooldown = (
            min(3600, self.cooldown_seconds * (2 ** min(failures - 1, 4)))
            if timeout else self.cooldown_seconds
        )
        routes[key] = {
            "provider": provider,
            "model": model,
            "status": "cooldown",
            "consecutive_failures": failures,
            "last_error": str(error)[:500],
            "last_failure_at": now.isoformat(),
            "cooldown_until": (now + timedelta(seconds=cooldown)).isoformat(),
            "cooldown_seconds_applied": cooldown,
            "last_success_at": current.get("last_success_at"),
        }
        state["updated_at"] = now.isoformat()
        self._save(state)

    def record_success(self, provider: str, model: str) -> None:
        state = self._load()
        routes = state["routes"]
        key = self._key(provider, model)
        current = routes.get(key) if isinstance(routes.get(key), dict) else {}
        now = _now()
        routes[key] = {
            "provider": provider,
            "model": model,
            "status": "healthy",
            "consecutive_failures": 0,
            "last_error": None,
            "last_failure_at": current.get("last_failure_at"),
            "cooldown_until": None,
            "last_success_at": now.isoformat(),
        }
        state["updated_at"] = now.isoformat()
        self._save(state)

    def excluded_routes(self, *, now: datetime | None = None) -> tuple[tuple[str, str], ...]:
        current_time = now or _now()
        state = self._load()
        excluded: list[tuple[str, str]] = []
        for row in (state.get("routes") or {}).values():
            if not isinstance(row, dict):
                continue
            raw_until = row.get("cooldown_until")
            if not raw_until:
                continue
            try:
                until = datetime.fromisoformat(str(raw_until))
            except ValueError:
                continue
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            if until > current_time:
                provider = str(row.get("provider") or "").strip()
                model = str(row.get("model") or "").strip()
                if provider and model:
                    excluded.append((provider, model))
        return tuple(sorted(set(excluded)))

    def snapshot(self) -> dict[str, Any]:
        return self._load()
