"""Read-only acceptance tests for the protected helper deployment/rollback."""
from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.stage_root_helper_agent_identity_20261022 import REPO

DEPLOY = REPO / "scripts/deploy_root_helper_identity_readonly_20261022.sh"
ROLLBACK = REPO / "scripts/rollback_root_helper_identity_readonly_20261022.sh"


def test_deployment_and_rollback_scripts_are_valid_bash():
    for script in (DEPLOY, ROLLBACK):
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def test_pinned_root_release_installation_cannot_run_by_default():
    source = DEPLOY.read_text()
    assert "ROOT_HELPER_IDENTITY_DRY_RUN_PASS" in source
    assert "root_owned_release_installer_required" in source
    assert "exact_founder_approval_flag_required" in source
    assert "ROOT_HELPER_IDENTITY_ROLLED_BACK_TO_ORIGINAL" in source
    assert "ROOT_HELPER_IDENTITY_READONLY_SOCKET_ACTIVATED" in source
    assert "cp -a --" in source
    assert "sha256sum --check" in source
    assert "original_helper_hash_changed" in source
    assert "legacy_canary" in source
    assert "identity_denial_canary" in source
    assert "ROOT_HELPER_IDENTITY_ACTIVATION_FAILED" in source
    assert "PYTHONDONTWRITEBYTECODE=1" in source
    assert "systemctl daemon-reload" in source
    assert "service_restart" not in source  # No new action in old RPC.


def test_rollback_removes_only_our_exact_override():
    source = ROLLBACK.read_text()
    assert "cmp -s" in source
    assert "override_changed_externally" in source
    assert "not_on_our_pinned_release" in source
    assert "original_release_changed" in source
    assert "ROOT_HELPER_IDENTITY_READONLY_ROLLBACK_VERIFIED" in source


def test_read_only_preflight_verifies_actual_running_original_root_helper():
    result = subprocess.run(["bash", str(DEPLOY), "--check"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "running root helper unchanged" in result.stdout
    assert "ACTIVATED" not in result.stdout


def test_root_required_before_apply_and_cannot_trigger_unprivileged():
    result = subprocess.run(
        ["bash", str(DEPLOY), "--apply-founder-approved"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "root_owned_release_installer_required" in result.stderr
