"""Deterministic concurrency planner for tenant-scoped Digital Avatar fleets."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from empire_os.digital_avatar import AvatarMeetingMode
from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding


_ACTIVE_STATES = {"planned", "active"}
_TERMINAL_STATES = {"cancelled", "completed"}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("meeting reservation times must include timezone")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class FleetConcurrencyPolicy:
    tenant_id: str
    max_concurrent_meetings: int
    max_concurrent_meetings_per_avatar: int
    capacity_evidence_ref: str

    def validate(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("concurrency policy tenant_id required")
        if self.max_concurrent_meetings < 1:
            raise ValueError("max_concurrent_meetings must be positive")
        if self.max_concurrent_meetings_per_avatar != 1:
            raise ValueError(
                "V1 max_concurrent_meetings_per_avatar must equal 1"
            )
        if not self.capacity_evidence_ref.strip():
            raise ValueError("capacity evidence ref required")
@dataclass(frozen=True)
class AvatarMeetingReservation:
    tenant_id: str
    avatar_id: str
    meeting_id: str
    starts_at: datetime
    ends_at: datetime
    mode: AvatarMeetingMode
    state: str = "planned"

    def validate(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("reservation tenant_id required")
        if not self.avatar_id.strip() or not self.meeting_id.strip():
            raise ValueError("reservation avatar_id and meeting_id required")
        start = _utc(self.starts_at)
        end = _utc(self.ends_at)
        if end <= start:
            raise ValueError("reservation ends_at must be after starts_at")
        if self.mode not in {
            AvatarMeetingMode.SHADOW,
            AvatarMeetingMode.COPILOT,
        }:
            raise ValueError("reservation mode exceeds V1 authority ceiling")
        if self.state not in (_ACTIVE_STATES | _TERMINAL_STATES):
            raise ValueError("unsupported reservation state")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        value["starts_at"] = _utc(self.starts_at).isoformat()
        value["ends_at"] = _utc(self.ends_at).isoformat()
        value["mode"] = self.mode.value
        return value
@dataclass(frozen=True)
class FleetReservationDecision:
    allowed: bool
    duplicate: bool
    blockers: tuple[str, ...]
    overlapping_tenant_meetings: int
    overlapping_avatar_meetings: int
    tenant_id: str
    avatar_id: str
    meeting_id: str
    mode: str
    recommendation_only: bool = True
    reservation_persisted: bool = False
    provider_call_performed: bool = False
    meeting_join_performed: bool = False
    speech_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _overlaps(
    left: AvatarMeetingReservation,
    right: AvatarMeetingReservation,
) -> bool:
    return (
        _utc(left.starts_at) < _utc(right.ends_at)
        and _utc(right.starts_at) < _utc(left.ends_at)
    )


def _same_reservation(
    left: AvatarMeetingReservation,
    right: AvatarMeetingReservation,
) -> bool:
    return left.as_dict() == right.as_dict()
def plan_avatar_meeting_reservation(
    *,
    runtime: AvatarFleetRuntimeBinding,
    requested: AvatarMeetingReservation,
    existing: Iterable[AvatarMeetingReservation],
    policy: FleetConcurrencyPolicy,
) -> FleetReservationDecision:
    requested.validate()
    policy.validate()

    if runtime.runtime_authority != "observe":
        raise ValueError("fleet runtime authority must remain observe")
    if runtime.execution_authority != "none":
        raise ValueError("fleet runtime execution authority must remain none")
    if (
        runtime.speech_execution_allowed
        or runtime.commercial_execution_allowed
        or runtime.payment_execution_allowed
        or runtime.revenue_recognition_allowed
    ):
        raise ValueError("fleet runtime contains forbidden execution authority")
    if requested.tenant_id != runtime.tenant_id:
        raise PermissionError("reservation_runtime_tenant_mismatch")
    if requested.avatar_id != runtime.avatar_id:
        raise PermissionError("reservation_runtime_avatar_mismatch")
    if policy.tenant_id != runtime.tenant_id:
        raise PermissionError("concurrency_policy_tenant_mismatch")

    rows = tuple(existing)
    for row in rows:
        row.validate()

    duplicates = [
        row for row in rows
        if row.meeting_id == requested.meeting_id
        and _same_reservation(row, requested)
    ]
    if duplicates:
        return FleetReservationDecision(
            allowed=True,
            duplicate=True,
            blockers=(),
            overlapping_tenant_meetings=0,
            overlapping_avatar_meetings=0,
            tenant_id=requested.tenant_id,
            avatar_id=requested.avatar_id,
            meeting_id=requested.meeting_id,
            mode=requested.mode.value,
        )
    blockers: list[str] = []

    meeting_conflicts = [
        row for row in rows
        if row.meeting_id == requested.meeting_id
        and not _same_reservation(row, requested)
    ]
    if meeting_conflicts:
        blockers.append("canonical_meeting_id_conflict")

    for row in rows:
        if (
            row.avatar_id == requested.avatar_id
            and row.tenant_id != requested.tenant_id
        ):
            blockers.append("avatar_cross_tenant_reservation_conflict")

    active = tuple(
        row for row in rows
        if row.state in _ACTIVE_STATES
    )
    tenant_overlaps = tuple(
        row for row in active
        if row.tenant_id == requested.tenant_id
        and _overlaps(row, requested)
    )
    avatar_overlaps = tuple(
        row for row in tenant_overlaps
        if row.avatar_id == requested.avatar_id
    )

    if avatar_overlaps:
        blockers.append("avatar_already_booked")
    if len(tenant_overlaps) >= policy.max_concurrent_meetings:
        blockers.append("tenant_concurrency_capacity_exhausted")

    ordered = tuple(sorted(set(blockers)))
    return FleetReservationDecision(
        allowed=not ordered,
        duplicate=False,
        blockers=ordered,
        overlapping_tenant_meetings=len(tenant_overlaps),
        overlapping_avatar_meetings=len(avatar_overlaps),
        tenant_id=requested.tenant_id,
        avatar_id=requested.avatar_id,
        meeting_id=requested.meeting_id,
        mode=requested.mode.value,
    )
