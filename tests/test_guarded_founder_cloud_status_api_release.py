"""Only the Cloud status API module may be promoted into the existing Founder app."""
from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1] /
    "scripts/install_guarded_founder_cloud_status_api_20261021.sh"
)
COMMIT = "5caaa410676942890caba41924d95338680466f1"


@pytest.mark.parametrize("args", (
    (), ("--check",), ("--check", "main"), ("--apply-owner-approved-observe", "bogus")
))
def test_only_exact_existing_cloud_release_accepted(args):
    completed = subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True,
        text=True, timeout=10, check=False,
    )
    assert completed.returncode != 0
    assert "FOUNDER_CLOUD_STATUS_API_PROMOTED" not in completed.stdout


def test_guarded_founder_patch_is_single_module_only():
    content = SCRIPT.read_text()
    for required in (
        "EXPECTED_SOURCE_SHA=", "EXPECTED_TARGET_SHA=",
        "EXPECTED_ROUTER_SHA=", "EXPECTED_STATUS_SHA=", "EXPECTED_UNIT_SHA=",
        "SOURCE='/opt/empire/predictive_cloud_guard_5caaa4106769/empire_os/predictive_cloud_status_api.py'",
        "cp -p -- \"$TARGET\" \"$backup/previous_status_api.py\"",
        "mv -T -- \"$tmp\" \"$TARGET\"",
        "systemctl restart \"$SERVICE\"",
        "FOUNDER_CLOUD_STATUS_LIVE_API_VALIDATION_PASS",
        "FOUNDER_CLOUD_STATUS_SINGLE_MODULE_ROLLED_BACK",
        "ROLLBACK_FILE=",
        "OTHER_ROUTERS_CLOUD_TIMER_DB_OUTBOUND_PAYMENTS_UNCHANGED",
        "flock -n 9",
        "systemctl show \"$SERVICE\" -p DropInPaths",
    ):
        assert required in content
    assert "systemctl restart empire-predictive-cloud-materializer" not in content
    for forbidden in (
        "CREATE ROLE", "ALTER TABLE", "DROP TABLE", "psql ",
        "systemctl stop empire-predictive-intelligence", "curl -X POST",
    ):
        assert forbidden not in content


def test_founder_cloud_api_source_is_constrained_to_existing_one():
    code = SCRIPT.read_text()
    assert "empire_founder_api_hist052_bridge_additive_20261018" in code
    assert "/srv/empire_os/empire_os/predictive_cloud_status_api.py" not in code
    assert "founder_dashboard_service.py" in code  # hash check only
    assert '[[ "$(sha "$SERVICE_SOURCE")" == "$EXPECTED_ROUTER_SHA" ]]' in code
    assert '[[ "$(sha "$TARGET")" == "$EXPECTED_SOURCE_SHA" ]]' in code
