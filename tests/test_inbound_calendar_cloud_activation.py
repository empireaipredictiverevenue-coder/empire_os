"""Redacted Calendar OAuth activation preflight; no cloud or customer access."""
import copy
import json
from pathlib import Path

import pytest

import scripts.review_inbound_calendar_cloud_activation_20261020 as review

TENANT = "00000000-0000-0000-0000-000000000101"
TENANT_TWO = "00000000-0000-0000-0000-000000000102"
SECRET = "00000000-0000-0000-0000-000000000105"
SECRET_TWO = "00000000-0000-0000-0000-000000000106"
ORIGIN = "https://recovery.example.test"


def config():
    return {
        "schema_version": review.SCHEMA,
        "founder_approval_ref": "reviewed-founder-release-20261020",
        "google_client_id": "approved-client-id.apps.googleusercontent.com",
        "google_redirect_uri": ORIGIN + "/v1/inbound-recovery/calendar-connect/callback",
        "application_origin": ORIGIN,
        "scaleway_region": "fr-par",
        "calendar_secrets": [{
            "tenant_id": TENANT,
            "calendar_id": "example-owned-calendar@example.test",
            "provider_account_ref": "approved-google-tenant-owner",
            "secret_id": SECRET,
        }],
    }


def test_valid_contract_is_only_operator_inventory_not_proof(tmp_path):
    path = tmp_path / "cloud-pilot.json"
    path.write_text(json.dumps(config()))
    path.chmod(0o600)
    report = review.inspect_cloud_activation(config_file=path, check_unit=False)
    assert report["approved_mapping_count"] == 1
    assert report["gates"]["private_operator_config_valid"]
    assert report["gates"]["bounded_tenant_secret_mappings"]
    assert report["live_customer_oauth_authorized"] is False
    assert report["credentials_read"] is False
    assert report["config_values_disclosed"] is False
    assert TENANT not in json.dumps(report)
    assert SECRET not in json.dumps(report)
    assert "approved-client-id" not in json.dumps(report)
    assert report["gates"]["provider_iam_authorization_proven"] is False


@pytest.mark.parametrize("mutation", [
    lambda d: d.update({"schema_version": "not-our-schema"}),
    lambda d: d.update({"founder_approval_ref": "yes"}),
    lambda d: d.update({"application_origin": "http://recovery.example.test"}),
    lambda d: d.update({"google_redirect_uri": "https://evil.test/callback"}),
    lambda d: d.update({"google_redirect_uri": ORIGIN + "/callback?x=1"}),
    lambda d: d.update({"scaleway_region": "invalid-region"}),
    lambda d: d.update({"google_client_id": "placeholder"}),
    lambda d: d.update({"calendar_secrets": []}),
    lambda d: d["calendar_secrets"][0].update({"secret_id": "not-uuid"}),
    lambda d: d["calendar_secrets"][0].update({"tenant_id": "other-tenant"}),
    lambda d: d.update({"unexpected_private_key": "do-not-accept"}),
])
def test_invalid_or_extra_configuration_never_authorizes(mutation):
    data = config()
    mutation(data)
    assert not review._valid_config(data)


def test_cross_tenant_shared_secret_and_duplicate_mapping_denied():
    data = config()
    other = copy.deepcopy(data["calendar_secrets"][0])
    other["tenant_id"] = TENANT_TWO
    data["calendar_secrets"].append(other)
    assert not review._valid_config(data)
    data["calendar_secrets"][1]["secret_id"] = SECRET_TWO
    assert review._valid_config(data)
    data["calendar_secrets"][1]["tenant_id"] = TENANT
    data["calendar_secrets"][1]["secret_id"] = SECRET
    assert not review._valid_config(data)


def test_file_must_be_owner_only_regular_non_symlink(tmp_path):
    path = tmp_path / "approved.json"
    path.write_text(json.dumps(config()))
    path.chmod(0o644)
    assert not review.inspect_cloud_activation(
        config_file=path, check_unit=False,
    )["gates"]["private_operator_config_valid"]
    path.chmod(0o600)
    alias = tmp_path / "alias.json"
    alias.symlink_to(path)
    assert not review.inspect_cloud_activation(
        config_file=alias, check_unit=False,
    )["gates"]["private_operator_config_valid"]
    assert review.inspect_cloud_activation(
        config_file=path, check_unit=False,
    )["gates"]["private_operator_config_valid"]


def test_unit_scoped_credentials_metadata_without_reading_contents(tmp_path, monkeypatch):
    path = tmp_path / "credentials"
    path.mkdir(mode=0o700)
    monkeypatch.setattr(review, "SCOPED_CREDENTIALS", path)
    for name in review.CREDENTIAL_NAMES:
        item = path / name
        item.write_bytes(b"fixture-stored-only-in-test-" + b"x" * 32)
        item.chmod(0o400)
    assert review._credentials_present(path)
    (path / review.CREDENTIAL_NAMES[0]).chmod(0o600)
    assert not review._credentials_present(path)
    (path / review.CREDENTIAL_NAMES[0]).chmod(0o400)
    path.chmod(0o755)
    assert not review._credentials_present(path)


def test_absent_pilot_config_reports_blockers_without_network_or_writes(tmp_path):
    output = review.inspect_cloud_activation(
        config_file=tmp_path / "not-installed.json", check_unit=False,
    )
    assert not output["gates"]["private_operator_config_valid"]
    assert not output["gates"]["scoped_runtime_credentials_present"]
    assert output["live_customer_oauth_authorized"] is False
    assert output["writes"] is False
