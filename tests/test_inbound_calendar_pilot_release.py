"""Verify staging signals without declaring a customer launch."""
import json
import subprocess
import sys
from scripts.review_inbound_calendar_pilot_release_20261020 import (
    DARK_HOST,
    inspect_recovery_calendar_staging,
)


def dark_response(url):
    if url == DARK_HOST + "/health":
        return 200, {
            "status": "dark-staging",
            "oauth_callbacks_enabled": False,
            "google_calendar_connected": False,
            "commercial_actions_authorized": False,
        }
    return 404, None


def test_dark_staging_gates_are_separate_from_pilot():
    report = inspect_recovery_calendar_staging(
        probe=dark_response, unit_installed=True,
    )
    assert report["staging_ready"] is True
    assert report["pilot_activation_approved"] is False
    assert "managed_service_installed_running" not in report["launch_blockers"]
    assert "managed_reboot_autostart" in report["launch_blockers"]
    assert "existing_openmanus_worker" in report["launch_blockers"]
    assert "production_secret_manager" in report["launch_blockers"]
    assert "customer_google_oauth" in report["launch_blockers"]
    assert report["writes"] is False
    assert report["real_revenue_verified"] is False


def test_unhealthy_and_unexpected_oauth_routes_rejected():
    assert not inspect_recovery_calendar_staging(
        probe=lambda _: (0, None),
    )["staging_ready"]

    def changed_route(url):
        if url.endswith("/callback"):
            return 200, {"connected": True}
        return dark_response(url)

    assert not inspect_recovery_calendar_staging(
        probe=changed_route,
    )["staging_ready"]


def test_explicit_flagged_cli_runs_read_only():
    args = [
        sys.executable, "-B", "-m",
        "scripts.review_inbound_calendar_pilot_release_20261020",
    ]
    no = subprocess.run(args, capture_output=True, text=True)
    assert no.returncode != 0
    yes = subprocess.run(
        args + ["--read-only", "--json"],
        capture_output=True, text=True,
    )
    assert yes.returncode == 0, yes.stderr
    report = json.loads(yes.stdout)
    assert report["mode"] == "read_only_release_attestation"
    assert report["pilot_activation_approved"] is False
    assert report["writes"] is False
