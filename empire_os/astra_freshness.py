"""Freshness validation for canonical Astra operational evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class AstraFreshnessResult:
    fresh: bool
    observed_at: str | None
    age_seconds: float | None
    reason: str


def _parse_utc(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("operational evidence observed_at is required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("operational evidence observed_at is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("operational evidence observed_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def validate_astra_operational_freshness(
    operational_row: Mapping[str, Any],
    *,
    now: datetime | None = None,
    max_age_seconds: int = 21600,
) -> AstraFreshnessResult:
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    observed = _parse_utc(operational_row.get("observed_at"))
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age = (current - observed).total_seconds()

    if age < -60:
        return AstraFreshnessResult(
            fresh=False,
            observed_at=observed.isoformat(),
            age_seconds=round(age, 3),
            reason="operational_evidence_from_future",
        )
    if age > max_age_seconds:
        return AstraFreshnessResult(
            fresh=False,
            observed_at=observed.isoformat(),
            age_seconds=round(age, 3),
            reason="operational_evidence_stale",
        )
    return AstraFreshnessResult(
        fresh=True,
        observed_at=observed.isoformat(),
        age_seconds=round(max(age, 0.0), 3),
        reason="operational_evidence_fresh",
    )
