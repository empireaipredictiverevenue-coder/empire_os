from dataclasses import replace

import pytest

from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.digital_avatar_fleet_metering import (
    aggregate_verified_meeting_usage,
    build_verified_meeting_usage,
)


def runtime(**overrides):
    values = {
        "tenant_id": "tenant-a",
        "avatar_id": "avatar-a",
        "owner_ref": "person:avatar-a",
        "owner_name": "Owner A",
        "capability_labels": ("sales",),
        "membership_user_id": "user-1",
        "membership_role": "operator",
        "owner_consent_evidence_ref": "consent:avatar-a:v1",
    }
    values.update(overrides)
    return AvatarFleetRuntimeBinding(**values)


def lifecycle(**overrides):
    values = {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-a",
        "bot_id": "bot-001",
        "status_code": "done",
        "updated_at": "2026-10-03T12:30:00+00:00",
        "joined_meeting": True,
        "terminal": True,
        "fatal": False,
        "evidence_refs": ("recall-verification:msg:1:abc",),
        "truth_class": "VERIFIED",
        "speech_execution": False,
        "execution_authority": "none",
    }
    values.update(overrides)
    return values


def test_verified_completed_meeting_produces_one_usage_unit():
    event = build_verified_meeting_usage(
        runtime=runtime(),
        lifecycle_state=lifecycle(),
    )
    assert event is not None
    assert event.metric == "digital_avatar_verified_meeting_session"
    assert event.units == 1
    assert event.period == "2026-10"
    assert event.billable_candidate is True
    assert event.commercial_terms_bound is False
    assert event.charge_executed is False
    assert event.payment_execution is False
    assert event.revenue_recognition is False
    assert event.execution_authority == "none"


@pytest.mark.parametrize(
    "overrides",
    [
        {"status_code": "in_waiting_room", "terminal": False, "joined_meeting": False},
        {"status_code": "in_call_recording", "terminal": False},
        {"status_code": "fatal", "fatal": True},
        {"status_code": "media_expired", "terminal": True},
        {"status_code": "done", "joined_meeting": False},
    ],
)
def test_non_completed_or_failed_lifecycle_does_not_meter(overrides):
    assert build_verified_meeting_usage(
        runtime=runtime(),
        lifecycle_state=lifecycle(**overrides),
    ) is None


def test_non_verified_or_missing_evidence_does_not_meter():
    assert build_verified_meeting_usage(
        runtime=runtime(),
        lifecycle_state=lifecycle(truth_class="OBSERVED"),
    ) is None
    assert build_verified_meeting_usage(
        runtime=runtime(),
        lifecycle_state=lifecycle(evidence_refs=()),
    ) is None


def test_avatar_mismatch_and_authority_violations_fail_closed():
    with pytest.raises(PermissionError, match="avatar mismatch"):
        build_verified_meeting_usage(
            runtime=runtime(),
            lifecycle_state=lifecycle(avatar_id="avatar-b"),
        )

    with pytest.raises(ValueError, match="forbidden authority"):
        build_verified_meeting_usage(
            runtime=runtime(),
            lifecycle_state=lifecycle(execution_authority="live"),
        )

    with pytest.raises(ValueError, match="speech invariant"):
        build_verified_meeting_usage(
            runtime=runtime(),
            lifecycle_state=lifecycle(speech_execution=True),
        )


def test_period_is_derived_from_utc_not_local_calendar_month():
    event = build_verified_meeting_usage(
        runtime=runtime(),
        lifecycle_state=lifecycle(
            updated_at="2026-11-01T00:30:00+01:00",
        ),
    )
    assert event is not None
    assert event.observed_at == "2026-10-31T23:30:00+00:00"
    assert event.period == "2026-10"


def test_identical_duplicate_usage_dedupes_to_one_unit():
    event = build_verified_meeting_usage(
        runtime=runtime(),
        lifecycle_state=lifecycle(),
    )
    monthly = aggregate_verified_meeting_usage(
        tenant_id="tenant-a",
        period="2026-10",
        events=(event, event),
    )
    assert monthly.observed_monthly_usage == 1
    assert len(monthly.usage_keys) == 1
    assert monthly.billing_execution is False
    assert monthly.payment_execution is False
    assert monthly.revenue_recognition is False
    assert monthly.execution_authority == "none"


def test_conflicting_duplicate_usage_fails_closed():
    event = build_verified_meeting_usage(
        runtime=runtime(),
        lifecycle_state=lifecycle(),
    )
    conflict = replace(event, bot_id="bot-conflict")
    with pytest.raises(ValueError, match="idempotency conflict"):
        aggregate_verified_meeting_usage(
            tenant_id="tenant-a",
            period="2026-10",
            events=(event, conflict),
        )


def test_cross_tenant_aggregate_fails_closed():
    event = build_verified_meeting_usage(
        runtime=runtime(),
        lifecycle_state=lifecycle(),
    )
    with pytest.raises(PermissionError, match="cross-tenant"):
        aggregate_verified_meeting_usage(
            tenant_id="tenant-b",
            period="2026-10",
            events=(event,),
        )


def test_other_period_is_not_counted_and_empty_period_is_not_fabricated():
    event = build_verified_meeting_usage(
        runtime=runtime(),
        lifecycle_state=lifecycle(),
    )
    with pytest.raises(ValueError, match="no verified usage for period"):
        aggregate_verified_meeting_usage(
            tenant_id="tenant-a",
            period="2026-11",
            events=(event,),
        )


def test_monthly_usage_converts_to_saas_usage_observation_only():
    event = build_verified_meeting_usage(
        runtime=runtime(),
        lifecycle_state=lifecycle(),
    )
    monthly = aggregate_verified_meeting_usage(
        tenant_id="tenant-a",
        period="2026-10",
        events=(event,),
    )
    observation = monthly.to_saas_usage_observation()
    assert observation.tenant_id == "tenant-a"
    assert observation.metric == "digital_avatar_verified_meeting_session"
    assert observation.value == 1
    assert observation.period == "2026-10"
    assert observation.source.startswith("digital_avatar_verified_lifecycle:")


def test_usage_key_is_stable_across_provider_retry_variants():
    first = build_verified_meeting_usage(
        runtime=runtime(),
        lifecycle_state=lifecycle(
            bot_id="bot-001",
            evidence_refs=("recall-verification:msg:1:abc",),
        ),
    )
    second = build_verified_meeting_usage(
        runtime=runtime(),
        lifecycle_state=lifecycle(
            bot_id="bot-002",
            evidence_refs=("recall-verification:msg:2:def",),
        ),
    )
    assert first.usage_key == second.usage_key
