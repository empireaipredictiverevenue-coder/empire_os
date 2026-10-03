from datetime import datetime, timedelta, timezone

import pytest

from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.digital_avatar_fleet_memory import (
    AvatarFleetContinuitySource,
    build_avatar_fleet_continuity_memory,
)
from empire_os.digital_avatar_meeting_outcome import AvatarMeetingOutcomePacket
from empire_os.saas_scale import TenantMembership


BASE = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def membership(role="operator", **overrides):
    values = {
        "tenant_id": "tenant-a",
        "user_id": "user-1",
        "role": role,
        "status": "active",
    }
    values.update(overrides)
    return TenantMembership(**values)


def runtime(avatar_id="avatar-a", **overrides):
    values = {
        "tenant_id": "tenant-a",
        "avatar_id": avatar_id,
        "owner_ref": f"person:{avatar_id}",
        "owner_name": "Owner A",
        "capability_labels": ("sales",),
        "membership_user_id": "user-1",
        "membership_role": "operator",
        "owner_consent_evidence_ref": "consent:avatar-a:v1",
    }
    values.update(overrides)
    return AvatarFleetRuntimeBinding(**values)
def outcome(meeting_id, **overrides):
    values = {
        "meeting_id": meeting_id,
        "avatar_id": "avatar-a",
        "account_name": f"Account {meeting_id}",
        "conversation_id": f"conversation:{meeting_id}",
        "opportunity_id": f"opportunity:{meeting_id}",
        "lifecycle_status": "done",
        "terminal": True,
        "fatal": False,
        "buyer_utterance_count": 3,
        "buyer_evidence_refs": (f"buyer:{meeting_id}:1",),
        "verification_refs": (f"verify:{meeting_id}:1",),
        "close_ready_at_end": False,
        "human_takeover_required": False,
        "follow_up_review_recommended": True,
        "conversation_bridge_recommended": True,
        "predictive_revenue_refresh_recommended": True,
    }
    values.update(overrides)
    return AvatarMeetingOutcomePacket(**values)


def source(
    meeting_id,
    *,
    observed_at=BASE,
    tenant_id="tenant-a",
    avatar_id="avatar-a",
    outcome_overrides=None,
):
    overrides = dict(outcome_overrides or {})
    overrides.setdefault("avatar_id", avatar_id)
    return AvatarFleetContinuitySource(
        tenant_id=tenant_id,
        avatar_id=avatar_id,
        observed_at=observed_at,
        source_ref=f"meeting-outcome:{meeting_id}",
        outcome=outcome(meeting_id, **overrides),
    )
def test_own_clone_history_is_newest_first_and_bounded():
    memory = build_avatar_fleet_continuity_memory(
        membership=membership(),
        runtime=runtime(),
        sources=(
            source("older", observed_at=BASE - timedelta(hours=2)),
            source("newest", observed_at=BASE),
            source("middle", observed_at=BASE - timedelta(hours=1)),
        ),
        max_entries=2,
    )
    assert [entry.meeting_id for entry in memory.entries] == [
        "newest",
        "middle",
    ]
    assert memory.source_count == 2
    assert memory.truth_class == "OBSERVED_CONTINUITY"
    assert memory.raw_transcript_included is False
    assert memory.raw_audio_included is False


def test_same_tenant_other_avatar_and_other_tenant_other_avatar_are_excluded():
    memory = build_avatar_fleet_continuity_memory(
        membership=membership(),
        runtime=runtime(),
        sources=(
            source("own"),
            source(
                "same-tenant-other-avatar",
                avatar_id="avatar-b",
            ),
            source(
                "other-tenant-other-avatar",
                tenant_id="tenant-b",
                avatar_id="avatar-z",
            ),
        ),
    )
    assert [entry.meeting_id for entry in memory.entries] == ["own"]
    rendered = repr(memory.as_dict())
    assert "same-tenant-other-avatar" not in rendered
    assert "other-tenant-other-avatar" not in rendered
def test_same_avatar_under_other_tenant_fails_closed():
    with pytest.raises(
        ValueError,
        match="avatar_memory_cross_tenant_conflict",
    ):
        build_avatar_fleet_continuity_memory(
            membership=membership(),
            runtime=runtime(),
            sources=(
                source("own"),
                source("conflict", tenant_id="tenant-b"),
            ),
        )


def test_viewer_or_disabled_membership_cannot_build_runtime_continuity():
    with pytest.raises(
        PermissionError,
        match="membership_operate_permission_denied",
    ):
        build_avatar_fleet_continuity_memory(
            membership=membership(role="viewer"),
            runtime=runtime(),
            sources=(source("m1"),),
        )
    with pytest.raises(
        PermissionError,
        match="membership_operate_permission_denied",
    ):
        build_avatar_fleet_continuity_memory(
            membership=membership(status="disabled"),
            runtime=runtime(),
            sources=(source("m1"),),
        )


def test_membership_must_match_runtime_tenant_and_user():
    with pytest.raises(
        PermissionError,
        match="continuity_membership_runtime_tenant_mismatch",
    ):
        build_avatar_fleet_continuity_memory(
            membership=membership(tenant_id="tenant-b"),
            runtime=runtime(),
            sources=(),
        )
    with pytest.raises(
        PermissionError,
        match="continuity_membership_runtime_user_mismatch",
    ):
        build_avatar_fleet_continuity_memory(
            membership=membership(user_id="user-other"),
            runtime=runtime(),
            sources=(),
        )
def test_observed_meeting_history_is_not_automatically_commercial_proof():
    memory = build_avatar_fleet_continuity_memory(
        membership=membership(),
        runtime=runtime(),
        sources=(source("observed"),),
    )
    assert memory.entries[0].truth_class == "OBSERVED"
    assert memory.entries[0].commercial_proof_eligible is False
    assert memory.commercial_proof_eligible_count == 0


def test_only_explicit_verified_outcome_with_cortex_eligibility_is_proof_eligible():
    memory = build_avatar_fleet_continuity_memory(
        membership=membership(),
        runtime=runtime(),
        sources=(
            source(
                "verified",
                outcome_overrides={
                    "verified_commercial_outcome": True,
                    "cortex_customer_label_eligible": True,
                    "revenue_recognized": True,
                },
            ),
            source(
                "not-cortex",
                observed_at=BASE - timedelta(minutes=1),
                outcome_overrides={
                    "verified_commercial_outcome": True,
                    "cortex_customer_label_eligible": False,
                },
            ),
        ),
    )
    assert memory.entries[0].commercial_proof_eligible is True
    assert memory.entries[1].commercial_proof_eligible is False
    assert memory.commercial_proof_eligible_count == 1
    rendered = repr(memory.as_dict()).lower()
    assert "revenue_recognized" not in rendered
def test_continuity_projects_refs_not_raw_transcript_text():
    memory = build_avatar_fleet_continuity_memory(
        membership=membership(),
        runtime=runtime(),
        sources=(source("m1"),),
    )
    payload = memory.as_dict()
    rendered = repr(payload)
    assert "buyer:m1:1" in rendered
    assert "verify:m1:1" in rendered
    assert "latest_buyer_utterance" not in rendered
    assert "transcript_turns" not in rendered
    assert memory.model_inference_performed is False
    assert memory.canonical_write_performed is False


def test_invalid_max_entries_fails_closed():
    for value in (0, 101):
        with pytest.raises(
            ValueError,
            match="max_entries must be between 1 and 100",
        ):
            build_avatar_fleet_continuity_memory(
                membership=membership(),
                runtime=runtime(),
                sources=(),
                max_entries=value,
            )


def test_continuity_never_grants_execution_authority():
    memory = build_avatar_fleet_continuity_memory(
        membership=membership(),
        runtime=runtime(),
        sources=(source("m1"),),
    )
    assert memory.speech_execution_allowed is False
    assert memory.commercial_execution_allowed is False
    assert memory.payment_execution_allowed is False
    assert memory.revenue_recognition_allowed is False
    assert memory.execution_authority == "none"
