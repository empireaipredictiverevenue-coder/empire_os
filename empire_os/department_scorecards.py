"""Astra OBSERVE scorecards: live KPI evidence -> typed read-only views.

Architecture delta: Astra owns this projection over the canonical department
registry. Callers supply tenant-scoped live observations from canonical sources
(EmpireDB for business data) and explicitly evidenced targets in matching units
and measurement periods. No database, file, queue or external writes occur.
Missing/degraded evidence fails closed to UNKNOWN; retry and source verification
belong to the caller. This module neither verifies revenue nor grants authority.
Focused tests verify failure paths; rollback is removal of this unused read API.
Live runtime/canonical-data verification is required before production promotion.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Iterable, Literal

from empire_os.departments import default_departments

Freshness = Literal["FRESH", "STALE", "UNKNOWN"]
TruthClass = Literal["OBSERVED", "VERIFIED_OUTCOME"]


@dataclass(frozen=True)
class KPIEvidence:
    """One live observation; target provenance is independent of observation refs.

    Unit and period describe both current and target. A target must only be
    supplied when its scope, unit and period match the observation exactly.
    """

    department_key: str
    kpi: str
    current: float | None = None
    observed_at: datetime | None = None
    evidence_refs: tuple[str, ...] = ()
    unit: str | None = None
    period: str | None = None
    truth_class: TruthClass = "OBSERVED"
    target: float | None = None
    target_evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class KPIScorecard:
    kpi: str
    current: float | None
    target: float | None
    variance: float | None
    freshness: Freshness
    status: Literal["KNOWN", "UNKNOWN"]
    observed_at: str | None
    age_seconds: float | None
    evidence_refs: tuple[str, ...]
    target_evidence_refs: tuple[str, ...]
    unit: str | None
    period: str | None
    truth_class: TruthClass | None
    unknown_reasons: tuple[str, ...]


@dataclass(frozen=True)
class DepartmentScorecard:
    department_key: str
    name: str
    generated_at: str
    kpis: tuple[KPIScorecard, ...]
    authority: Literal["OBSERVE"] = "OBSERVE"
    schema_version: str = "empire.department_scorecard.v1"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return isfinite(value)
    except OverflowError:
        return False


def _refs(values: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        return ()
    return tuple(dict.fromkeys(v.strip() for v in values if isinstance(v, str) and v.strip()))


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _score(kpi: str, rows: list[KPIEvidence], now: datetime, max_age: timedelta) -> KPIScorecard:
    row = rows[0] if len(rows) == 1 else KPIEvidence("", kpi)
    reasons: list[str] = []
    if not rows:
        reasons.append("missing_evidence")
    elif len(rows) > 1:
        # Do not silently choose between conflicting or differently scoped rows.
        reasons.append("ambiguous_evidence")
    refs = _refs(row.evidence_refs)
    target_refs = _refs(row.target_evidence_refs)
    age = (now - row.observed_at).total_seconds() if _aware(row.observed_at) else None
    freshness: Freshness = "UNKNOWN"
    if age is not None and age >= 0:
        freshness = "FRESH" if age <= max_age.total_seconds() else "STALE"
    if freshness != "FRESH":
        reasons.append("stale_evidence" if freshness == "STALE" else "unknown_freshness")
    if not refs:
        reasons.append("missing_evidence_refs")
    if not _number(row.current):
        reasons.append("invalid_or_missing_current")
    truth = row.truth_class if row.truth_class in ("OBSERVED", "VERIFIED_OUTCOME") else None
    if truth is None:
        reasons.append("unsupported_truth_class")
    current = row.current if not reasons else None
    target = row.target if _number(row.target) and target_refs else None
    if target is None:
        reasons.append("unknown_target")
    unit = row.unit if isinstance(row.unit, str) and row.unit.strip() else None
    period = row.period if isinstance(row.period, str) and row.period.strip() else None
    if unit is None or period is None:
        reasons.append("unknown_comparison_scope")
    variance = current - target if current is not None and target is not None and unit and period else None
    if variance is not None and not _number(variance):
        variance = None
        reasons.append("invalid_variance")
    return KPIScorecard(
        kpi=kpi, current=current, target=target, variance=variance,
        freshness=freshness, status="KNOWN" if variance is not None else "UNKNOWN",
        observed_at=row.observed_at.isoformat() if _aware(row.observed_at) else None,
        age_seconds=age, evidence_refs=refs, target_evidence_refs=target_refs,
        unit=unit, period=period, truth_class=truth if current is not None else None,
        unknown_reasons=tuple(reasons),
    )


def build_department_scorecards(
    evidence: Iterable[KPIEvidence] = (),
    *,
    max_age: timedelta,
    now: datetime | None = None,
) -> tuple[DepartmentScorecard, ...]:
    """Build every registered KPI, with no default targets or department ranking.

    Freshness policy must be explicit. Missing observations (including source
    outages represented by no evidence) remain UNKNOWN, never zero. Stale values
    are withheld from current/variance. Variance is current minus target, not a
    performance judgement. Duplicate observations fail closed for that KPI.
    """
    now = datetime.now(timezone.utc) if now is None else now
    if not _aware(now):
        raise ValueError("now must be timezone-aware")
    if not isinstance(max_age, timedelta) or max_age.total_seconds() < 0:
        raise ValueError("max_age must be a nonnegative timedelta")
    departments = default_departments()
    allowed = {(d.key, kpi) for d in departments for kpi in d.kpis}
    grouped: dict[tuple[str, str], list[KPIEvidence]] = {}
    for row in evidence:
        if not isinstance(row, KPIEvidence):
            raise TypeError("evidence must contain KPIEvidence records")
        key = (row.department_key, row.kpi)
        if key not in allowed:
            raise ValueError(f"unregistered department/KPI: {key!r}")
        grouped.setdefault(key, []).append(row)
    return tuple(
        DepartmentScorecard(
            department_key=d.key, name=d.name, generated_at=now.isoformat(),
            kpis=tuple(_score(kpi, grouped.get((d.key, kpi), []), now, max_age) for kpi in d.kpis),
        )
        for d in departments
    )
