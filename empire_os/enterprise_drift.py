"""Phase 17 enterprise control and SLO evidence drift review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from empire_os.enterprise_controls import ControlEvidence, SloObservation


@dataclass(frozen=True)
class ControlDrift:
    control_key: str
    baseline_status: str
    current_status: str
    changed: bool
    direction: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SloDrift:
    service_key: str
    metric: str
    window: str
    baseline_observed: float | None
    current_observed: float | None
    baseline_margin: float | None
    current_margin: float | None
    margin_delta: float | None
    trend: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EnterpriseDriftReview:
    comparison_available: bool
    control_drift: tuple[ControlDrift, ...]
    slo_drift: tuple[SloDrift, ...]
    blockers: tuple[str, ...]
    mode: str = "OBSERVE"
    side_effects: str = "none"
    execution_authority: str = "none"
    control_mutation: bool = False
    infrastructure_mutation: bool = False
    slo_target_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "control_drift": [row.as_dict() for row in self.control_drift],
            "slo_drift": [row.as_dict() for row in self.slo_drift],
        }


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


def _is_fresh(
    observed_at: str,
    *,
    now: datetime,
    max_age_seconds: int,
) -> tuple[bool, str | None]:
    observed = _parse_timestamp(observed_at)
    age = (now - observed).total_seconds()
    if age < -60:
        return False, "future"
    if age > max_age_seconds:
        return False, "stale"
    return True, None


def _control_direction(baseline: str, current: str) -> str:
    if baseline == current:
        return "stable"
    rank = {"fail": 0, "unknown": 1, "pass": 2}
    if rank[current] > rank[baseline]:
        return "improving"
    return "declining"


def review_enterprise_drift(
    *,
    baseline_controls: Iterable[ControlEvidence],
    current_controls: Iterable[ControlEvidence],
    baseline_slos: Iterable[SloObservation],
    current_slos: Iterable[SloObservation],
    now: datetime,
    max_age_seconds: int = 21600,
) -> EnterpriseDriftReview:
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    current_time = now.astimezone(timezone.utc)

    bc = list(baseline_controls)
    cc = list(current_controls)
    bs = list(baseline_slos)
    cs = list(current_slos)
    for row in bc + cc:
        row.validate()
    if not bc or not cc:
        raise ValueError("baseline and current control evidence required")
    if not bs or not cs:
        raise ValueError("baseline and current SLO evidence required")

    blockers: list[str] = []
    for label, rows in (
        ("baseline_control", bc),
        ("current_control", cc),
        ("baseline_slo", bs),
        ("current_slo", cs),
    ):
        for row in rows:
            fresh, reason = _is_fresh(
                row.observed_at,
                now=current_time,
                max_age_seconds=max_age_seconds,
            )
            if not fresh:
                key = (
                    row.control_key
                    if isinstance(row, ControlEvidence)
                    else f"{row.service_key}:{row.metric}:{row.window}"
                )
                blockers.append(f"{label}_{key}_evidence_{reason}")

    baseline_control_map = {row.control_key: row for row in bc}
    current_control_map = {row.control_key: row for row in cc}
    control_rows: list[ControlDrift] = []
    for key in sorted(set(baseline_control_map) | set(current_control_map)):
        before = baseline_control_map.get(key)
        after = current_control_map.get(key)
        if before is None or after is None:
            blockers.append(f"control_{key}_comparison_evidence_missing")
            continue
        if _parse_timestamp(after.observed_at) <= _parse_timestamp(before.observed_at):
            blockers.append(f"control_{key}_chronology_invalid")
            continue
        control_rows.append(ControlDrift(
            control_key=key,
            baseline_status=before.status,
            current_status=after.status,
            changed=before.status != after.status,
            direction=_control_direction(before.status, after.status),
        ))

    def slo_key(row: SloObservation) -> tuple[str, str, str]:
        return (row.service_key, row.metric, row.window)

    baseline_slo_map = {slo_key(row): row for row in bs}
    current_slo_map = {slo_key(row): row for row in cs}
    slo_rows: list[SloDrift] = []
    for key in sorted(set(baseline_slo_map) | set(current_slo_map)):
        before = baseline_slo_map.get(key)
        after = current_slo_map.get(key)
        label = ":".join(key)
        if before is None or after is None:
            blockers.append(f"slo_{label}_comparison_evidence_missing")
            continue
        if _parse_timestamp(after.observed_at) <= _parse_timestamp(before.observed_at):
            blockers.append(f"slo_{label}_chronology_invalid")
            continue

        baseline_margin = (
            float(before.observed) - float(before.target)
            if before.observed is not None
            else None
        )
        current_margin = (
            float(after.observed) - float(after.target)
            if after.observed is not None
            else None
        )
        delta = None
        trend = "unknown"
        if baseline_margin is not None and current_margin is not None:
            delta = current_margin - baseline_margin
            if abs(delta) <= 1e-12:
                trend = "stable"
            elif delta > 0:
                trend = "improving"
            else:
                trend = "declining"
        else:
            blockers.append(f"slo_{label}_observed_value_missing")

        slo_rows.append(SloDrift(
            service_key=key[0],
            metric=key[1],
            window=key[2],
            baseline_observed=before.observed,
            current_observed=after.observed,
            baseline_margin=baseline_margin,
            current_margin=current_margin,
            margin_delta=(round(delta, 6) if delta is not None else None),
            trend=trend,
        ))

    ordered = tuple(sorted(set(blockers)))
    return EnterpriseDriftReview(
        comparison_available=not ordered,
        control_drift=tuple(control_rows),
        slo_drift=tuple(slo_rows),
        blockers=ordered,
    )
