from datetime import datetime, timedelta, timezone

import pytest

from empire_os.digital_avatar import AvatarMeetingMode, DigitalAvatarIdentity
from empire_os.digital_avatar_fleet import AvatarFleetBinding
from empire_os.digital_avatar_fleet_concurrency import (
    AvatarMeetingReservation,
    FleetConcurrencyPolicy,
)
from empire_os.digital_avatar_fleet_dispatch import (
    AvatarFleetDispatchRequest,
    plan_avatar_fleet_dispatch,
)
from empire_os.digital_avatar_fleet_routing import AvatarFleetMeetingNeed
from empire_os.saas_scale import TenantMembership


BASE = datetime(2026, 10, 3, 10, 0, tzinfo=timezone.utc)


def membership():
    return TenantMembership(
        tenant_id="tenant-a",
        user_id="user-1",
        role="operator",
        status="active",
    )
def binding(
    avatar_id,
    capabilities=("sales",),
    *,
    tenant_id="tenant-a",
    owner_name="Owner",
    consent_ref=None,
):
    return AvatarFleetBinding(
        tenant_id=tenant_id,
        avatar_id=avatar_id,
        owner_ref=f"person:{avatar_id}",
        owner_name=owner_name,
        owner_consent_evidence_ref=(
            consent_ref or f"consent:{avatar_id}:v1"
        ),
        capability_labels=tuple(capabilities),
        status="active",
    )


def identity(
    avatar_id,
    *,
    owner_name="Owner",
    consent_ref=None,
):
    return DigitalAvatarIdentity(
        avatar_id=avatar_id,
        owner_name=owner_name,
        display_name=f"{owner_name} — AI Digital Avatar",
        organisation_name="Empire AI",
        disclosure_text="I am an authorised Empire AI Digital Avatar.",
        owner_consent_evidence_ref=(
            consent_ref or f"consent:{avatar_id}:v1"
        ),
    )
def need(*capabilities, preferred=None):
    return AvatarFleetMeetingNeed(
        tenant_id="tenant-a",
        meeting_id="meeting-001",
        required_capability_labels=tuple(capabilities),
        objective_evidence_ref="objective:meeting-001",
        requested_mode=AvatarMeetingMode.COPILOT,
        preferred_avatar_id=preferred,
    )


def request(*capabilities, preferred=None):
    return AvatarFleetDispatchRequest(
        need=need(*capabilities, preferred=preferred),
        starts_at=BASE,
        ends_at=BASE + timedelta(minutes=30),
    )


def policy(max_concurrent=2):
    return FleetConcurrencyPolicy(
        tenant_id="tenant-a",
        max_concurrent_meetings=max_concurrent,
        max_concurrent_meetings_per_avatar=1,
        capacity_evidence_ref="capacity:tenant-a:v1",
    )
def test_unique_clone_with_valid_identity_and_free_slot_is_dispatch_ready():
    result = plan_avatar_fleet_dispatch(
        membership=membership(),
        request=request("sales", "product"),
        bindings=(
            binding("avatar-sales", ("sales",)),
            binding("avatar-founder", ("sales", "product")),
        ),
        identities={
            "avatar-founder": identity("avatar-founder"),
        },
        existing_reservations=(),
        concurrency_policy=policy(),
    )
    assert result.dispatch_ready is True
    assert result.selected_avatar_id == "avatar-founder"
    assert result.routing_blockers == ()
    assert result.identity_blockers == ()
    assert result.concurrency_blockers == ()


def test_multiple_capable_and_free_clones_require_human_selection():
    result = plan_avatar_fleet_dispatch(
        membership=membership(),
        request=request("sales"),
        bindings=(
            binding("avatar-a", ("sales",)),
            binding("avatar-b", ("sales",)),
        ),
        identities={
            "avatar-a": identity("avatar-a"),
            "avatar-b": identity("avatar-b"),
        },
        existing_reservations=(),
        concurrency_policy=policy(),
    )
    assert result.dispatch_ready is False
    assert result.human_selection_required is True
    assert result.assignment_blockers == ("human_selection_required",)
    assert result.routing_blockers == ("human_selection_required",)
    assert result.available_avatar_ids == ("avatar-a", "avatar-b")


def test_capability_ambiguity_is_narrowed_by_availability():
    result = plan_avatar_fleet_dispatch(
        membership=membership(),
        request=request("sales"),
        bindings=(
            binding("avatar-a", ("sales",)),
            binding("avatar-b", ("sales",)),
        ),
        identities={
            "avatar-a": identity("avatar-a"),
            "avatar-b": identity("avatar-b"),
        },
        existing_reservations=(
            AvatarMeetingReservation(
                tenant_id="tenant-a",
                avatar_id="avatar-a",
                meeting_id="meeting-existing",
                starts_at=BASE,
                ends_at=BASE + timedelta(minutes=30),
                mode=AvatarMeetingMode.COPILOT,
            ),
        ),
        concurrency_policy=policy(),
    )
    assert result.dispatch_ready is True
    assert result.selected_avatar_id == "avatar-b"
    assert result.available_avatar_ids == ("avatar-b",)
    assert result.human_selection_required is False
    assert result.routing_blockers == ()
    assert "avatar_already_booked" in result.concurrency_blockers
def test_missing_selected_identity_blocks_dispatch():
    result = plan_avatar_fleet_dispatch(
        membership=membership(),
        request=request("sales"),
        bindings=(binding("avatar-a"),),
        identities={},
        existing_reservations=(),
        concurrency_policy=policy(),
    )
    assert result.dispatch_ready is False
    assert result.identity_blockers == (
        "selected_avatar_identity_unavailable",
    )


def test_owner_or_consent_mismatch_blocks_dispatch():
    result = plan_avatar_fleet_dispatch(
        membership=membership(),
        request=request("sales"),
        bindings=(
            binding(
                "avatar-a",
                owner_name="Owner A",
                consent_ref="consent:a:v1",
            ),
        ),
        identities={
            "avatar-a": identity(
                "avatar-a",
                owner_name="Owner B",
                consent_ref="consent:b:v1",
            )
        },
        existing_reservations=(),
        concurrency_policy=policy(),
    )
    assert result.dispatch_ready is False
    assert result.identity_blockers == (
        "selected_avatar_identity_invalid",
    )
def test_same_avatar_overlap_blocks_dispatch():
    result = plan_avatar_fleet_dispatch(
        membership=membership(),
        request=request("sales"),
        bindings=(binding("avatar-a"),),
        identities={"avatar-a": identity("avatar-a")},
        existing_reservations=(
            AvatarMeetingReservation(
                tenant_id="tenant-a",
                avatar_id="avatar-a",
                meeting_id="meeting-existing",
                starts_at=BASE - timedelta(minutes=5),
                ends_at=BASE + timedelta(minutes=10),
                mode=AvatarMeetingMode.COPILOT,
            ),
        ),
        concurrency_policy=policy(),
    )
    assert result.dispatch_ready is False
    assert "avatar_already_booked" in result.concurrency_blockers


def test_tenant_capacity_exhaustion_blocks_dispatch():
    result = plan_avatar_fleet_dispatch(
        membership=membership(),
        request=request("sales", preferred="avatar-b"),
        bindings=(
            binding("avatar-a"),
            binding("avatar-b"),
        ),
        identities={"avatar-b": identity("avatar-b")},
        existing_reservations=(
            AvatarMeetingReservation(
                tenant_id="tenant-a",
                avatar_id="avatar-a",
                meeting_id="meeting-existing",
                starts_at=BASE,
                ends_at=BASE + timedelta(minutes=30),
                mode=AvatarMeetingMode.COPILOT,
            ),
        ),
        concurrency_policy=policy(max_concurrent=1),
    )
    assert result.dispatch_ready is False
    assert "tenant_concurrency_capacity_exhausted" in (
        result.concurrency_blockers
    )
def test_preferred_eligible_clone_flows_through_dispatch():
    result = plan_avatar_fleet_dispatch(
        membership=membership(),
        request=request("sales", preferred="avatar-b"),
        bindings=(
            binding("avatar-a", ("sales",)),
            binding("avatar-b", ("sales", "product")),
        ),
        identities={"avatar-b": identity("avatar-b")},
        existing_reservations=(),
        concurrency_policy=policy(),
    )
    assert result.dispatch_ready is True
    assert result.selected_avatar_id == "avatar-b"


def test_invalid_time_fails_before_routing():
    bad = AvatarFleetDispatchRequest(
        need=need("sales"),
        starts_at=datetime(2026, 10, 3, 10, 0),
        ends_at=datetime(2026, 10, 3, 10, 30),
    )
    with pytest.raises(ValueError, match="include timezone"):
        plan_avatar_fleet_dispatch(
            membership=membership(),
            request=bad,
            bindings=(),
            identities={},
            existing_reservations=(),
            concurrency_policy=policy(),
        )


def test_dispatch_never_grants_external_authority():
    result = plan_avatar_fleet_dispatch(
        membership=membership(),
        request=request("sales"),
        bindings=(binding("avatar-a"),),
        identities={"avatar-a": identity("avatar-a")},
        existing_reservations=(),
        concurrency_policy=policy(),
    )
    assert result.dispatch_ready is True
    assert result.recommendation_only is True
    assert result.reservation_persisted is False
    assert result.provider_call_performed is False
    assert result.calendar_invite_sent is False
    assert result.meeting_join_performed is False
    assert result.speech_execution_allowed is False
    assert result.commercial_execution_allowed is False
    assert result.execution_authority == "none"
