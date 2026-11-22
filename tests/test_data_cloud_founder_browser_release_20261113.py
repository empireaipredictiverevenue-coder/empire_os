"""Guarded original CRM browser release checks; synthetic only."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PUBLISHER = Path(__file__).resolve().parents[1] / "scripts/activate_data_cloud_founder_browser_guarded_20261113.py"
spec = importlib.util.spec_from_file_location("founder_browser_owner_release", PUBLISHER)
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def test_release_is_only_one_original_crm_unit_addition():
    data = publisher.dropin_contents().decode()
    assert data.count("LoadCredential=") == 1
    assert "empire-data-cloud-founder-api-key:" in data
    assert data.count("ExecStart=/") == 1
    assert publisher.ENTRY in data
    assert "--host 127.0.0.1 --port 8783 --no-proxy-headers" in data
    assert "PYTHONDONTWRITEBYTECODE=1" in data
    for forbidden in ("postgres", "CREATE ROLE", "ALTER TABLE", "ExecStartPre=", "Environment=API_KEY", "systemctl"):
        assert forbidden not in data


def test_commit_pin_must_be_exact_and_worktree_clean(monkeypatch):
    with pytest.raises(RuntimeError, match="exact_founder_release_commit_required"):
        publisher.read_source_commit("uncommitted")
    monkeypatch.setattr(publisher, "source_git", lambda *args: (
        "f" * 40 if args == ("rev-parse", "HEAD") else " M changed.py"))
    with pytest.raises(RuntimeError, match="branch_changed_or_dirty"):
        publisher.read_source_commit("f" * 40)


def test_current_service_owner_change_fails_closed(monkeypatch):
    values = {
        ("systemctl", "is-active", publisher.UNIT): "active",
        ("systemctl", "is-active", publisher.GW_UNIT): "active",
        ("systemctl", "show", publisher.UNIT, "-p", "ExecStart", "--value"):
            "replaced_private_app:app",
    }
    monkeypatch.setattr(publisher, "call", lambda args, text=True: values.get(tuple(args), ""))
    with pytest.raises(RuntimeError, match="original_multi_pipeline_crm_owner_changed"):
        publisher.live_baseline()


def test_release_source_paths_are_always_in_original_owned_worktree():
    assert publisher.ROOT.name == "data_cloud_source_provenance_review_20261109"
    assert publisher.ENTRY == "data_cloud_founder_browser_entrypoint_20261113:app"
    assert len(publisher.FILES) == 4
    assert all("predictive_cloud_customer_api/" in name or name.startswith("scripts/")
               for name in publisher.FILES)
    assert publisher.KEY.name == "founder-api-key.secret"
    assert publisher.OVERLAY.parent.name == "empire-revenue-crm-pilot.service.d"
