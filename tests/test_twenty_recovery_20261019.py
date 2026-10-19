"""Twenty recovery without replacing canonical EmpireDB or emailing anyone."""
from datetime import datetime, timezone
import json
import subprocess

import pytest

from empire_os.twenty_recovery_boundary import (
    inspect_twenty, compare_twenty_business_export,
)
from scripts.audit_original_twenty_docker_20261019 import inspect_docker


def test_original_twenty_history_not_confused_with_running_service(tmp_path):
    plugin = tmp_path / "twenty.yaml"
    plugin.write_text("name: twenty-crm")
    r = inspect_twenty(
        tmp_path, plugin_path=plugin,
        commit_probe=lambda root: True,
        health_probe=lambda: {
            "twenty_health_http_status": 404,
            "twenty_health_endpoint_responding": False,
        },
    )
    assert r["state"] == "HISTORICAL_CODE_PRESENT_ORIGINAL_DATA_UNVERIFIED"
    assert r["old_git_startup_reference_found"] is True
    assert r["hermes_catalog_definition_found"] is True
    assert r["original_twenty_database_restored"] is False
    assert r["running_original_instance_verified"] is False
    assert r["canonical_crm_database"] == "EmpireDB PostgreSQL"
    assert r["canonical_empiredb_writes"] is False
    assert r["outbound_authorized"] is False


def test_twenty_healthy_endpoint_cannot_prove_original_db(tmp_path):
    d = inspect_twenty(
        tmp_path, plugin_path=tmp_path / "missing.yaml",
        commit_probe=lambda root: False,
        health_probe=lambda: {
            "twenty_health_http_status": 200,
            "twenty_health_endpoint_responding": True,
        },
    )
    assert d["original_twenty_database_restored"] is False
    assert d["running_original_instance_verified"] is False


def test_approved_business_export_comparison_does_not_import_contacts():
    rows = [
        {"tenant": "empire", "company_domain": "solar-example.co.uk",
         "company_source_verified": True, "person_email": "PRIVATE@example.com"},
        {"tenant": "empire", "company_domain": "solar-example.co.uk",
         "company_source_verified": True},
        {"tenant": "other", "company_domain": "other.com",
         "company_source_verified": True},
        {"tenant": "empire", "company_domain": "roofingcompany.com",
         "company_source_verified": False},
    ]
    d = compare_twenty_business_export(rows, tenant="empire")
    assert d["reviewed_rows"] == 4
    assert d["businesses_for_future_canonical_identity_review"] == 1
    assert d["held_rows"] == 3
    assert d["contacts_or_people_exported"] is False
    assert d["twenty_records_imported"] == 0
    assert d["canonical_empiredb_writes"] is False
    assert "PRIVATE" not in json.dumps(d)


@pytest.mark.parametrize("rows", [[{}] * 251, "not-a-list"])
def test_invalid_export_size_or_type_holds(rows):
    with pytest.raises(ValueError):
        compare_twenty_business_export(rows, tenant="empire")


def test_no_docker_access_does_not_claim_no_original_volumes():
    class Result:
        returncode = 1
        stdout = ""
        stderr = "permission denied: PRIVATE DOCKER SERVER TOKEN"
    got = inspect_docker(runner=lambda *a, **kw: Result())
    assert got["state"] == "DOCKER_OWNER_ACCESS_REQUIRED"
    assert got["twenty_volumes_verified"] is False
    assert got["twenty_data_restored"] is False
    assert "TOKEN" not in json.dumps(got)


def test_privileged_owner_inventory_only_names_not_environment():
    class Result:
        returncode = 0
        stderr = "secret-do-not-display"
        def __init__(self, stdout):
            self.stdout = stdout
    responses = [
        "twenty-server|twentycrm/twenty:v2|Exited (0)\nother|nginx|Up 3 days",
        "twenty_db-data\nother_db\ntwenty_server-local-data",
    ]
    out = inspect_docker(runner=lambda *a, **kw: Result(responses.pop(0)))
    assert out["state"] == "READ_ONLY_METADATA_INVENTORY_COMPLETE"
    assert len(out["twenty_containers"]) == 1
    assert len(out["twenty_named_volumes"]) == 2
    assert out["original_postgresql_content_restored"] is False
    assert "secret-do-not-display" not in json.dumps(out)


def test_founder_private_twenty_route_reports_unverified_restore(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import empire_os.founder_lead_supply_api as api
    app = FastAPI()
    app.include_router(api.create_founder_lead_supply_router(
        report_path=tmp_path / "missing-report.json",
        exchange_path=tmp_path / "missing-exchange.json",
    ))
    original = api.inspect_twenty
    try:
        api.inspect_twenty = lambda *a, **kw: inspect_twenty(
            tmp_path, plugin_path=tmp_path / "missing.yaml",
            commit_probe=lambda root: False,
            health_probe=lambda: {
                "twenty_health_http_status": 404,
                "twenty_health_endpoint_responding": False,
            },
        )
        data = TestClient(app).get("/v1/founder-lead-supply/twenty-recovery").json()
    finally:
        api.inspect_twenty = original
    assert data["available"] is True
    assert data["original_customer_records_verified"] is False
    assert data["canonical_empiredb_writes"] is False
