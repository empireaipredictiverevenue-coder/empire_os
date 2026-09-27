"""Shared containment governor for legacy hosted-data egress.

This module owns request budgets and circuit state while EmpireOS migrates away
from the hosted legacy backend. It contains no database credentials and grants
no business authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable, Mapping


DEFAULT_HOURLY_BUDGET = 3000
DEFAULT_COMPONENT_HOURLY_BUDGET = 1000
DEFAULT_DAILY_BUDGET = 25000
DEFAULT_PROBE_SECONDS = 1800


def _env_int(
    environ: Mapping[str, str],
    names: tuple[str, ...],
    default: int,
    *,
    minimum: int = 1,
) -> int:
    raw = None
    for name in names:
        if environ.get(name) not in (None, ""):
            raw = environ[name]
            break
    try:
        value = int(raw if raw is not None else default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _component_name(environ: Mapping[str, str]) -> str:
    raw_component = (
        str(environ.get("EMPIRE_COMPONENT") or "").strip()
        or Path(sys.argv[0] or "python").name
    )
    return (
        re.sub(r"[^A-Za-z0-9_.-]+", "-", raw_component)[:80]
        or "python"
    )


@dataclass(frozen=True)
class LegacyEgressConfig:
    state_path: Path
    lock_path: Path
    hourly_budget: int
    component_hourly_budget: int
    daily_budget: int
    probe_seconds: int

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "LegacyEgressConfig":
        source = os.environ if environ is None else environ
        state_path = Path(
            source.get("EMPIRE_LEGACY_DATA_EGRESS_STATE_PATH")
            or source.get("EMPIRE_SUPABASE_EGRESS_STATE_PATH")
            or "/srv/empire_os/runtime/control/supabase_egress_state.json"
        )
        lock_path = Path(
            source.get("EMPIRE_LEGACY_DATA_EGRESS_LOCK_PATH")
            or source.get("EMPIRE_SUPABASE_EGRESS_LOCK_PATH")
            or "/srv/empire_os/runtime/control/supabase_egress_state.lock"
        )
        return cls(
            state_path=state_path,
            lock_path=lock_path,
            hourly_budget=_env_int(
                source,
                (
                    "EMPIRE_LEGACY_DATA_MAX_REQUESTS_PER_HOUR",
                    "EMPIRE_SUPABASE_MAX_REQUESTS_PER_HOUR",
                ),
                DEFAULT_HOURLY_BUDGET,
            ),
            component_hourly_budget=_env_int(
                source,
                (
                    "EMPIRE_LEGACY_DATA_MAX_REQUESTS_PER_COMPONENT_HOUR",
                    "EMPIRE_SUPABASE_MAX_REQUESTS_PER_COMPONENT_HOUR",
                ),
                DEFAULT_COMPONENT_HOURLY_BUDGET,
            ),
            daily_budget=_env_int(
                source,
                (
                    "EMPIRE_LEGACY_DATA_MAX_REQUESTS_PER_DAY",
                    "EMPIRE_SUPABASE_MAX_REQUESTS_PER_DAY",
                ),
                DEFAULT_DAILY_BUDGET,
            ),
            probe_seconds=_env_int(
                source,
                (
                    "EMPIRE_LEGACY_DATA_EGRESS_PROBE_SECONDS",
                    "EMPIRE_SUPABASE_EGRESS_PROBE_SECONDS",
                ),
                DEFAULT_PROBE_SECONDS,
                minimum=60,
            ),
        )


class LegacyDataEgressGovernor:
    """Cross-process request budget and recovery-probe circuit."""

    def __init__(
        self,
        config: LegacyEgressConfig,
        *,
        environ: Mapping[str, str] | None = None,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._config = config
        self._environ = os.environ if environ is None else environ
        self._now = now

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        now: Callable[[], float] = time.time,
    ) -> "LegacyDataEgressGovernor":
        source = os.environ if environ is None else environ
        return cls(
            LegacyEgressConfig.from_environment(source),
            environ=source,
            now=now,
        )

    @property
    def state_path(self) -> Path:
        return self._config.state_path

    @property
    def lock_path(self) -> Path:
        return self._config.lock_path

    def load_state(self) -> dict[str, Any]:
        try:
            value = json.loads(
                self._config.state_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _write_state(self, state: dict[str, Any]) -> None:
        path = self._config.state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(state, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.chmod(tmp, 0o666)
        tmp.replace(path)
        os.chmod(path, 0o666)

    def _with_lock(self, fn: Callable[[], Any]) -> Any:
        path = self._config.lock_path
        path.parent.mkdir(parents=True, exist_ok=True)

        old_umask = os.umask(0)
        try:
            fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o666)
        finally:
            os.umask(old_umask)

        with os.fdopen(fd, "a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                return fn()
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def reserve(self, *, allow_probe: bool = False) -> None:
        now = self._now()

        def reserve_locked() -> None:
            state = self.load_state()
            circuit = state.get("circuit")
            if isinstance(circuit, dict) and circuit.get("open") is True:
                next_probe_at = float(circuit.get("next_probe_at") or 0)
                if now < next_probe_at:
                    remaining = max(1, int(next_probe_at - now))
                    raise RuntimeError(
                        "Legacy data egress circuit open locally; "
                        f"next probe in {remaining}s"
                    )
                if not allow_probe:
                    raise RuntimeError(
                        "Legacy data egress circuit open locally; "
                        "probe reserved for dedicated egress guard"
                    )
                circuit["next_probe_at"] = now + self._config.probe_seconds
                circuit["last_probe_reserved_at"] = now
                state["circuit"] = circuit
                self._write_state(state)
                return

            hour_bucket = int(now // 3600)
            day_bucket = int(now // 86400)
            counts = state.get("counts")
            counts = dict(counts) if isinstance(counts, dict) else {}

            if counts.get("hour_bucket") != hour_bucket:
                counts["hour_bucket"] = hour_bucket
                counts["hour_count"] = 0
            if counts.get("day_bucket") != day_bucket:
                counts["day_bucket"] = day_bucket
                counts["day_count"] = 0

            hour_count = int(counts.get("hour_count") or 0)
            day_count = int(counts.get("day_count") or 0)

            component = _component_name(self._environ)
            components = counts.get("components")
            components = dict(components) if isinstance(components, dict) else {}
            component_state = components.get(component)
            component_state = (
                dict(component_state)
                if isinstance(component_state, dict)
                else {}
            )
            if component_state.get("hour_bucket") != hour_bucket:
                component_state["hour_bucket"] = hour_bucket
                component_state["hour_count"] = 0
            component_hour_count = int(
                component_state.get("hour_count") or 0
            )

            reason = None
            if component_hour_count >= self._config.component_hourly_budget:
                reason = "component_hourly_request_budget_exceeded:" + component
            elif hour_count >= self._config.hourly_budget:
                reason = "hourly_request_budget_exceeded"
            elif day_count >= self._config.daily_budget:
                reason = "daily_request_budget_exceeded"

            if reason is not None:
                reset_at = (
                    (hour_bucket + 1) * 3600
                    if reason.startswith(("hourly", "component_hourly"))
                    else (day_bucket + 1) * 86400
                )
                state["circuit"] = {
                    "open": True,
                    "reason": reason,
                    "opened_at": now,
                    "next_probe_at": reset_at,
                    "source": "local_request_budget",
                }
                state["counts"] = counts
                self._write_state(state)
                raise RuntimeError(
                    "Legacy data egress circuit opened locally: " + reason
                )

            counts["hour_count"] = hour_count + 1
            counts["day_count"] = day_count + 1
            component_state["hour_count"] = component_hour_count + 1
            component_state["updated_at"] = now
            components[component] = component_state
            counts["components"] = components
            counts["updated_at"] = now
            state["counts"] = counts
            self._write_state(state)

        self._with_lock(reserve_locked)

    def open(self, reason: str, *, source: str = "legacy_response") -> None:
        now = self._now()

        def update() -> None:
            state = self.load_state()
            state["circuit"] = {
                "open": True,
                "reason": reason,
                "opened_at": now,
                "next_probe_at": now + self._config.probe_seconds,
                "source": source,
            }
            self._write_state(state)

        self._with_lock(update)

    def success(self, *, recovery_probe: bool = False) -> None:
        if not recovery_probe:
            return

        def update() -> None:
            state = self.load_state()
            circuit = state.get("circuit")
            if not isinstance(circuit, dict) or circuit.get("open") is not True:
                return
            state["circuit"] = {
                "open": False,
                "reason": "probe_succeeded",
                "closed_at": self._now(),
            }
            self._write_state(state)

        self._with_lock(update)

    def observe_http_error(self, code: int, body: str) -> bool:
        restricted = (
            int(code) == 402
            and (
                "exceed_egress_quota" in body
                or "restricted due to the following violations" in body
            )
        )
        if restricted:
            self.open(
                "exceed_egress_quota",
                source="legacy_response",
            )
        return restricted

    def is_contained(self) -> bool:
        state = self.load_state()
        circuit = state.get("circuit")
        return (
            isinstance(circuit, dict)
            and circuit.get("open") is True
        )



def reserve_legacy_data_request(*, allow_probe: bool = False) -> None:
    """Compatibility entrypoint for runtimes not yet behind the legacy adapter."""
    LegacyDataEgressGovernor.from_environment().reserve(
        allow_probe=allow_probe
    )


def open_legacy_data_egress_circuit(reason: str) -> None:
    LegacyDataEgressGovernor.from_environment().open(reason)


def close_legacy_data_egress_circuit(
    *,
    recovery_probe: bool = False,
) -> None:
    LegacyDataEgressGovernor.from_environment().success(
        recovery_probe=recovery_probe
    )



def legacy_data_component_name(
    environ: Mapping[str, str] | None = None,
) -> str:
    source = os.environ if environ is None else environ
    return _component_name(source)
