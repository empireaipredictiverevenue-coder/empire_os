"""Identity-validation adapter over canonical Clone Fleet assignment."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.digital_avatar_fleet import (
    AvatarFleetBinding,
    AvatarFleetRuntimeBinding,
    normalize_avatar_fleet_bindings,
    prepare_avatar_fleet_runtime,
)
from empire_os.digital_avatar_fleet_assignment import (
    AvatarFleetAssignmentRequest,
    assign_avatar_for_meeting,
)
from empire_os.digital_avatar_fleet_concurrency import (
    AvatarMeetingReservation,
    FleetConcurrencyPolicy,
)
from empire_os.digital_avatar_fleet_routing import (
    AvatarFleetMeetingNeed,
    route_avatar_for_meeting,
)
from empire_os.saas_scale import TenantMembership


@dataclass(frozen=True)
class AvatarFleetDispatchRequest:
    need: AvatarFleetMeetingNeed
    starts_at: datetime
    ends_at: datetime

    def validate(self) -> None:
        AvatarFleetAssignmentRequest(
            need=self.need,
            starts_at=self.starts_at,
            ends_at=self.ends_at,
        ).validate()


@dataclass(frozen=True)
class AvatarFleetDispatchDecision:
    tenant_id: str
    meeting_id: str
    requested_mode: str
    selected_avatar_id: str | None
    eligible_avatar_ids: tuple[str, ...]
    available_avatar_ids: tuple[str, ...]
    assignment_blockers: tuple[str, ...]
    routing_blockers: tuple[str, ...]
    identity_blockers: tuple[str, ...]
    candidate_identity_blockers: Mapping[str, tuple[str, ...]]
    concurrency_blockers: tuple[str, ...]
    human_selection_required: bool
    duplicate: bool
    dispatch_ready: bool
    recommendation_only: bool = True
    reservation_persisted: bool = False
    provider_call_performed: bool = False
    calendar_invite_sent: bool = False
    meeting_join_performed: bool = False
    speech_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    payment_execution_allowed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["candidate_identity_blockers"] = {
            key: list(items)
            for key, items in self.candidate_identity_blockers.items()
        }
        return value
def _eligible_runtimes(
    *,
    membership: TenantMembership,
    need: AvatarFleetMeetingNeed,
    bindings: tuple[AvatarFleetBinding, ...],
    identities: Mapping[str, DigitalAvatarIdentity],
) -> tuple[
    tuple[AvatarFleetRuntimeBinding, ...],
    tuple[str, ...],
    dict[str, tuple[str, ...]],
]:
    route = route_avatar_for_meeting(
        membership=membership,
        need=need,
        bindings=bindings,
    )
    normalized = normalize_avatar_fleet_bindings(bindings)
    by_avatar = {
        binding.avatar_id: binding
        for binding in normalized
        if binding.tenant_id == need.tenant_id
    }

    runtimes: list[AvatarFleetRuntimeBinding] = []
    blockers: dict[str, tuple[str, ...]] = {}
    for avatar_id in route.eligible_avatar_ids:
        binding = by_avatar.get(avatar_id)
        if binding is None:
            blockers[avatar_id] = (
                "selected_avatar_binding_unavailable",
            )
            continue
        identity = identities.get(avatar_id)
        if identity is None:
            blockers[avatar_id] = (
                "selected_avatar_identity_unavailable",
            )
            continue
        try:
            runtime = prepare_avatar_fleet_runtime(
                membership=membership,
                binding=binding,
                identity=identity,
            )
        except (PermissionError, ValueError):
            blockers[avatar_id] = (
                "selected_avatar_identity_invalid",
            )
            continue
        runtimes.append(runtime)

    return (
        tuple(runtimes),
        route.eligible_avatar_ids,
        blockers,
    )


def _concurrency_blockers(
    candidate_blockers: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    excluded = {
        "runtime_binding_missing",
        "runtime_binding_tenant_mismatch",
    }
    return tuple(sorted({
        blocker
        for blockers in candidate_blockers.values()
        for blocker in blockers
        if blocker not in excluded
    }))
def plan_avatar_fleet_dispatch(
    *,
    membership: TenantMembership,
    request: AvatarFleetDispatchRequest,
    bindings: Iterable[AvatarFleetBinding],
    identities: Mapping[str, DigitalAvatarIdentity],
    existing_reservations: Iterable[AvatarMeetingReservation],
    concurrency_policy: FleetConcurrencyPolicy,
) -> AvatarFleetDispatchDecision:
    request.validate()
    rows = tuple(bindings)
    runtimes, routed_ids, identity_by_avatar = _eligible_runtimes(
        membership=membership,
        need=request.need,
        bindings=rows,
        identities=identities,
    )

    assignment = assign_avatar_for_meeting(
        membership=membership,
        request=AvatarFleetAssignmentRequest(
            need=request.need,
            starts_at=request.starts_at,
            ends_at=request.ends_at,
        ),
        bindings=rows,
        runtimes=runtimes,
        existing_reservations=tuple(existing_reservations),
        concurrency_policy=concurrency_policy,
    )

    identity_blockers = tuple(sorted({
        blocker
        for blockers in identity_by_avatar.values()
        for blocker in blockers
    }))
    routing_blockers: tuple[str, ...] = ()
    if not assignment.capable_avatar_ids:
        routing_blockers = assignment.blockers
    elif assignment.human_selection_required:
        routing_blockers = ("human_selection_required",)

    return AvatarFleetDispatchDecision(
        tenant_id=request.need.tenant_id,
        meeting_id=request.need.meeting_id,
        requested_mode=request.need.requested_mode.value,
        selected_avatar_id=assignment.selected_avatar_id,
        eligible_avatar_ids=(
            assignment.capable_avatar_ids or routed_ids
        ),
        available_avatar_ids=assignment.available_avatar_ids,
        assignment_blockers=assignment.blockers,
        routing_blockers=routing_blockers,
        identity_blockers=identity_blockers,
        candidate_identity_blockers=identity_by_avatar,
        concurrency_blockers=_concurrency_blockers(
            assignment.candidate_blockers
        ),
        human_selection_required=(
            assignment.human_selection_required
        ),
        duplicate=assignment.duplicate,
        dispatch_ready=assignment.assignment_ready,
    )
