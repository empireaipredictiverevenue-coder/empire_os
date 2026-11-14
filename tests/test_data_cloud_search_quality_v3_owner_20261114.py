"""Offline owner-gateway source refresh contract.

No production changes, DB connections, systemd writes, metered requests or
credentials are used by these tests.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/activate_data_cloud_relevant_public_search_v3_20261114.py"
spec = importlib.util.spec_from_file_location("search_owner_v3", PATH)
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)


def test_v3_is_one_original_gateway_owner_not_new_service():
    assert owner.SERVICE == "empire-public-gateway.service"
    assert owner.CRM == "empire-revenue-crm-pilot.service"
    assert owner.OWNER_ENTRY == "owned_index_gateway_entrypoint_20261113v2:app"
    assert "data-cloud-founder-search-20261114-v3" in str(owner.V3)
    assert str(owner.OVERLAY).endswith(".conf")
    assert owner.V3 != owner.V2


def test_provenance_pins_both_original_owner_commits():
    assert owner.SOURCE_COMMIT == "2dd2a063533aee021f2d85bdbc15877aebd319c9"
    assert owner.SOURCE_SHA == "1edeec22be82f3be75588e94a251d418134afc484ba86cdee9e45607b1fbe993"
    assert owner.SOURCE_FILE.endswith("search_fabric/public_fallback.py")
    assert owner.ADAPTER.endswith("predictive_cloud_customer_api/gateway_candidate_entrypoint.py")


def test_no_arbitrary_or_dirty_worktree_admitted():
    with pytest.raises(RuntimeError, match="exact_data_cloud_source_commit_required"):
        owner.approve_source("not-a-commit")


def test_owner_code_preserves_old_gateway_on_failure():
    body = PATH.read_text()
    assert "cmd([\"systemctl\", \"daemon-reload\"])" in body
    assert "cmd([\"systemctl\", \"restart\", SERVICE])" in body
    assert "rollback()" in body
    assert "guarded_search_source_v3_activation_failed_rolled_back" in body
    assert "owned_index_gateway_entrypoint_20261113v2:app" in body


def test_single_owner_release_restricts_meter_and_billing_changes():
    source = PATH.read_text()
    assert "CREATE TABLE" not in source
    assert "GRANT EXECUTE" not in source
    assert "ALTER ROLE" not in source
    assert "UPDATE empire_data_cloud_api.tenants" not in source
    assert "supplier" not in source.lower()
    assert "paid_provider_calls_authorized" in source
    assert '"source_id") == "empire_search_fabric_public"' in source
