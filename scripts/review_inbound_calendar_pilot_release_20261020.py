"""Read-only, evidence-based Revenue Recovery calendar staging deployment gate.

This inspector never provisions services, connects Google, dispatches agents,
changes a database, or upgrades a dark staging release to customer service.
Any unverified control remains blocked even when a developer fixture passes.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.error import URLError
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler
import subprocess
from typing import Callable
import json

DARK_HOST = "http://127.0.0.1:8794"
UNIT = Path("/etc/systemd/system/empire-inbound-recovery-staging.service")
OPENMANUS_OUTBOX = Path("/home/ubuntu/empire_recovery_runtime/openmanus_review_jobs.sqlite")


@dataclass(frozen=True)
class CalendarReleaseGate:
    name: str
    passed: bool
    observed: str
    requirement: str


class DenyRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def _response(url: str) -> tuple[int, dict | None]:
    # Fixed loopback origin; no cookies, auth headers, redirects, proxy, or
    # external provider access. Do not construct URL from user input.
    if not url.startswith(DARK_HOST + "/"):
        raise ValueError("only_private_loopback_staging_supported")
    from urllib.error import HTTPError
    opener = build_opener(ProxyHandler({}), DenyRedirect)
    try:
        with opener.open(url, timeout=2) as response:
            code = response.status
            if url.endswith("/health") and code == 200:
                payload = response.read(8193)
                if len(payload) > 8192:
                    return code, None
                return code, json.loads(payload)
            return code, None
    except HTTPError as exc:
        return exc.code, None
    except (URLError, OSError, ValueError):
        return 0, None


def inspect_recovery_calendar_staging(
    *,
    probe: Callable[[str], tuple[int, dict | None]] = _response,
    unit_installed: bool = False,
    reboot_autostart_enabled: bool = False,
    openmanus_worker_proven: bool = False,
    identity_config_proven: bool = False,
    oauth_client_proven: bool = False,
    kms_vault_proven: bool = False,
    database_rls_proven: bool = False,
) -> dict:
    """Explicit externally verified flags; NOT self-attested release approval."""
    health, body = probe(DARK_HOST + "/health")
    expected = bool(
        health == 200 and isinstance(body, dict)
        and body.get("status") == "dark-staging"
        and body.get("oauth_callbacks_enabled") is False
        and body.get("google_calendar_connected") is False
        and body.get("commercial_actions_authorized") is False
    )
    routes = tuple(probe(DARK_HOST + path)[0] for path in (
        "/v1/inbound-recovery/calendar-connect/status",
        "/v1/inbound-recovery/calendar-connect/callback",
        "/openapi.json",
    ))
    gates = (
        CalendarReleaseGate("private_staging_health", expected,
                            "200 dark-staging" if expected else "missing_or_untrusted",
                            "200 plus explicit no-live-actions health flags"),
        CalendarReleaseGate("dark_api_boundary", routes == (404, 404, 404),
                            "status/callback/docs=" + ",".join(map(str, routes)),
                            "all private OAuth routes and docs return 404"),
        CalendarReleaseGate("managed_service_installed_running", unit_installed,
                            "verified" if unit_installed else "not_independently_verified",
                            "systemd unit installed and running with loopback-only bind"),
        CalendarReleaseGate("managed_reboot_autostart", reboot_autostart_enabled,
                            "verified" if reboot_autostart_enabled else "disabled",
                            "approved service restarts automatically following reboot"),
        CalendarReleaseGate("existing_openmanus_worker", openmanus_worker_proven,
                            "verified" if openmanus_worker_proven else "pending_review_job_only",
                            "real authenticated worker with narrow review-only permissions"),
        CalendarReleaseGate("canonical_customer_identity", identity_config_proven,
                            "verified" if identity_config_proven else "not_activated",
                            "issuer and browser session backed by live tenant membership"),
        CalendarReleaseGate("customer_google_oauth", oauth_client_proven,
                            "verified" if oauth_client_proven else "not_activated",
                            "registered OAuth callback and customer-specific consent"),
        CalendarReleaseGate("production_secret_manager", kms_vault_proven,
                            "verified" if kms_vault_proven else "local_staging_vault_only",
                            "audited revocable secret manager; no fixture credentials"),
        CalendarReleaseGate("database_rls_migrations", database_rls_proven,
                            "verified" if database_rls_proven else "prepared_unapplied",
                            "isolated Postgres + RLS proof before migrations"),
    )
    return {
        "product": "inbound_revenue_recovery",
        "mode": "read_only_release_attestation",
        "gates": [asdict(g) for g in gates],
        "staging_ready": gates[0].passed and gates[1].passed,
        "pilot_activation_approved": False,
        "launch_blockers": [g.name for g in gates if not g.passed],
        "customer_calendar_connected": False,
        "real_revenue_verified": False,
        "openmanus_jobs_dispatched": 0,
        "writes": False,
    }


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--read-only", required=True, action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    # The tool cannot attest external authorizations. Do not populate the
    # production-only gates from service source or ambient environment.
    running = subprocess.run(
        ["systemctl", "is-active", "empire-inbound-recovery-staging.service"],
        capture_output=True, text=True, timeout=3, check=False,
    )
    enabled = subprocess.run(
        ["systemctl", "is-enabled", "empire-inbound-recovery-staging.service"],
        capture_output=True, text=True, timeout=3, check=False,
    )
    report = inspect_recovery_calendar_staging(
        unit_installed=UNIT.is_file() and running.returncode == 0 and
            running.stdout.strip() == "active",
        reboot_autostart_enabled=enabled.returncode == 0 and
            enabled.stdout.strip() == "enabled",
    )
    print(json.dumps(report, indent=2 if args.json else None, sort_keys=True))


if __name__ == "__main__":
    main()
