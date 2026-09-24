"""Self-healing containment for Supabase egress pressure.

The guard performs one tiny canonical probe. If hosted egress is restricted or
EmpireOS's local request budget is open, it stops only the explicit high-egress
timer allowlist. When a later probe succeeds, it restarts only timers that are
still enabled, staggered to avoid a recovery thundering herd.

It never touches inbound email, payment/revenue workers, database schema,
credentials, or commercial authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Callable

from empire_os.qualification_worker_v2 import request_json


STATUS_PATH = Path(
    "/srv/empire_os/runtime/control/supabase_egress_guard.json"
)

MANAGED_TIMERS = (
    "empire-acquisition.timer",
    "empire-astra-dispatcher.timer",
    "empire-astra-observer.timer",
    "empire-buyer-acquisition-scout.timer",
    "empire-buyer-capacity-readiness.timer",
    "empire-buyer-deferred-enrichment.timer",
    "empire-buyer-review-materializer.timer",
    "empire-commercial-evidence-auto-verifier.timer",
    "empire-commercial-product-catalog.timer",
    "empire-conversation-recovery.timer",
    "empire-gtm-pipeline.timer",
    "empire-outbound-followup.timer",
    "empire-predictive-intelligence.timer",
    "empire-predictive-revenue-enterprise-activation.timer",
    "empire-private-capital-snapshot.timer",
    "empire-qualification-booster.timer",
    "empire-qualification.timer",
    "empire-commercial-exchange.timer",
    "empire-outbound-governor.timer",
    "empire-department-cycle.timer",
    "empire-closer-reply-worker.timer",
)


Run = Callable[..., subprocess.CompletedProcess]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_status(payload: dict[str, Any]) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS_PATH.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(STATUS_PATH)


def _systemctl(
    run: Run,
    *args: str,
) -> subprocess.CompletedProcess:
    return run(
        ["systemctl", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _is_enabled(run: Run, unit: str) -> bool:
    result = _systemctl(run, "is-enabled", unit)
    return result.returncode == 0 and result.stdout.strip() == "enabled"


def _stop_contained_units(run: Run) -> list[str]:
    managed: list[str] = []
    for timer in MANAGED_TIMERS:
        if _is_enabled(run, timer):
            managed.append(timer)
        _systemctl(run, "stop", timer)
        service = timer.removesuffix(".timer") + ".service"
        _systemctl(run, "stop", service)
    return managed


def _restore_units(
    run: Run,
    timers: list[str],
    *,
    stagger_seconds: float,
    sleep: Callable[[float], None],
) -> list[str]:
    restored: list[str] = []
    for timer in timers:
        if timer not in MANAGED_TIMERS:
            continue
        if not _is_enabled(run, timer):
            continue
        result = _systemctl(run, "start", timer)
        if result.returncode == 0:
            restored.append(timer)
            if stagger_seconds > 0:
                sleep(stagger_seconds)
    return restored


def _existing_managed() -> list[str]:
    try:
        payload = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("managed_timers") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    return [
        str(value)
        for value in rows
        if str(value) in MANAGED_TIMERS
    ]


def run_guard(
    *,
    request=request_json,
    run: Run = subprocess.run,
    sleep: Callable[[float], None] = time.sleep,
    stagger_seconds: float = 5.0,
) -> dict[str, Any]:
    """Run one guard cycle and return a non-consequential status payload."""
    try:
        request(
            "GET",
            "/rest/v1/prospects?select=id&limit=1",
        )
    except Exception as exc:
        message = str(exc)
        restricted = (
            "HTTP 402" in message
            or "exceed_egress_quota" in message
            or "egress circuit open locally" in message
            or "egress circuit opened locally" in message
        )
        if not restricted:
            payload = {
                "schema_version": "empire.supabase-egress-guard.v1",
                "observed_at": _now(),
                "state": "probe_error",
                "contained": False,
                "error": f"{type(exc).__name__}:{message[:300]}",
                "inbound_mail_touched": False,
                "revenue_mutation": False,
            }
            _write_status(payload)
            return payload

        previous = _existing_managed()
        managed = _stop_contained_units(run)
        managed = list(dict.fromkeys(previous + managed))
        payload = {
            "schema_version": "empire.supabase-egress-guard.v1",
            "observed_at": _now(),
            "state": "contained",
            "contained": True,
            "reason": message[:300],
            "managed_timers": managed,
            "inbound_mail_touched": False,
            "revenue_mutation": False,
        }
        _write_status(payload)
        return payload

    previous = _existing_managed()
    restored = _restore_units(
        run,
        previous,
        stagger_seconds=max(0.0, float(stagger_seconds)),
        sleep=sleep,
    )
    payload = {
        "schema_version": "empire.supabase-egress-guard.v1",
        "observed_at": _now(),
        "state": "healthy",
        "contained": False,
        "restored_timers": restored,
        "managed_timers": [],
        "inbound_mail_touched": False,
        "revenue_mutation": False,
    }
    _write_status(payload)
    return payload
