"""Phase 18 evidence freshness gate for Revenue OS."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


COMPONENTS = (
    "astra",
    "predictive",
    "capital",
    "demand",
    "enterprise",
)


@dataclass(frozen=True)
class RevenueOsFreshness:
    fresh_for_review: bool
    component_ages_seconds: Mapping[str, float | None]
    blockers: tuple[str, ...]
    mode: str = "OBSERVE"
    side_effects: str = "none"
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["component_ages_seconds"] = dict(
            self.component_ages_seconds
        )
        return data


def _parse_timestamp(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("evidence timestamp required")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("evidence timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("evidence timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def assess_revenue_os_freshness(
    observed_at: Mapping[str, str | None],
    *,
    now: datetime,
    max_age_seconds: int = 21600,
) -> RevenueOsFreshness:
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    current = now.astimezone(timezone.utc)
    blockers: list[str] = []
    ages: dict[str, float | None] = {}

    for component in COMPONENTS:
        raw = observed_at.get(component)
        if raw is None or not str(raw).strip():
            ages[component] = None
            blockers.append(f"{component}_evidence_timestamp_missing")
            continue

        observed = _parse_timestamp(str(raw))
        age = (current - observed).total_seconds()
        ages[component] = round(age, 3)

        if age < -60:
            blockers.append(f"{component}_evidence_from_future")
        elif age > max_age_seconds:
            blockers.append(f"{component}_evidence_stale")

    ordered = tuple(sorted(set(blockers)))
    return RevenueOsFreshness(
        fresh_for_review=not ordered,
        component_ages_seconds=ages,
        blockers=ordered,
    )
