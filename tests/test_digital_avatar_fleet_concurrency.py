from datetime import datetime, timedelta, timezone

import pytest

from empire_os.digital_avatar import AvatarMeetingMode
from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.digital_avatar_fleet_concurrency import (
    AvatarMeetingReservation,
    FleetConcurrencyPolicy,
    plan_avatar_meeting_reservation,
)


BASE = datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc)


def runtime(avatar_id="avatar-a", tenant_id="tenant-a"):
    return AvatarFleetRuntimeBinding(
        tenant_id=tenant_id,
        avatar_id=avatar_id,
        owner_ref=f"person:{avatar_id}",
        owner_name="Owner",
        capability_labels=("sales",),
        membership_user_id="user-1",
        membership_role="operator",
        owner_consent_evidence_ref="consent:verified:v1",
    )


def reservation(
    meeting_id,
    *,
    avatar_id="avatar-a",
    tenant_id="tenant-a",
    start=BASE,
    minutes=30,
    mode=AvatarMeetingMode.COPILOT,
    state="planned",
):
    return AvatarMeetingReservation(
        tenant_id=tenant_id,
        avatar_id=avatar_id,
        meeting_id=meeting_id,
        starts_at=start,
        ends_at=start + timedelta(minutes=minutes),
        mode=mode,
        state=state,
    )
def policy(max_concurrent=2, **overrides):
    values = {
        "tenant_id": "tenant-a",
        "max_concurrent_meetings": max_concurrent,
        "max_concurrent_meetings_per_avatar": 1,
        "capacity_evidence_ref": "capacity:tenant-a:verified:v1",
    }
    values.update(overrides)
    return FleetConcurrencyPolicy(**values)


def test_same_avatar_non_overlapping_meeting_is_allowed():
    existing = reservation("meeting-1", start=BASE, minutes=30)
    requested = reservation(
        "meeting-2",
        start=BASE + timedelta(minutes=30),
        minutes=30,
    )
    result = plan_avatar_meeting_reservation(
        runtime=runtime(),
        requested=requested,
        existing=(existing,),
        policy=policy(),
    )
    assert result.allowed is True
    assert result.overlapping_avatar_meetings == 0
    assert result.overlapping_tenant_meetings == 0


def test_same_avatar_overlap_is_denied():
    result = plan_avatar_meeting_reservation(
        runtime=runtime(),
        requested=reservation(
            "meeting-2",
            start=BASE + timedelta(minutes=15),
        ),
        existing=(reservation("meeting-1"),),
        policy=policy(),
    )
    assert result.allowed is False
    assert "avatar_already_booked" in result.blockers
    assert result.overlapping_avatar_meetings == 1
def test_different_avatars_can_overlap_until_tenant_capacity():
    existing = reservation("meeting-1", avatar_id="avatar-a")
    requested = reservation("meeting-2", avatar_id="avatar-b")
    allowed = plan_avatar_meeting_reservation(
        runtime=runtime("avatar-b"),
        requested=requested,
        existing=(existing,),
        policy=policy(max_concurrent=2),
    )
    assert allowed.allowed is True
    assert allowed.overlapping_tenant_meetings == 1

    exhausted = plan_avatar_meeting_reservation(
        runtime=runtime("avatar-c"),
        requested=reservation("meeting-3", avatar_id="avatar-c"),
        existing=(
            existing,
            reservation("meeting-2", avatar_id="avatar-b"),
        ),
        policy=policy(max_concurrent=2),
    )
    assert exhausted.allowed is False
    assert "tenant_concurrency_capacity_exhausted" in exhausted.blockers
    assert exhausted.overlapping_tenant_meetings == 2


def test_cross_tenant_reservation_does_not_consume_capacity():
    result = plan_avatar_meeting_reservation(
        runtime=runtime("avatar-b"),
        requested=reservation("meeting-2", avatar_id="avatar-b"),
        existing=(
            reservation(
                "other-meeting",
                tenant_id="tenant-b",
                avatar_id="avatar-other",
            ),
        ),
        policy=policy(max_concurrent=1),
    )
    assert result.allowed is True
    assert result.overlapping_tenant_meetings == 0
def test_same_avatar_id_seen_in_another_tenant_fails_closed():
    result = plan_avatar_meeting_reservation(
        runtime=runtime(),
        requested=reservation("meeting-2"),
        existing=(
            reservation(
                "other-meeting",
                tenant_id="tenant-b",
                avatar_id="avatar-a",
            ),
        ),
        policy=policy(),
    )
    assert result.allowed is False
    assert "avatar_cross_tenant_reservation_conflict" in result.blockers


def test_meeting_id_collision_is_denied_even_across_tenants():
    result = plan_avatar_meeting_reservation(
        runtime=runtime(),
        requested=reservation("meeting-shared"),
        existing=(
            reservation(
                "meeting-shared",
                tenant_id="tenant-b",
                avatar_id="avatar-other",
                state="completed",
            ),
        ),
        policy=policy(),
    )
    assert result.allowed is False
    assert "canonical_meeting_id_conflict" in result.blockers


def test_identical_reservation_is_idempotent_duplicate():
    requested = reservation("meeting-1")
    result = plan_avatar_meeting_reservation(
        runtime=runtime(),
        requested=requested,
        existing=(requested,),
        policy=policy(),
    )
    assert result.allowed is True
    assert result.duplicate is True
    assert result.provider_call_performed is False
    assert result.reservation_persisted is False
def test_terminal_reservations_do_not_consume_capacity():
    result = plan_avatar_meeting_reservation(
        runtime=runtime("avatar-b"),
        requested=reservation("meeting-new", avatar_id="avatar-b"),
        existing=(
            reservation(
                "meeting-old",
                avatar_id="avatar-a",
                state="completed",
            ),
        ),
        policy=policy(max_concurrent=1),
    )
    assert result.allowed is True
    assert result.overlapping_tenant_meetings == 0


@pytest.mark.parametrize(
    "mode",
    [
        AvatarMeetingMode.REPRESENT,
        AvatarMeetingMode.NEGOTIATE,
        AvatarMeetingMode.CLOSE,
    ],
)
def test_v1_rejects_modes_above_copilot(mode):
    with pytest.raises(ValueError, match="authority ceiling"):
        plan_avatar_meeting_reservation(
            runtime=runtime(),
            requested=reservation("meeting-1", mode=mode),
            existing=(),
            policy=policy(),
        )


def test_capacity_requires_verified_evidence_reference():
    with pytest.raises(ValueError, match="capacity evidence ref required"):
        plan_avatar_meeting_reservation(
            runtime=runtime(),
            requested=reservation("meeting-1"),
            existing=(),
            policy=policy(capacity_evidence_ref=""),
        )
def test_runtime_and_policy_tenant_must_match_request():
    with pytest.raises(
        PermissionError,
        match="reservation_runtime_tenant_mismatch",
    ):
        plan_avatar_meeting_reservation(
            runtime=runtime(tenant_id="tenant-b"),
            requested=reservation("meeting-1"),
            existing=(),
            policy=policy(),
        )

    with pytest.raises(
        PermissionError,
        match="concurrency_policy_tenant_mismatch",
    ):
        plan_avatar_meeting_reservation(
            runtime=runtime(),
            requested=reservation("meeting-1"),
            existing=(),
            policy=policy(tenant_id="tenant-b"),
        )


def test_decision_is_recommendation_only_with_zero_execution_authority():
    result = plan_avatar_meeting_reservation(
        runtime=runtime(),
        requested=reservation("meeting-1"),
        existing=(),
        policy=policy(),
    )
    assert result.allowed is True
    assert result.recommendation_only is True
    assert result.reservation_persisted is False
    assert result.provider_call_performed is False
    assert result.meeting_join_performed is False
    assert result.speech_execution_allowed is False
    assert result.commercial_execution_allowed is False
    assert result.execution_authority == "none"
