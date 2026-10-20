"""Timezone-aware verified staffed-hours policy for AI reception previews.

Staffed hours are not bookable inventory. Never infer that a person is
available, or a booking is confirmed, merely because the business is open.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from empire_os.inbound_revenue_recovery import (
    ReceptionDecision,
    TenantReceptionProfile,
    plan_reception_response,
)


def _hhmm(value: str) -> time:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise ValueError("hours_must_be_HH_MM")
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid_hours_time") from exc


@dataclass(frozen=True)
class StaffedWindow:
    weekday: int  # Monday=0, Sunday=6
    opens: str
    closes: str

    def __post_init__(self) -> None:
        if isinstance(self.weekday, bool) or self.weekday not in range(7):
            raise ValueError("invalid_weekday")
        if _hhmm(self.opens) >= _hhmm(self.closes):
            raise ValueError("overnight_or_empty_window_not_supported")


@dataclass(frozen=True)
class BusinessHoursPolicy:
    tenant_id: str
    timezone_name: str
    windows: tuple[StaffedWindow, ...] = ()
    closed_dates: tuple[str, ...] = ()
    verified: bool = False

    def __post_init__(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id_required")
        try:
            ZoneInfo(self.timezone_name)
        except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
            raise ValueError("invalid_business_timezone") from exc
        for closed_date in self.closed_dates:
            try:
                if date.fromisoformat(closed_date).isoformat() != closed_date:
                    raise ValueError()
            except (ValueError, TypeError) as exc:
                raise ValueError("invalid_closed_date") from exc
        per_day: dict[int, list[StaffedWindow]] = {}
        for window in self.windows:
            per_day.setdefault(window.weekday, []).append(window)
        for days in per_day.values():
            ordered = sorted(days, key=lambda window: window.opens)
            for current, later in zip(ordered, ordered[1:]):
                if current.closes > later.opens:
                    raise ValueError("overlapping_staffed_hours")


@dataclass(frozen=True)
class StaffedHoursStatus:
    tenant_id: str
    verified: bool
    open_now: bool | None
    local_date: str
    next_open_at: str | None
    reason: str


def staffed_hours_status(
    policy: BusinessHoursPolicy, when: datetime, *, lookahead_days: int = 14
) -> StaffedHoursStatus:
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("aware_datetime_required")
    if not (1 <= lookahead_days <= 31):
        raise ValueError("invalid_hours_lookahead")
    tz = ZoneInfo(policy.timezone_name)
    local = when.astimezone(tz)
    today = local.date()
    if not policy.verified:
        return StaffedHoursStatus(
            tenant_id=policy.tenant_id, verified=False, open_now=None,
            local_date=today.isoformat(), next_open_at=None,
            reason="hours_not_verified",
        )
    closed_dates = set(policy.closed_dates)
    today_windows = (
        [w for w in policy.windows if w.weekday == today.weekday()]
        if today.isoformat() not in closed_dates else []
    )
    open_now = any(
        _hhmm(w.opens) <= local.time().replace(tzinfo=None) < _hhmm(w.closes)
        for w in today_windows
    )
    upcoming: datetime | None = None
    for offset in range(lookahead_days + 1):
        day = today + timedelta(days=offset)
        if day.isoformat() in closed_dates:
            continue
        for w in policy.windows:
            if day.weekday() != w.weekday:
                continue
            opening = datetime.combine(day, _hhmm(w.opens), tzinfo=tz)
            # Round-trip normalization copes with UK summer-time clock changes.
            opening = opening.astimezone(timezone.utc).astimezone(tz)
            if opening > local and (upcoming is None or opening < upcoming):
                upcoming = opening
    return StaffedHoursStatus(
        tenant_id=policy.tenant_id, verified=True, open_now=open_now,
        local_date=today.isoformat(),
        next_open_at=upcoming.isoformat() if upcoming else None,
        reason="within_verified_hours" if open_now else "outside_verified_hours",
    )


def plan_hours_aware_reception_response(
    profile: TenantReceptionProfile,
    policy: BusinessHoursPolicy,
    when: datetime,
    intent: str,
) -> ReceptionDecision:
    if profile.tenant_id != policy.tenant_id:
        raise ValueError("business_hours_tenant_mismatch")
    normal = plan_reception_response(profile, intent)
    if normal.action in {"honour_opt_out", "urgent_human_escalation"}:
        return normal
    hours = staffed_hours_status(policy, when)
    if intent.strip().lower() in {"human", "complaint", "sensitive"} and hours.open_now is not True:
        return ReceptionDecision(
            "request_human_followup",
            f"I am the AI assistant for {profile.business_name}. "
            "I cannot confirm a staffed transfer right now. "
            "Would you like to request follow-up from the team?",
            reason=hours.reason,
        )
    return normal
