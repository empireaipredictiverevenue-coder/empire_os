"""Connections remain gated even when local environment claims readiness."""
import pytest
from empire_os.a2a_external_connection_preflight_v1 import REQUIRED, review_connections


def test_empty_configuration_gates_every_live_action():
    result = review_connections({})
    assert result["meta"]["verified_business_account_connection"] is False
    assert result["meta"]["social_publish_enabled"] is False
    assert result["meta"]["messenger_or_instagram_dm_enabled"] is False
    assert result["stripe"]["payment_links_created"] == 0
    assert result["stripe"]["real_payments_authorized"] is False
    assert result["secret_values_in_output"] is False
    assert result["account_connections_performed_by_this_review"] is False


def test_credentials_present_do_not_prove_provider_authorization():
    present = {name: True for fields in REQUIRED.values() for name in fields}
    result = review_connections(
        present,
        account_readback_verified=True,
        meta_permissions_verified=True,
        meta_business_assets_verified=True,
        payment_provider_test_verified=True,
        payment_webhook_signature_verified=True,
        live_payment_authorized_by_finance_owner=True,
    )
    assert all(result["meta"]["configured_required_presence"].values())
    assert not result["meta"]["verified_business_account_connection"]
    assert not result["meta"]["social_publish_enabled"]
    assert not result["stripe"]["verified_sandbox_payment_provider_connection"]
    assert not result["stripe"]["real_payments_authorized"]


def test_malformed_status_inputs_fail_closed():
    with pytest.raises(ValueError, match="boolean_config_presence"):
        review_connections({"META_APP_ID": "secret"})
    with pytest.raises(ValueError):
        review_connections(None)


def test_no_secrets_appearing_as_values_in_preflight():
    result = review_connections({"STRIPE_SECRET_KEY": True, "META_APP_SECRET": True})
    assert result["stripe"]["configured_required_presence"]["STRIPE_SECRET_KEY"]
    assert result["meta"]["configured_required_presence"]["META_APP_SECRET"]
    assert "never_real_secret_value" not in str(result)
    assert result["execution_authority"] == "NONE"
