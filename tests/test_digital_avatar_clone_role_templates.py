import pytest

from empire_os.digital_avatar import AvatarMeetingMode
from empire_os.digital_avatar_clone_role_templates import (
    clone_role_template_catalog,
    get_clone_role_template,
    propose_clone_role,
)
from empire_os.digital_avatar_fleet_routing import (
    AvatarFleetMeetingNeed,
    route_avatar_for_meeting,
)
from empire_os.saas_scale import TenantMembership


EXPECTED = (
    "founder_executive",
    "sales_closer",
    "account_manager",
    "product_specialist",
    "technical_specialist",
)


def test_template_catalog_is_deterministic_unique_and_authority_free():
    catalog = clone_role_template_catalog()
    assert tuple(item.key for item in catalog) == EXPECTED
    assert len({item.key for item in catalog}) == len(catalog)
    for item in catalog:
        assert item.mode == "OBSERVE"
        assert item.identity_created is False
        assert item.consent_granted is False
        assert item.meeting_authority == "none"
        assert item.speech_execution_allowed is False
        assert item.commercial_execution_allowed is False
        assert item.payment_execution_allowed is False
        assert item.execution_authority == "none"
        payload = item.as_dict()
        assert "tenant_id" not in payload
        assert "owner_ref" not in payload
        assert "owner_consent_evidence_ref" not in payload


@pytest.mark.parametrize(
    ("key", "capability", "consultation"),
    [
        ("founder_executive", "strategy", "predictive_revenue"),
        ("sales_closer", "qualification", "sales"),
        ("account_manager", "customer_success", "product"),
        ("product_specialist", "solution_design", "technical"),
        ("technical_specialist", "integration", "research"),
    ],
)
def test_role_defaults_are_explicit_product_capabilities(
    key,
    capability,
    consultation,
):
    value = get_clone_role_template(key)
    assert capability in value.capability_labels
    assert consultation in value.consultation_domains


def test_unknown_template_fails_closed():
    with pytest.raises(KeyError, match="unknown clone role template"):
        get_clone_role_template("magic_closer")


def test_proposal_requires_explicit_owner_consent_input():
    with pytest.raises(ValueError, match="tenant/avatar/owner consent required"):
        propose_clone_role(
            template_key="sales_closer",
            tenant_id="tenant-a",
            avatar_id="avatar-a",
            owner_ref="person:a",
            owner_name="Owner A",
            owner_consent_evidence_ref="",
        )


def test_template_proposal_does_not_create_identity_or_authority():
    proposal = propose_clone_role(
        template_key="sales_closer",
        tenant_id="tenant-a",
        avatar_id="avatar-a",
        owner_ref="person:a",
        owner_name="Owner A",
        owner_consent_evidence_ref="consent:a:v1",
    )
    assert proposal.proposal_only is True
    assert proposal.identity_created is False
    assert proposal.consent_granted is False
    assert proposal.meeting_authority == "none"
    assert proposal.speech_execution_allowed is False
    assert proposal.commercial_execution_allowed is False
    assert proposal.payment_execution_allowed is False
    assert proposal.execution_authority == "none"


def test_materialized_binding_preserves_explicit_identity_and_template_capabilities():
    proposal = propose_clone_role(
        template_key="technical_specialist",
        tenant_id="tenant-a",
        avatar_id="avatar-tech",
        owner_ref="person:tech-owner",
        owner_name="Tech Owner",
        owner_consent_evidence_ref="consent:tech-owner:v7",
    )
    binding = proposal.to_fleet_binding()
    assert binding.tenant_id == "tenant-a"
    assert binding.avatar_id == "avatar-tech"
    assert binding.owner_ref == "person:tech-owner"
    assert binding.owner_name == "Tech Owner"
    assert binding.owner_consent_evidence_ref == "consent:tech-owner:v7"
    assert binding.capability_labels == (
        "technical",
        "integration",
        "architecture",
    )


def test_routing_uses_validated_materialized_binding_not_template_name():
    proposal = propose_clone_role(
        template_key="product_specialist",
        tenant_id="tenant-a",
        avatar_id="avatar-product",
        owner_ref="person:product-owner",
        owner_name="Product Owner",
        owner_consent_evidence_ref="consent:product-owner:v1",
    )
    result = route_avatar_for_meeting(
        membership=TenantMembership(
            tenant_id="tenant-a",
            user_id="operator-1",
            role="operator",
            status="active",
        ),
        need=AvatarFleetMeetingNeed(
            tenant_id="tenant-a",
            meeting_id="meeting-001",
            required_capability_labels=("solution_design",),
            objective_evidence_ref="objective:1",
            requested_mode=AvatarMeetingMode.COPILOT,
        ),
        bindings=(proposal.to_fleet_binding(),),
    )
    assert result.selection_ready is True
    assert result.selected_avatar_id == "avatar-product"
    assert "product_specialist" not in result.required_capability_labels
