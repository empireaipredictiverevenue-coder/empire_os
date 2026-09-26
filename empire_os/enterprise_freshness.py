"""Phase 17 enterprise evidence freshness and SLO trend review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from empire_os.enterprise_controls import ControlEvidence, SloObservation


@dataclass(frozen=True)
class EvidenceFreshnessItem:
    kind: str
    key: str
    observed_at: str
    age_seconds: float
    freshness: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SloTrendReview:
    service_key: str
    metric: str
    window: str
    sample_count: int
    observed_sample_count: int
    trend: str
    first_margin: float | None
    latest_margin: float | None
    delta_margin: float | None
    latest_meets_target: bool | None
    observed_from: str | None
    observed_to: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EnterpriseEvidenceReview:
    fresh_for_review: bool
    trend_review_complete: bool
    freshness: tuple[EvidenceFreshnessItem, ...]
    slo_trends: tuple[SloTrendReview, ...]
    blockers: tuple[str, ...]
    mode: str = "OBSERVE"
    side_effects: str = "none"
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "freshness": [row.as_dict() for row in self.freshness],
            "slo_trends": [row.as_dict() for row in self.slo_trends],
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


def _freshness(
    *,
    kind: str,
    key: str,
    observed_at: str,
    now: datetime,
    max_age_seconds: int,
) -> EvidenceFreshnessItem:
    observed = _parse_timestamp(observed_at)
    age = (now - observed).total_seconds()
    status = "fresh"
    if age < -60:
        status = "future"
    elif age > max_age_seconds:
        status = "stale"
    return EvidenceFreshnessItem(
        kind=kind,
        key=key,
        observed_at=observed_at,
        age_seconds=round(age, 3),
        freshness=status,
    )


def _slo_trends(slos: list[SloObservation]) -> tuple[SloTrendReview, ...]:
    grouped: dict[tuple[str, str, str], list[tuple[datetime, SloObservation]]] = {}
    for row in slos:
        stamp = _parse_timestamp(row.observed_at)
        grouped.setdefault((row.service_key, row.metric, row.window), []).append(
            (stamp, row)
        )

    reviews: list[SloTrendReview] = []
    for key in sorted(grouped):
        rows = sorted(grouped[key], key=lambda item: item[0])
        observed_rows = [(stamp, row) for stamp, row in rows if row.observed is not None]
        trend = "unknown"
        first_margin = latest_margin = delta_margin = None
        observed_from = observed_to = None
        latest_meets_target = rows[-1][1].meets_target if rows else None

        if len(observed_rows) >= 2:
            first_stamp, first = observed_rows[0]
            latest_stamp, latest = observed_rows[-1]
            first_margin = float(first.observed) - float(first.target)
            latest_margin = float(latest.observed) - float(latest.target)
            delta_margin = latest_margin - first_margin
            if abs(delta_margin) <= 1e-12:
                trend = "stable"
            elif delta_margin > 0:
                trend = "improving"
            else:
                trend = "declining"
            observed_from = first_stamp.isoformat()
            observed_to = latest_stamp.isoformat()

        reviews.append(SloTrendReview(
            service_key=key[0],
            metric=key[1],
            window=key[2],
            sample_count=len(rows),
            observed_sample_count=len(observed_rows),
            trend=trend,
            first_margin=first_margin,
            latest_margin=latest_margin,
            delta_margin=delta_margin,
            latest_meets_target=latest_meets_target,
            observed_from=observed_from,
            observed_to=observed_to,
        ))
    return tuple(reviews)


def review_enterprise_evidence(
    *,
    controls: Iterable[ControlEvidence],
    slos: Iterable[SloObservation],
    now: datetime,
    max_age_seconds: int = 21600,
) -> EnterpriseEvidenceReview:
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    current = now.astimezone(timezone.utc)
    control_rows = list(controls)
    slo_rows = list(slos)
    if not control_rows:
        raise ValueError("control evidence required")
    if not slo_rows:
        raise ValueError("SLO observations required")

    for row in control_rows:
        row.validate()
    freshness: list[EvidenceFreshnessItem] = []
    for row in control_rows:
        freshness.append(_freshness(
            kind="control",
            key=row.control_key,
            observed_at=row.observed_at,
            now=current,
            max_age_seconds=max_age_seconds,
        ))
    for row in slo_rows:
        freshness.append(_freshness(
            kind="slo",
            key=f"{row.service_key}:{row.metric}:{row.window}",
            observed_at=row.observed_at,
            now=current,
            max_age_seconds=max_age_seconds,
        ))

    blockers = tuple(sorted({
        f"{row.kind}_{row.key}_evidence_{row.freshness}"
        for row in freshness
        if row.freshness != "fresh"
    }))
    trends = _slo_trends(slo_rows)
    return EnterpriseEvidenceReview(
        fresh_for_review=not blockers,
        trend_review_complete=all(row.trend != "unknown" for row in trends),
        freshness=tuple(freshness),
        slo_trends=trends,
        blockers=blockers,
    )
