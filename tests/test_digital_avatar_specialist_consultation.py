import pytest

from empire_os.departments import default_departments
from empire_os.digital_avatar import AvatarMeetingMode
from empire_os.digital_avatar_fleet import AvatarFleetRuntimeBinding
from empire_os.digital_avatar_specialist_consultation import (
    AvatarSpecialistConsultationRequest,
    build_avatar_specialist_consultation_plan,
)


def runtime(**overrides):
    values = {
        "tenant_id": "tenant-a",
        "avatar_id": "avatar-a",
        "owner_ref": "person:avatar-a",
        "owner_name": "Owner A",
        "capability_labels": ("sales", "product"),
        "membership_user_id": "user-1",
        "membership_role": "operator",
        "owner_consent_evidence_ref": "consent:avatar-a:v1",
    }
    values.update(overrides)
    return AvatarFleetRuntimeBinding(**values)


def request(*domains, **overrides):
    values = {
        "tenant_id": "tenant-a",
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-a",
        "mode": AvatarMeetingMode.COPILOT,
        "consultation_domains": tuple(domains),
        "question_evidence_ref": "buyer:meeting-001:q1",
        "objective_evidence_ref": "objective:meeting-001:v1",
        "max_specialists": 3,
    }
    values.update(overrides)
    return AvatarSpecialistConsultationRequest(**values)
@pytest.mark.parametrize(
    ("domain", "department_key"),
    [
        ("sales", "sales_revenue"),
        ("product", "product"),
        ("technical", "engineering"),
        ("predictive_revenue", "data_quant"),
        ("research", "rd_innovation"),
        ("marketing", "marketing_growth"),
        ("strategy", "strategy"),
    ],
)
def test_domain_resolves_to_existing_department_registry(
    domain,
    department_key,
):
    plan = build_avatar_specialist_consultation_plan(
        runtime=runtime(),
        request=request(domain),
    )
    assert plan.selected_department_keys == (department_key,)
    registry = {item.key: item for item in default_departments()}
    lane = plan.selected_lanes[0]
    assert lane.department_name == registry[department_key].name
    assert lane.mission == registry[department_key].mission
    assert lane.components == registry[department_key].components
    assert lane.agent_roles == registry[department_key].agent_roles
    assert lane.consultation_authority == "read_only"


def test_duplicate_domains_dedupe_and_order_is_preserved():
    plan = build_avatar_specialist_consultation_plan(
        runtime=runtime(),
        request=request("sales", "product", "sales", "technical"),
    )
    assert plan.requested_domains == (
        "sales",
        "product",
        "technical",
    )
    assert plan.selected_department_keys == (
        "sales_revenue",
        "product",
        "engineering",
    )
def test_max_specialists_is_bounded_and_truncation_is_explicit():
    plan = build_avatar_specialist_consultation_plan(
        runtime=runtime(),
        request=request(
            "sales",
            "product",
            "technical",
            "predictive_revenue",
            max_specialists=2,
        ),
    )
    assert plan.selected_department_keys == (
        "sales_revenue",
        "product",
    )
    assert plan.truncated_domains == (
        "technical",
        "predictive_revenue",
    )


def test_unknown_domain_fails_closed():
    with pytest.raises(ValueError, match="unknown consultation domain"):
        build_avatar_specialist_consultation_plan(
            runtime=runtime(),
            request=request("sales", "magic"),
        )


@pytest.mark.parametrize(
    "mode",
    [
        AvatarMeetingMode.REPRESENT,
        AvatarMeetingMode.NEGOTIATE,
        AvatarMeetingMode.CLOSE,
    ],
)
def test_modes_above_copilot_are_rejected(mode):
    with pytest.raises(ValueError, match="authority ceiling"):
        build_avatar_specialist_consultation_plan(
            runtime=runtime(),
            request=request("sales", mode=mode),
        )
def test_runtime_tenant_and_avatar_must_match():
    with pytest.raises(
        PermissionError,
        match="consultation_runtime_tenant_mismatch",
    ):
        build_avatar_specialist_consultation_plan(
            runtime=runtime(tenant_id="tenant-b"),
            request=request("sales"),
        )

    with pytest.raises(
        PermissionError,
        match="consultation_runtime_avatar_mismatch",
    ):
        build_avatar_specialist_consultation_plan(
            runtime=runtime(avatar_id="avatar-b"),
            request=request("sales"),
        )


def test_missing_department_owner_fails_closed():
    departments = tuple(
        item
        for item in default_departments()
        if item.key != "engineering"
    )
    with pytest.raises(
        ValueError,
        match="consultation department owner missing: engineering",
    ):
        build_avatar_specialist_consultation_plan(
            runtime=runtime(),
            request=request("technical"),
            departments=departments,
        )


def test_consultation_plan_carries_only_evidence_refs_and_zero_authority():
    plan = build_avatar_specialist_consultation_plan(
        runtime=runtime(),
        request=request("sales", "predictive_revenue"),
    )
    assert plan.evidence_refs == (
        "buyer:meeting-001:q1",
        "objective:meeting-001:v1",
    )
    assert plan.read_only is True
    assert plan.private_to_owner is True
    assert plan.recommendation_only is True
    assert plan.department_work_enqueued is False
    assert plan.external_execution_performed is False
    assert plan.speech_execution_allowed is False
    assert plan.commercial_execution_allowed is False
    assert plan.payment_execution_allowed is False
    assert plan.revenue_recognition_allowed is False
    assert plan.execution_authority == "none"
def test_missing_evidence_ref_fails_closed():
    with pytest.raises(
        ValueError,
        match="question evidence ref required",
    ):
        build_avatar_specialist_consultation_plan(
            runtime=runtime(),
            request=request("sales", question_evidence_ref=""),
        )


def test_invalid_max_specialists_fails_closed():
    with pytest.raises(ValueError, match="outside supported range"):
        build_avatar_specialist_consultation_plan(
            runtime=runtime(),
            request=request("sales", max_specialists=0),
        )
