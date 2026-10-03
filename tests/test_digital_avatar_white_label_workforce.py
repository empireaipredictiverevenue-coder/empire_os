import inspect

import pytest

import empire_os.digital_avatar_white_label_workforce as module
from empire_os.digital_avatar_clone_role_templates import (
    get_clone_role_template,
)
from empire_os.digital_avatar_white_label_workforce import (
    AvatarWorkforceWhiteLabelConfig,
    project_white_label_workforce,
)


def config(**overrides):
    values = {
        "tenant_id": "tenant-acme",
        "brand_name": "Acme",
        "workforce_product_name": "Acme AI Workforce",
        "allowed_template_keys": (
            "sales_closer",
            "technical_specialist",
        ),
        "brand_asset_ref": "brand:acme:v1",
    }
    values.update(overrides)
    return AvatarWorkforceWhiteLabelConfig(**values)


def test_allowed_template_subset_projects_in_configured_order():
    value = project_white_label_workforce(config())
    assert [role.template_key for role in value.roles] == [
        "sales_closer",
        "technical_specialist",
    ]
    assert value.roles[0].branded_label == (
        "Acme Sales / Closer AI Digital Avatar"
    )
    assert value.workforce_product_name == "Acme AI Workforce"


def test_projection_preserves_canonical_template_capabilities_and_consultation():
    value = project_white_label_workforce(config())
    for role in value.roles:
        source = get_clone_role_template(role.template_key)
        assert role.capability_labels == source.capability_labels
        assert role.consultation_domains == source.consultation_domains
        assert role.capability_override_allowed is False
        assert role.consultation_override_allowed is False
        assert role.template_authority == "none"


def test_unknown_or_duplicate_template_key_fails_closed():
    with pytest.raises(ValueError, match="unknown white-label workforce template"):
        project_white_label_workforce(
            config(allowed_template_keys=("sales_closer", "magic"))
        )
    with pytest.raises(ValueError, match="must be unique"):
        project_white_label_workforce(
            config(
                allowed_template_keys=(
                    "sales_closer",
                    "sales_closer",
                )
            )
        )


def test_brand_projection_contains_no_owner_consent_or_secret_fields():
    payload = project_white_label_workforce(config()).as_dict()
    rendered = repr(payload).lower()
    assert "owner_consent" not in rendered
    assert "owner_ref" not in rendered
    assert "api_key" not in rendered
    assert "password" not in rendered
    assert "secret" not in rendered


def test_ai_disclosure_cannot_be_disabled_by_configuration():
    value = project_white_label_workforce(config())
    assert value.mandatory_ai_disclosure is True
    assert value.disclosure_override_allowed is False
    assert value.live_identity_disclosure_still_required is True
    assert all("AI Digital Avatar" in role.branded_label for role in value.roles)


def test_projection_is_authority_free_and_nonpersistent():
    value = project_white_label_workforce(config())
    assert value.projection_only is True
    assert value.identity_created is False
    assert value.consent_granted is False
    assert value.tenant_configuration_persisted is False
    assert value.dns_domain_mutation is False
    assert value.speech_execution_allowed is False
    assert value.commercial_execution_allowed is False
    assert value.payment_execution_allowed is False
    assert value.revenue_recognition_allowed is False
    assert value.execution_authority == "none"
    assert value.mode == "OBSERVE"


def test_module_does_not_import_legacy_sqlite_white_label_or_tenant_store():
    source = inspect.getsource(module)
    assert "empire_os.whitelabel" not in source
    assert "empire_os.tenants" not in source
    assert "sqlite3" not in source
