"""Pure, read-only circuit-breaker evidence evaluation for EmpireOS.

The evaluator never mutates production state. It derives CLOSED / OPEN /
HALF_OPEN from supplied timestamped failure/success evidence and an injected
clock, making the result deterministic and suitable for Founder Console use.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

CLOSED = "CLOSED"
OPEN = "OPEN"
HALF_OPEN = "HALF_OPEN"

DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_FAILURE_WINDOW_SECONDS = 3600
DEFAULT_COOLDOWN_SECONDS = 300


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime evidence must include timezone")
    return value.astimezone(timezone.utc)


def _parse_event_times(
    events: Iterable[Mapping[str, Any]] | None,
    *,
    now: datetime,
) -> tuple[datetime, ...]:
    parsed: list[datetime] = []
    for event in events or ():
        raw = str(event.get("at") or "").strip()
        if not raw:
            continue
        try:
            stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if stamp.tzinfo is None:
            continue
        stamp = stamp.astimezone(timezone.utc)
        if stamp <= now:
            parsed.append(stamp)
    return tuple(sorted(parsed))


def _most_recent_trip(
    failures: tuple[datetime, ...],
    *,
    threshold: int,
    window: timedelta,
) -> datetime | None:
    if len(failures) < threshold:
        return None

    start = 0
    trip_at: datetime | None = None
    for end, stamp in enumerate(failures):
        while start <= end and stamp - failures[start] > window:
            start += 1
        count = end - start + 1
        if count >= threshold:
            trip_at = stamp
    return trip_at


def evaluate_circuit(
    key: str,
    *,
    failure_events: Iterable[Mapping[str, Any]] | None = None,
    success_events: Iterable[Mapping[str, Any]] | None = None,
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
    failure_window_seconds: int = DEFAULT_FAILURE_WINDOW_SECONDS,
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    clean_key = str(key or "").strip()
    if not clean_key:
        raise ValueError("circuit key is required")
    if failure_threshold < 1:
        raise ValueError("failure_threshold must be >= 1")
    if failure_window_seconds < 1:
        raise ValueError("failure_window_seconds must be >= 1")
    if cooldown_seconds < 0:
        raise ValueError("cooldown_seconds must be >= 0")

    current = _utc(now or datetime.now(timezone.utc))
    failures = _parse_event_times(failure_events, now=current)
    successes = _parse_event_times(success_events, now=current)
    window = timedelta(seconds=failure_window_seconds)
    cooldown = timedelta(seconds=cooldown_seconds)

    trip_at = _most_recent_trip(
        failures,
        threshold=failure_threshold,
        window=window,
    )
    latest_failure = failures[-1] if failures else None
    latest_success = successes[-1] if successes else None

    recent_failures = tuple(
        stamp for stamp in failures
        if current - stamp <= window
    )

    state = CLOSED
    can_accept = True
    state_since: datetime | None = None
    reason = "failure_threshold_not_breached"

    if trip_at is not None:
        if latest_success is not None and latest_success > trip_at:
            state = CLOSED
            can_accept = True
            state_since = latest_success
            reason = "success_after_trip"
        else:
            reference = latest_failure or trip_at
            elapsed = current - reference
            if elapsed < cooldown:
                state = OPEN
                can_accept = False
                state_since = trip_at
                reason = "failure_threshold_breached_cooldown_active"
            else:
                state = HALF_OPEN
                can_accept = True
                state_since = reference + cooldown
                reason = "cooldown_elapsed_probe_allowed"

    return {
        "key": clean_key,
        "state": state,
        "reason": reason,
        "failure_count_recent": len(recent_failures),
        "failure_threshold": failure_threshold,
        "failure_window_seconds": failure_window_seconds,
        "cooldown_seconds": cooldown_seconds,
        "trip_at": trip_at.isoformat() if trip_at else None,
        "last_failure_at": (
            latest_failure.isoformat() if latest_failure else None
        ),
        "last_success_at": (
            latest_success.isoformat() if latest_success else None
        ),
        "state_since": state_since.isoformat() if state_since else None,
        "can_accept": can_accept,
        "evaluated_at": current.isoformat(),
        "side_effects": "none",
    }


def evaluate_lane_circuit(
    lane_id: str,
    failure_events: Iterable[Mapping[str, Any]] | None = None,
    success_events: Iterable[Mapping[str, Any]] | None = None,
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    *,
    failure_window_seconds: int = DEFAULT_FAILURE_WINDOW_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    return evaluate_circuit(
        lane_id,
        failure_events=failure_events,
        success_events=success_events,
        failure_threshold=failure_threshold,
        failure_window_seconds=failure_window_seconds,
        cooldown_seconds=cooldown_seconds,
        now=now,
    )


def evaluate_provider_circuit(
    provider_name: str,
    failure_events: Iterable[Mapping[str, Any]] | None = None,
    success_events: Iterable[Mapping[str, Any]] | None = None,
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    *,
    failure_window_seconds: int = DEFAULT_FAILURE_WINDOW_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    return evaluate_circuit(
        f"provider:{str(provider_name or '').strip()}",
        failure_events=failure_events,
        success_events=success_events,
        failure_threshold=failure_threshold,
        failure_window_seconds=failure_window_seconds,
        cooldown_seconds=cooldown_seconds,
        now=now,
    )
