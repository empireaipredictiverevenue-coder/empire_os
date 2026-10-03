import pytest

from empire_os.digital_avatar_commercial_packaging import (
    AvatarCommercialEntitlementEvidence,
    avatar_commercial_package_catalog,
    get_avatar_commercial_package,
    project_avatar_commercial_package,
)


def verified_catalog_row(product_code="digital_avatar_workforce", **overrides):
    values = {
        "product_id": "11111111-1111-4111-8111-111111111111",
        "version_id": "22222222-2222-4222-8222-222222222222",
        "product_code": product_code,
        "product_name": "Digital Avatar Workforce",
        "product_family": "digital_avatar",
        "billing_model": "monthly_subscription",
        "currency": "USD",
        "version": 1,
        "active": True,
        "catalog_state": "VERIFIED",
        "version_state": "VERIFIED",
        "binding_terms_ready": True,
        "price_basis": {
            "state": "VERIFIED",
            "unit": "per_month",
            "amount_cents": 123456,
            "currency": "USD",
            "billing_model": "monthly_subscription",
        },
        "acquisition_cost_basis": {"state": "VERIFIED"},
        "fulfilment_cost_basis": {"state": "VERIFIED"},
        "margin_policy": {"state": "VERIFIED"},
    }
    values.update(overrides)
    return values
def entitlement(product_code="digital_avatar_workforce", **overrides):
    values = {
        "verified": True,
        "reference": "commercial_terms:tenant-a:avatar:v1",
        "verified_at": "2026-10-02T22:00:00+00:00",
        "tenant_id": "tenant-a",
        "product_code": product_code,
        "allowed_role_template_keys": (
            "sales_closer",
            "product_specialist",
        ),
        "allowed_meeting_modes": ("SHADOW", "COPILOT"),
        "max_active_avatars": 4,
        "included_verified_meetings_per_month": 120,
        "white_label_allowed": False,
    }
    values.update(overrides)
    return AvatarCommercialEntitlementEvidence(**values)


def test_package_catalog_is_deterministic_and_contains_no_price_fields():
    catalog = avatar_commercial_package_catalog()
    assert tuple(item.key for item in catalog) == (
        "copilot",
        "workforce",
        "white_label_workforce",
    )
    for item in catalog:
        payload = item.as_dict()
        assert "amount_cents" not in payload
        assert "price" not in payload
        assert "currency" not in payload
        assert "billing_model" not in payload


def test_unknown_package_fails_closed():
    with pytest.raises(KeyError, match="unknown avatar commercial package"):
        get_avatar_commercial_package("magic")
def test_missing_catalog_row_blocks_commercial_readiness():
    result = project_avatar_commercial_package(
        tenant_id="tenant-a",
        package_key="workforce",
        catalog_row=None,
        entitlement=entitlement(),
    )
    assert result.commercially_ready is False
    assert result.entitlement_ready is True
    assert result.catalog_price == {}
    assert "catalog_product_missing" in result.blockers


def test_inactive_or_unverified_catalog_row_blocks():
    result = project_avatar_commercial_package(
        tenant_id="tenant-a",
        package_key="workforce",
        catalog_row=verified_catalog_row(
            active=False,
            catalog_state="UNKNOWN",
            version_state="PENDING",
        ),
        entitlement=entitlement(),
    )
    assert result.commercially_ready is False
    assert "catalog:product_inactive" in result.blockers
    assert "catalog:catalog_unverified" in result.blockers
    assert "catalog:version_unverified" in result.blockers
    assert result.catalog_price == {}


def test_verified_catalog_and_entitlement_are_commercially_ready():
    result = project_avatar_commercial_package(
        tenant_id="tenant-a",
        package_key="workforce",
        catalog_row=verified_catalog_row(),
        entitlement=entitlement(),
    )
    assert result.commercially_ready is True
    assert result.entitlement_ready is True
    assert result.blockers == ()
    assert result.catalog_product_id == "11111111-1111-4111-8111-111111111111"
    assert result.catalog_version_id == "22222222-2222-4222-8222-222222222222"
    assert result.catalog_version == 1
    assert result.catalog_price == {
        "unit": "per_month",
        "amount_cents": 123456,
        "currency": "USD",
        "billing_model": "monthly_subscription",
    }
def test_entitlement_must_be_verified_and_complete():
    result = project_avatar_commercial_package(
        tenant_id="tenant-a",
        package_key="workforce",
        catalog_row=verified_catalog_row(),
        entitlement=entitlement(
            verified=False,
            reference=None,
            max_active_avatars=None,
            included_verified_meetings_per_month=None,
        ),
    )
    assert result.commercially_ready is False
    assert result.entitlement_ready is False
    assert "entitlement_unverified" in result.blockers
    assert "entitlement_reference_missing" in result.blockers
    assert "entitlement_avatar_limit_missing" in result.blockers
    assert "entitlement_meeting_limit_missing" in result.blockers


def test_entitlement_tenant_or_product_mismatch_fails_closed():
    with pytest.raises(PermissionError, match="entitlement tenant mismatch"):
        project_avatar_commercial_package(
            tenant_id="tenant-a",
            package_key="workforce",
            catalog_row=verified_catalog_row(),
            entitlement=entitlement(tenant_id="tenant-b"),
        )
    with pytest.raises(ValueError, match="entitlement product mismatch"):
        project_avatar_commercial_package(
            tenant_id="tenant-a",
            package_key="workforce",
            catalog_row=verified_catalog_row(),
            entitlement=entitlement(product_code="digital_avatar_copilot"),
        )
def test_unknown_role_template_or_higher_authority_mode_blocks():
    bad_role = project_avatar_commercial_package(
        tenant_id="tenant-a",
        package_key="workforce",
        catalog_row=verified_catalog_row(),
        entitlement=entitlement(
            allowed_role_template_keys=("sales_closer", "magic_role"),
        ),
    )
    assert bad_role.commercially_ready is False
    assert "entitlement_role_unknown" in bad_role.blockers

    high_mode = project_avatar_commercial_package(
        tenant_id="tenant-a",
        package_key="workforce",
        catalog_row=verified_catalog_row(),
        entitlement=entitlement(
            allowed_meeting_modes=("SHADOW", "REPRESENT"),
        ),
    )
    assert high_mode.commercially_ready is False
    assert "entitlement_mode_exceeds_v1" in high_mode.blockers


def test_white_label_entitlement_only_allowed_in_white_label_package():
    blocked = project_avatar_commercial_package(
        tenant_id="tenant-a",
        package_key="workforce",
        catalog_row=verified_catalog_row(),
        entitlement=entitlement(white_label_allowed=True),
    )
    assert blocked.commercially_ready is False
    assert "entitlement_white_label_not_in_package" in blocked.blockers

    ready = project_avatar_commercial_package(
        tenant_id="tenant-a",
        package_key="white_label_workforce",
        catalog_row=verified_catalog_row(
            product_code="digital_avatar_white_label_workforce",
        ),
        entitlement=entitlement(
            product_code="digital_avatar_white_label_workforce",
            white_label_allowed=True,
        ),
    )
    assert ready.commercially_ready is True
    assert ready.white_label_allowed is True
def test_catalog_product_code_mismatch_fails_closed():
    with pytest.raises(ValueError, match="package/catalog product mismatch"):
        project_avatar_commercial_package(
            tenant_id="tenant-a",
            package_key="workforce",
            catalog_row=verified_catalog_row(
                product_code="some_other_product",
            ),
            entitlement=entitlement(),
        )


def test_projection_never_executes_checkout_payment_or_revenue():
    result = project_avatar_commercial_package(
        tenant_id="tenant-a",
        package_key="workforce",
        catalog_row=verified_catalog_row(),
        entitlement=entitlement(),
    )
    assert result.actual_revenue is False
    assert result.checkout_created is False
    assert result.subscription_mutation is False
    assert result.payment_request_creation is False
    assert result.funds_movement is False
    assert result.recognized_revenue is False
    assert result.execution_authority == "none"
