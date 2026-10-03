"""Capability + availability assignment for Digital Avatar clone fleets."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

from empire_os.digital_avatar_fleet import (
    AvatarFleetBinding,
    AvatarFleetRuntimeBinding,
)
from empire_os.digital_avatar_fleet_concurrency import (
    AvatarMeetingReservation,
    FleetConcurrencyPolicy,
    plan_avatar_meeting_reservation,
)
from empire_os.digital_avatar_fleet_routing import (
    AvatarFleetMeetingNeed,
    route_avatar_for_meeting,
)
from empire_os.saas_scale import TenantMembership


@dataclass(frozen=True)
class AvatarFleetAssignmentRequest:
    need: AvatarFleetMeetingNeed
    starts_at: datetime
    ends_at: datetime

    def validate(self) -> None:
        self.need.validate()
        probe = AvatarMeetingReservation(
            tenant_id=self.need.tenant_id,
            avatar_id="validation-probe",
            meeting_id=self.need.meeting_id,
            starts_at=self.starts_at,
            ends_at=self.ends_at,
            mode=self.need.requested_mode,
        )
        probe.validate()


@dataclass(frozen=True)
class AvatarFleetAssignmentDecision:
    tenant_id: str
    meeting_id: str
    selected_avatar_id: str | None
    capable_avatar_ids: tuple[str, ...]
    available_avatar_ids: tuple[str, ...]
    candidate_blockers: Mapping[str, tuple[str, ...]]
    blockers: tuple[str, ...]
    human_selection_required: bool
    duplicate: bool
    recommendation_only: bool = True
    reservation_persisted: bool = False
    provider_call_performed: bool = False
    meeting_join_performed: bool = False
    speech_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    payment_execution_allowed: bool = False
    execution_authority: str = "none"

    @property
    def assignment_ready(self) -> bool:
        return self.selected_avatar_id is not None and not self.blockers

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["candidate_blockers"] = {
            key: list(items)
            for key, items in self.candidate_blockers.items()
        }
        value["assignment_ready"] = self.assignment_ready
        return value
def _runtime_map(
    runtimes: Iterable[AvatarFleetRuntimeBinding],
) -> dict[str, AvatarFleetRuntimeBinding]:
    result: dict[str, AvatarFleetRuntimeBinding] = {}
    for runtime in runtimes:
        if not runtime.tenant_id.strip() or not runtime.avatar_id.strip():
            raise ValueError("fleet runtime tenant/avatar required")
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
        current = result.get(runtime.avatar_id)
        if current is not None and current != runtime:
            raise ValueError("fleet_runtime_binding_conflict")
        result[runtime.avatar_id] = runtime
    return result


def assign_avatar_for_meeting(
    *,
    membership: TenantMembership,
    request: AvatarFleetAssignmentRequest,
    bindings: Iterable[AvatarFleetBinding],
    runtimes: Iterable[AvatarFleetRuntimeBinding],
    existing_reservations: Iterable[AvatarMeetingReservation],
    concurrency_policy: FleetConcurrencyPolicy,
) -> AvatarFleetAssignmentDecision:
    request.validate()
    binding_rows = tuple(bindings)
    reservation_rows = tuple(existing_reservations)
    runtime_by_avatar = _runtime_map(runtimes)

    routing = route_avatar_for_meeting(
        membership=membership,
        need=request.need,
        bindings=binding_rows,
    )
    capable = routing.eligible_avatar_ids
    if not capable:
        return AvatarFleetAssignmentDecision(
            tenant_id=request.need.tenant_id,
            meeting_id=request.need.meeting_id,
            selected_avatar_id=None,
            capable_avatar_ids=(),
            available_avatar_ids=(),
            candidate_blockers={},
            blockers=routing.blockers or ("no_eligible_avatar",),
            human_selection_required=False,
            duplicate=False,
        )
    candidate_blockers: dict[str, tuple[str, ...]] = {}
    available: list[str] = []
    duplicate_by_avatar: dict[str, bool] = {}

    for avatar_id in capable:
        runtime = runtime_by_avatar.get(avatar_id)
        if runtime is None:
            candidate_blockers[avatar_id] = ("runtime_binding_missing",)
            continue
        if runtime.tenant_id != request.need.tenant_id:
            candidate_blockers[avatar_id] = ("runtime_binding_tenant_mismatch",)
            continue

        requested = AvatarMeetingReservation(
            tenant_id=request.need.tenant_id,
            avatar_id=avatar_id,
            meeting_id=request.need.meeting_id,
            starts_at=request.starts_at,
            ends_at=request.ends_at,
            mode=request.need.requested_mode,
        )
        decision = plan_avatar_meeting_reservation(
            runtime=runtime,
            requested=requested,
            existing=reservation_rows,
            policy=concurrency_policy,
        )
        if decision.allowed:
            available.append(avatar_id)
            duplicate_by_avatar[avatar_id] = decision.duplicate
        else:
            candidate_blockers[avatar_id] = decision.blockers

    available_ids = tuple(sorted(available))
    preferred = str(request.need.preferred_avatar_id or "").strip()

    if preferred:
        if routing.selected_avatar_id != preferred:
            return AvatarFleetAssignmentDecision(
                tenant_id=request.need.tenant_id,
                meeting_id=request.need.meeting_id,
                selected_avatar_id=None,
                capable_avatar_ids=capable,
                available_avatar_ids=available_ids,
                candidate_blockers=candidate_blockers,
                blockers=("preferred_avatar_unavailable",),
                human_selection_required=False,
                duplicate=False,
            )
        if preferred not in available_ids:
            return AvatarFleetAssignmentDecision(
                tenant_id=request.need.tenant_id,
                meeting_id=request.need.meeting_id,
                selected_avatar_id=None,
                capable_avatar_ids=capable,
                available_avatar_ids=available_ids,
                candidate_blockers=candidate_blockers,
                blockers=("preferred_avatar_unavailable",),
                human_selection_required=False,
                duplicate=False,
            )
        return AvatarFleetAssignmentDecision(
            tenant_id=request.need.tenant_id,
            meeting_id=request.need.meeting_id,
            selected_avatar_id=preferred,
            capable_avatar_ids=capable,
            available_avatar_ids=available_ids,
            candidate_blockers=candidate_blockers,
            blockers=(),
            human_selection_required=False,
            duplicate=duplicate_by_avatar.get(preferred, False),
        )
    if not available_ids:
        common_conflict = any(
            "canonical_meeting_id_conflict" in blockers
            for blockers in candidate_blockers.values()
        )
        blockers = (
            ("canonical_meeting_id_conflict",)
            if common_conflict
            else ("no_available_eligible_avatar",)
        )
        return AvatarFleetAssignmentDecision(
            tenant_id=request.need.tenant_id,
            meeting_id=request.need.meeting_id,
            selected_avatar_id=None,
            capable_avatar_ids=capable,
            available_avatar_ids=(),
            candidate_blockers=candidate_blockers,
            blockers=blockers,
            human_selection_required=False,
            duplicate=False,
        )

    if len(available_ids) > 1:
        return AvatarFleetAssignmentDecision(
            tenant_id=request.need.tenant_id,
            meeting_id=request.need.meeting_id,
            selected_avatar_id=None,
            capable_avatar_ids=capable,
            available_avatar_ids=available_ids,
            candidate_blockers=candidate_blockers,
            blockers=("human_selection_required",),
            human_selection_required=True,
            duplicate=False,
        )

    selected = available_ids[0]
    return AvatarFleetAssignmentDecision(
        tenant_id=request.need.tenant_id,
        meeting_id=request.need.meeting_id,
        selected_avatar_id=selected,
        capable_avatar_ids=capable,
        available_avatar_ids=available_ids,
        candidate_blockers=candidate_blockers,
        blockers=(),
        human_selection_required=False,
        duplicate=duplicate_by_avatar.get(selected, False),
    )
