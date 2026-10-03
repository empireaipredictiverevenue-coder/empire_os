from datetime import datetime, timedelta, timezone

import pytest

from empire_os.digital_avatar import AvatarMeetingMode
from empire_os.digital_avatar_fleet import (
    AvatarFleetBinding,
    AvatarFleetRuntimeBinding,
)
from empire_os.digital_avatar_fleet_assignment import (
    AvatarFleetAssignmentRequest,
    assign_avatar_for_meeting,
)
from empire_os.digital_avatar_fleet_concurrency import (
    AvatarMeetingReservation,
    FleetConcurrencyPolicy,
)
from empire_os.digital_avatar_fleet_routing import AvatarFleetMeetingNeed
from empire_os.saas_scale import TenantMembership


BASE = datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc)


def membership():
    return TenantMembership(
        tenant_id="tenant-a",
        user_id="user-1",
        role="operator",
        status="active",
    )


def binding(avatar_id, capabilities=("sales",), *, tenant_id="tenant-a"):
    return AvatarFleetBinding(
        tenant_id=tenant_id,
        avatar_id=avatar_id,
        owner_ref=f"person:{avatar_id}",
        owner_name=f"Owner {avatar_id}",
        owner_consent_evidence_ref=f"consent:{avatar_id}:v1",
        capability_labels=tuple(capabilities),
        status="active",
    )


def runtime(avatar_id, *, tenant_id="tenant-a"):
    return AvatarFleetRuntimeBinding(
        tenant_id=tenant_id,
        avatar_id=avatar_id,
        owner_ref=f"person:{avatar_id}",
        owner_name=f"Owner {avatar_id}",
        capability_labels=("sales", "product"),
        membership_user_id="user-1",
        membership_role="operator",
        owner_consent_evidence_ref=f"consent:{avatar_id}:v1",
    )
def need(*caps, preferred=None):
    return AvatarFleetMeetingNeed(
        tenant_id="tenant-a",
        meeting_id="meeting-new",
        required_capability_labels=tuple(caps),
        objective_evidence_ref="objective:meeting-new:v1",
        requested_mode=AvatarMeetingMode.COPILOT,
        preferred_avatar_id=preferred,
    )


def request(*caps, preferred=None):
    return AvatarFleetAssignmentRequest(
        need=need(*caps, preferred=preferred),
        starts_at=BASE,
        ends_at=BASE + timedelta(minutes=30),
    )


def policy(max_concurrent=3):
    return FleetConcurrencyPolicy(
        tenant_id="tenant-a",
        max_concurrent_meetings=max_concurrent,
        max_concurrent_meetings_per_avatar=1,
        capacity_evidence_ref="capacity:tenant-a:verified:v1",
    )


def existing(
    meeting_id,
    avatar_id,
    *,
    start=BASE,
    minutes=30,
    tenant_id="tenant-a",
    state="planned",
):
    return AvatarMeetingReservation(
        tenant_id=tenant_id,
        avatar_id=avatar_id,
        meeting_id=meeting_id,
        starts_at=start,
        ends_at=start + timedelta(minutes=minutes),
        mode=AvatarMeetingMode.COPILOT,
        state=state,
    )
def test_unique_capable_and_available_clone_is_selected():
    result = assign_avatar_for_meeting(
        membership=membership(),
        request=request("sales", "product"),
        bindings=(
            binding("avatar-sales", ("sales",)),
            binding("avatar-founder", ("sales", "product")),
        ),
        runtimes=(
            runtime("avatar-sales"),
            runtime("avatar-founder"),
        ),
        existing_reservations=(),
        concurrency_policy=policy(),
    )
    assert result.assignment_ready is True
    assert result.selected_avatar_id == "avatar-founder"
    assert result.capable_avatar_ids == ("avatar-founder",)
    assert result.available_avatar_ids == ("avatar-founder",)


def test_busy_capable_clone_is_filtered_and_available_clone_selected():
    result = assign_avatar_for_meeting(
        membership=membership(),
        request=request("sales"),
        bindings=(
            binding("avatar-a", ("sales",)),
            binding("avatar-b", ("sales",)),
        ),
        runtimes=(runtime("avatar-a"), runtime("avatar-b")),
        existing_reservations=(
            existing("meeting-busy", "avatar-a"),
        ),
        concurrency_policy=policy(),
    )
    assert result.assignment_ready is True
    assert result.selected_avatar_id == "avatar-b"
    assert result.capable_avatar_ids == ("avatar-a", "avatar-b")
    assert result.available_avatar_ids == ("avatar-b",)
    assert result.candidate_blockers["avatar-a"] == (
        "avatar_already_booked",
    )
def test_multiple_capable_and_available_clones_require_human_selection():
    result = assign_avatar_for_meeting(
        membership=membership(),
        request=request("sales"),
        bindings=(
            binding("avatar-a", ("sales",)),
            binding("avatar-b", ("sales",)),
        ),
        runtimes=(runtime("avatar-a"), runtime("avatar-b")),
        existing_reservations=(),
        concurrency_policy=policy(),
    )
    assert result.assignment_ready is False
    assert result.selected_avatar_id is None
    assert result.available_avatar_ids == ("avatar-a", "avatar-b")
    assert result.human_selection_required is True
    assert result.blockers == ("human_selection_required",)


def test_preferred_busy_clone_does_not_silently_substitute():
    result = assign_avatar_for_meeting(
        membership=membership(),
        request=request("sales", preferred="avatar-a"),
        bindings=(
            binding("avatar-a", ("sales",)),
            binding("avatar-b", ("sales",)),
        ),
        runtimes=(runtime("avatar-a"), runtime("avatar-b")),
        existing_reservations=(
            existing("meeting-busy", "avatar-a"),
        ),
        concurrency_policy=policy(),
    )
    assert result.assignment_ready is False
    assert result.selected_avatar_id is None
    assert result.blockers == ("preferred_avatar_unavailable",)
    assert "avatar-b" in result.available_avatar_ids
def test_candidate_without_validated_runtime_binding_is_unavailable():
    result = assign_avatar_for_meeting(
        membership=membership(),
        request=request("sales"),
        bindings=(binding("avatar-a", ("sales",)),),
        runtimes=(),
        existing_reservations=(),
        concurrency_policy=policy(),
    )
    assert result.assignment_ready is False
    assert result.blockers == ("no_available_eligible_avatar",)
    assert result.candidate_blockers == {
        "avatar-a": ("runtime_binding_missing",)
    }


def test_tenant_capacity_exhaustion_blocks_all_available_candidates():
    result = assign_avatar_for_meeting(
        membership=membership(),
        request=request("sales"),
        bindings=(
            binding("avatar-b", ("sales",)),
            binding("avatar-c", ("sales",)),
        ),
        runtimes=(runtime("avatar-b"), runtime("avatar-c")),
        existing_reservations=(
            existing("meeting-running", "avatar-a"),
        ),
        concurrency_policy=policy(max_concurrent=1),
    )
    assert result.assignment_ready is False
    assert result.available_avatar_ids == ()
    assert result.blockers == ("no_available_eligible_avatar",)
    assert all(
        "tenant_concurrency_capacity_exhausted" in blockers
        for blockers in result.candidate_blockers.values()
    )
def test_canonical_meeting_conflict_blocks_assignment():
    result = assign_avatar_for_meeting(
        membership=membership(),
        request=request("sales"),
        bindings=(binding("avatar-a", ("sales",)),),
        runtimes=(runtime("avatar-a"),),
        existing_reservations=(
            existing(
                "meeting-new",
                "avatar-other",
                start=BASE + timedelta(hours=2),
                state="completed",
            ),
        ),
        concurrency_policy=policy(),
    )
    assert result.assignment_ready is False
    assert result.blockers == ("canonical_meeting_id_conflict",)


def test_identical_existing_reservation_is_idempotent_assignment():
    requested = request("sales")
    same = AvatarMeetingReservation(
        tenant_id="tenant-a",
        avatar_id="avatar-a",
        meeting_id="meeting-new",
        starts_at=requested.starts_at,
        ends_at=requested.ends_at,
        mode=AvatarMeetingMode.COPILOT,
    )
    result = assign_avatar_for_meeting(
        membership=membership(),
        request=requested,
        bindings=(binding("avatar-a", ("sales",)),),
        runtimes=(runtime("avatar-a"),),
        existing_reservations=(same,),
        concurrency_policy=policy(),
    )
    assert result.assignment_ready is True
    assert result.selected_avatar_id == "avatar-a"
    assert result.duplicate is True
    assert result.reservation_persisted is False
def test_cross_tenant_binding_is_not_a_capable_candidate():
    result = assign_avatar_for_meeting(
        membership=membership(),
        request=request("sales"),
        bindings=(
            binding("avatar-local", ("sales",)),
            binding(
                "avatar-secret",
                ("sales",),
                tenant_id="tenant-b",
            ),
        ),
        runtimes=(runtime("avatar-local"),),
        existing_reservations=(),
        concurrency_policy=policy(),
    )
    assert result.capable_avatar_ids == ("avatar-local",)
    assert "avatar-secret" not in repr(result.as_dict())


def test_assignment_never_grants_execution_authority():
    result = assign_avatar_for_meeting(
        membership=membership(),
        request=request("sales"),
        bindings=(binding("avatar-a", ("sales",)),),
        runtimes=(runtime("avatar-a"),),
        existing_reservations=(),
        concurrency_policy=policy(),
    )
    assert result.recommendation_only is True
    assert result.reservation_persisted is False
    assert result.provider_call_performed is False
    assert result.meeting_join_performed is False
    assert result.speech_execution_allowed is False
    assert result.commercial_execution_allowed is False
    assert result.payment_execution_allowed is False
    assert result.execution_authority == "none"
def test_runtime_binding_tenant_mismatch_fails_candidate_not_cross_tenant_leak():
    result = assign_avatar_for_meeting(
        membership=membership(),
        request=request("sales"),
        bindings=(binding("avatar-a", ("sales",)),),
        runtimes=(runtime("avatar-a", tenant_id="tenant-b"),),
        existing_reservations=(),
        concurrency_policy=policy(),
    )
    assert result.assignment_ready is False
    assert result.candidate_blockers["avatar-a"] == (
        "runtime_binding_tenant_mismatch",
    )


def test_invalid_request_time_fails_before_routing():
    bad = AvatarFleetAssignmentRequest(
        need=need("sales"),
        starts_at=BASE,
        ends_at=BASE,
    )
    with pytest.raises(ValueError, match="ends_at must be after"):
        assign_avatar_for_meeting(
            membership=membership(),
            request=bad,
            bindings=(binding("avatar-a", ("sales",)),),
            runtimes=(runtime("avatar-a"),),
            existing_reservations=(),
            concurrency_policy=policy(),
        )
