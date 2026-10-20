"""Read-only, fail-closed operator preflight for customer Calendar OAuth.

No cloud API calls, secret contents, customer data, accounts, token minting,
systemd writes, or tenant databases. Never accept env-derived generic keys.
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

SCHEMA = "empire.inbound.calendar.cloud_pilot.v1"
OAUTH_UNIT = "empire-inbound-recovery-calendar-oauth.service"
SCOPED_CREDENTIALS = Path("/run/credentials") / OAUTH_UNIT
CREDENTIAL_NAMES = (
    "scaleway-secret-iam-token",
    "google-calendar-oauth-client-secret",
    "calendar-owner-ed25519-private-key",
    "calendar-oauth-state-encryption-key",
    "calendar-consent-evidence-hmac-key",
)
_ALLOWED = {
    "schema_version", "founder_approval_ref", "google_client_id",
    "application_origin", "google_redirect_uri",
    "scaleway_region", "calendar_secrets",
}
_ITEM = {"tenant_id", "calendar_id", "provider_account_ref", "secret_id"}
_GOOGLE_CLIENT = re.compile(r"^[A-Za-z0-9_-]{8,200}\.apps\.googleusercontent\.com$")
_APPROVAL = re.compile(r"^[A-Za-z0-9:@._/-]{12,160}$")


def _canonical_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (TypeError, ValueError, AttributeError):
        return False


def _private_file(path: Path, *, limit: int = 65536) -> bool:
    # Stat before reading; arbitrary environment paths are never accepted.
    try:
        if not path.is_absolute() or path.is_symlink():
            return False
        meta = path.stat()
        return bool(
            stat.S_ISREG(meta.st_mode)
            and meta.st_uid in (0, os.geteuid())
            and not (stat.S_IMODE(meta.st_mode) & 0o077)
            and 1 <= meta.st_size <= limit
        )
    except OSError:
        return False


def _valid_config(data: object) -> bool:
    if not isinstance(data, dict) or set(data) != _ALLOWED:
        return False
    if data["schema_version"] != SCHEMA:
        return False
    if (not isinstance(data["founder_approval_ref"], str)
        or not _APPROVAL.fullmatch(data["founder_approval_ref"])):
        return False
    if (not isinstance(data["google_client_id"], str)
        or not _GOOGLE_CLIENT.fullmatch(data["google_client_id"])):
        return False
    if data["scaleway_region"] not in ("fr-par", "nl-ams", "pl-waw"):
        return False
    origin = data["application_origin"]
    redirect = data["google_redirect_uri"]
    if not isinstance(origin, str) or not isinstance(redirect, str):
        return False
    try:
        o = urlsplit(origin)
        callback = urlsplit(redirect)
    except ValueError:
        return False
    if (o.scheme != "https" or not o.hostname or o.username or o.password
        or o.path not in ("", "/") or o.query or o.fragment
        or callback.scheme != "https" or callback.username or callback.password
        or callback.query or callback.fragment
        or redirect != origin + "/v1/inbound-recovery/calendar-connect/callback"):
        return False
    bindings = data["calendar_secrets"]
    if not isinstance(bindings, list) or not 1 <= len(bindings) <= 10:
        return False
    by_secret: set[str] = set()
    by_binding: set[tuple[str, str, str]] = set()
    for item in bindings:
        if not isinstance(item, dict) or set(item) != _ITEM:
            return False
        if (not _canonical_uuid(item["tenant_id"])
            or not _canonical_uuid(item["secret_id"])):
            return False
        for name in ("calendar_id", "provider_account_ref"):
            value = item[name]
            if (not isinstance(value, str) or not 1 <= len(value.strip()) <= 240
                or value != value.strip()):
                return False
        key = (item["tenant_id"], item["calendar_id"], item["provider_account_ref"])
        if item["secret_id"] in by_secret or key in by_binding:
            return False
        by_secret.add(item["secret_id"])
        by_binding.add(key)
    return True


def _credentials_present(directory: Path) -> bool:
    # Metadata only, not key material. Scoped unit is never the staging unit.
    if directory != SCOPED_CREDENTIALS:
        return False
    try:
        if directory.is_symlink() or not directory.is_dir():
            return False
        if stat.S_IMODE(directory.stat().st_mode) & 0o007:
            return False
        for name in CREDENTIAL_NAMES:
            credential = directory / name
            if credential.is_symlink() or not credential.is_file():
                return False
            metadata = credential.stat()
            if (not stat.S_ISREG(metadata.st_mode)
                or (stat.S_IMODE(metadata.st_mode) & 0o222)
                or not 20 <= metadata.st_size <= 16384):
                return False
    except OSError:
        return False
    return True


def inspect_cloud_activation(
    *, config_file: Path,
    credentials_directory: Path = SCOPED_CREDENTIALS,
    check_unit: bool = True,
) -> dict:
    config_valid = False
    approved_count = 0
    if _private_file(config_file):
        try:
            candidate = json.loads(config_file.read_text(encoding="utf-8"))
            config_valid = _valid_config(candidate)
            if config_valid:
                approved_count = len(candidate["calendar_secrets"])
        except (OSError, UnicodeError, ValueError, TypeError):
            pass
    unit_installed = Path("/etc/systemd/system").joinpath(OAUTH_UNIT).is_file()
    unit_running = False
    if check_unit and unit_installed:
        try:
            status = subprocess.run(
                ["systemctl", "is-active", OAUTH_UNIT],
                capture_output=True, text=True, timeout=3, check=False,
            )
            unit_running = status.returncode == 0 and status.stdout.strip() == "active"
        except (OSError, subprocess.TimeoutExpired):
            unit_running = False
    credentials_ready = _credentials_present(credentials_directory)
    # The config is an operator *inventory*, not proof that the actual
    # IAM grant, OAuth redirect, Google calendar or RLS is usable.
    gates = {
        "private_operator_config_valid": config_valid,
        "bounded_tenant_secret_mappings": config_valid and approved_count > 0,
        "calendar_oauth_unit_installed": unit_installed,
        "calendar_oauth_unit_running": unit_running,
        "scoped_runtime_credentials_present": credentials_ready,
        "provider_iam_authorization_proven": False,
        "google_oauth_callback_registered_proven": False,
        "live_customer_consent_and_calendar_readback_proven": False,
        "production_database_rls_verified": False,
    }
    return {
        "mode": "READ_ONLY_NO_NETWORK_NO_SECRETS",
        "approved_mapping_count": approved_count,
        "gates": gates,
        "unverified": [key for key, ok in gates.items() if not ok],
        "live_customer_oauth_authorized": False,
        "pilot_revenue_verified": False,
        "config_values_disclosed": False,
        "credentials_read": False,
        "writes": False,
    }


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Redacted Calendar OAuth cloud readiness inspection")
    p.add_argument("--read-only", action="store_true", required=True)
    p.add_argument("--config", type=Path,
                   default=Path("/etc/empire/inbound-calendar-cloud-pilot.json"))
    args = p.parse_args()
    # Never render parsed configuration, IDs or file contents.
    print(json.dumps(inspect_cloud_activation(config_file=args.config),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
