"""Deterministic inbound demand-loss pattern analysis using provider events only.

Low sample sizes return insufficient evidence, never invented insights, and
never a revenue/ROI forecast. Local time uses the business's verified TZ.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from empire_os.inbound_revenue_recovery import MISSED_STATUSES, RecoveryEvent


@dataclass(frozen=True)
class PatternPolicy:
    tenant_id: str
    timezone_name: str
    window_days: int = 28
    minimum_calls: int = 20
    minimum_segment_calls: int = 5
    minimum_missed_calls: int = 3
    alert_rate_percent: int = 40

    def __post_init__(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id_required")
        try:
            ZoneInfo(self.timezone_name)
        except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
            raise ValueError("valid_timezone_required") from exc
        for field_name, maximum in (
            ("window_days", 90), ("minimum_calls", 1000),
            ("minimum_segment_calls", 500), ("minimum_missed_calls", 500),
            ("alert_rate_percent", 100),
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
                raise ValueError("invalid_pattern_threshold")


def _ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _daypart(hour: int) -> str:
    if hour < 6:
        return "overnight"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


def analyse_inbound_patterns(
    events: list[RecoveryEvent] | tuple[RecoveryEvent, ...],
    *,
    as_of: datetime,
    policy: PatternPolicy,
) -> dict[str, Any]:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of_must_be_timezone_aware")
    by_call: dict[str, list[RecoveryEvent]] = defaultdict(list)
    since = as_of - timedelta(days=policy.window_days)
    seen: dict[str, RecoveryEvent] = {}
    for event in events:
        if not isinstance(event, RecoveryEvent):
            raise ValueError("invalid_recovery_event")
        if event.tenant_id != policy.tenant_id or event.synthetic:
            continue
        if not event.verified or event.origin != "provider":
            continue
        stamp = _ts(event.occurred_at)
        if not since <= stamp <= as_of:
            continue
        previous = seen.get(event.event_id)
        if previous is not None:
            if previous != event:
                raise ValueError("conflicting_provider_event_id")
            continue
        seen[event.event_id] = event
        by_call[event.call_id].append(event)
    by_segment: dict[str, dict[str, int]] = defaultdict(
        lambda: {"calls": 0, "missed_calls": 0}
    )
    observed = missed_total = ambiguous = 0
    timezone = ZoneInfo(policy.timezone_name)
    for call_events in by_call.values():
        # Only terminal answer or missed provider evidence should classify calls.
        missed_statuses = [e for e in call_events if e.kind in MISSED_STATUSES]
        answered_statuses = [e for e in call_events if e.kind in {"answered", "completed"}]
        if missed_statuses and answered_statuses:
            ambiguous += 1
            continue
        if not missed_statuses and not answered_statuses:
            continue
        selected = min(
            missed_statuses if missed_statuses else answered_statuses,
            key=lambda e: (_ts(e.occurred_at), e.event_id),
        )
        local = _ts(selected.occurred_at).astimezone(timezone)
        segment = f"{local.weekday()}:{_daypart(local.hour)}"
        by_segment[segment]["calls"] += 1
        missed = bool(missed_statuses)
        by_segment[segment]["missed_calls"] += int(missed)
        observed += 1
        missed_total += int(missed)

    cohort_sufficient = observed >= policy.minimum_calls
    alerts: list[dict[str, Any]] = []
    for segment, bucket in sorted(by_segment.items()):
        if not cohort_sufficient:
            break
        n, misses = bucket["calls"], bucket["missed_calls"]
        if n < policy.minimum_segment_calls or misses < policy.minimum_missed_calls:
            continue
        rate = round(100 * misses / n, 1)
        if rate < policy.alert_rate_percent:
            continue
        weekday, daypart = segment.split(":")
        alerts.append({
            "weekday": int(weekday),
            "daypart": daypart,
            "provider_observed_calls": n,
            "provider_verified_missed_calls": misses,
            "observed_missed_rate_percent": rate,
            "priority": "operator_capacity_review",
            "reason": "recurring_verified_missed_calls_above_configured_threshold",
            "action": "review_business_staffing_and_callback_process",
            "automated_changes": False,
            "estimated_revenue": None,
        })
    alerts.sort(key=lambda a: (
        -a["provider_verified_missed_calls"], -a["observed_missed_rate_percent"],
        a["weekday"], a["daypart"],
    ))
    return {
        "tenant_id": policy.tenant_id,
        "mode": "offline_observational_patterns_only",
        "as_of": as_of.isoformat(),
        "timezone": policy.timezone_name,
        "window_days": policy.window_days,
        "cohort_sufficient": cohort_sufficient,
        "sample_size": observed,
        "missed_calls": missed_total,
        "overall_missed_rate_percent": (
            round(100 * missed_total / observed, 1) if observed else None
        ),
        "ambiguous_dispositions_excluded": ambiguous,
        "alerts": alerts,
        "revenue_estimated": False,
        "predictive_causal_claims": False,
        "customer_contact_authorized": False,
    }
