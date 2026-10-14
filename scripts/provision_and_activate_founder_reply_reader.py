#!/usr/bin/env python3
"""Provision one isolated EmpireDB reply-reader login and activate Founder view.

This performs one narrowly-approved database role creation and one existing
Founder API read-only view activation. Dry-run default. No mail/DNS actions.
Credentials are generated in memory and never included in command arguments,
stdout, exception messages, logs, or source files.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import stat
import subprocess
from pathlib import Path

from dotenv import dotenv_values
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from scripts import deploy_founder_canonical_reply_view as release

LOGIN = "empire_founder_reply_reader_login"
CAPABILITY = "empire_closer_observer"
POSTGRES_DB = "empiredb"
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "/var/run/postgresql"}
PROVISION_ACTION = "CREATE_DEDICATED_READ_ONLY_LOGIN_AND_ACTIVATE_FOUNDER_REPLY_VIEW"


class ProvisionHeld(RuntimeError):
    pass


def _canonical_base_conninfo() -> dict[str, str]:
    """Read protected canonical DB config only as root, no secret output."""
    if os.geteuid() != 0:
        raise ProvisionHeld("ROOT_ACCESS_REQUIRED")
    path = release.DB_ENV
    try:
        attrs = path.stat()
        if attrs.st_uid != 0 or stat.S_IMODE(attrs.st_mode) & 0o077:
            raise ProvisionHeld("CANONICAL_DB_ENV_NOT_ROOT_PRIVATE")
        conf = dotenv_values(path)
        raw = str(conf.get("EMPIREDB_DSN") or "").strip()
        if not raw:
            raise ProvisionHeld("CANONICAL_EMPIREDB_DSN_REQUIRED")
        parsed = conninfo_to_dict(raw)
        if (parsed.get("dbname") != POSTGRES_DB
                or str(parsed.get("host") or "") not in ALLOWED_HOSTS
                or str(parsed.get("port") or "5432") != "5432"):
            raise ProvisionHeld("CANONICAL_LOCAL_EMPIREDB_ENDPOINT_REQUIRED")
        return parsed
    except ProvisionHeld:
        raise
    except Exception:
        raise ProvisionHeld("PROTECTED_CANONICAL_DSN_UNAVAILABLE") from None


def _new_reader_dsn(base: dict[str, str], password: str) -> str:
    if not password or any(ch not in "0123456789abcdef" for ch in password):
        raise ProvisionHeld("UNSAFE_READER_SECRET")
    safe = {k: v for k, v in base.items()
            if k not in ("user", "password", "application_name", "options",
                         "service", "passfile", "target_session_attrs")}
    return make_conninfo(
        **safe,
        user=LOGIN, password=password, application_name=LOGIN,
        connect_timeout="5",
    )


def _pg_sql(script: str) -> None:
    """Execute fixed, bounded SQL on the local DB as postgres; never echo SQL."""
    try:
        outcome = subprocess.run(
            ["runuser", "-u", "postgres", "--",
             "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1",
             "-d", POSTGRES_DB],
            input=script,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=25,
        )
        if outcome.returncode != 0:
            raise ProvisionHeld("DEDICATED_READER_ROLE_SQL_FAILED")
    except ProvisionHeld:
        raise
    except Exception:
        raise ProvisionHeld("LOCAL_POSTGRES_PROVISION_UNAVAILABLE") from None


def _create_login(password: str) -> None:
    """Fail on an existing role; never overwrite an established login."""
    if not password or any(ch not in "0123456789abcdef" for ch in password):
        raise ProvisionHeld("UNSAFE_READER_SECRET")
    sql = f"""BEGIN;
DO $verify$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='{LOGIN}') THEN
    RAISE EXCEPTION 'reserved reader login already exists';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='{CAPABILITY}' AND rolcanlogin IS FALSE
  ) THEN
    RAISE EXCEPTION 'expected NOLOGIN read capability unavailable';
  END IF;
END $verify$;
CREATE ROLE {LOGIN} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS PASSWORD '{password}';
GRANT {CAPABILITY} TO {LOGIN} WITH INHERIT FALSE, SET TRUE;
GRANT CONNECT ON DATABASE {POSTGRES_DB} TO {LOGIN};
ALTER ROLE {LOGIN} SET statement_timeout = '5s';
COMMIT;
"""
    _pg_sql(sql)


def _revoke_new_login() -> None:
    """No-op if the role does not exist. Used only after safe release rollback."""
    _pg_sql(f"""BEGIN;
REVOKE CONNECT ON DATABASE {POSTGRES_DB} FROM {LOGIN};
REVOKE {CAPABILITY} FROM {LOGIN};
DROP ROLE IF EXISTS {LOGIN};
COMMIT;
""")


def _check_existing_provider_selection() -> None:
    """Reject a conflicting explicit mailbox mode before creating a login."""
    if os.geteuid() != 0:
        raise ProvisionHeld("ROOT_ACCESS_REQUIRED")
    try:
        for path in release.EXISTING_FOUNDER_ENV:
            if path.is_symlink():
                raise ProvisionHeld("UNSAFE_EXISTING_FOUNDER_ENV_SYMLINK")
            if path.is_file():
                config = dotenv_values(path)
                selected = str(config.get("EMPIRE_FOUNDER_MAILBOX_PROVIDER") or "").strip()
                if selected and selected != "empiredb_canonical_replies":
                    raise ProvisionHeld("CONFLICTING_FOUNDER_PROVIDER_SETTING")
    except ProvisionHeld:
        raise
    except Exception:
        raise ProvisionHeld("EXISTING_FOUNDER_ENV_CHECK_FAILED") from None


def provision_and_activate() -> dict[str, object]:
    if os.geteuid() != 0:
        raise ProvisionHeld("ROOT_ACCESS_REQUIRED")
    if (release.PRIVATE_DSN_FILE.exists() or release.PRIVATE_DSN_FILE.is_symlink()
            or release.SYSTEMD_DROPIN.exists() or release.SYSTEMD_DROPIN.is_symlink()):
        raise ProvisionHeld("EXISTING_FOUNDER_REPLY_RELEASE_REQUIRES_REVIEW")
    if release._json_probe(release.READINESS_URL).get("provider") != "owned_imap":
        raise ProvisionHeld("FOUNDER_API_NOT_ON_EXPECTED_BASELINE")
    _check_existing_provider_selection()
    base = _canonical_base_conninfo()
    password = secrets.token_hex(32)
    reader_dsn = _new_reader_dsn(base, password)
    created = False
    try:
        _create_login(password)
        created = True
        # The existing release verifies session-user privilege flags,
        # all table write rights, role membership, cap-role SELECT rights,
        # and real inbound/outbound SELECT queries before restart.
        proof = release.activate(verified_dsn=reader_dsn)
        if proof.get("status") != "CANONICAL_REPLY_VIEW_ACTIVE":
            raise ProvisionHeld("READ_ONLY_VIEW_NOT_VERIFIED")
        return {
            "status": "CANONICAL_REPLY_VIEW_ACTIVE",
            "dedicated_login_created": True,
            "login": LOGIN,
            "capability": CAPABILITY,
            "login_is_write_capable": False,
            "founder_service_restarted": True,
            "email_sent": False,
            "dns_changed": False,
            "outbound_enabled": False,
            "private_credential_installed": True,
            "unrelated_services_restarted": False,
        }
    except Exception as exc:
        # The existing release always removes its files and restores the unit
        # on a failed readback. Never disable a login still possibly in use.
        rollback_complete = (not release.PRIVATE_DSN_FILE.exists()
                             and not release.SYSTEMD_DROPIN.exists())
        if created and rollback_complete:
            try:
                _revoke_new_login()
            except Exception:
                raise ProvisionHeld(
                    "CREDENTIAL_CLEANUP_REQUIRES_PRIVILEGED_REVIEW"
                ) from None
        if created and not rollback_complete:
            raise ProvisionHeld(
                "READER_RELEASE_NEEDS_PRIVILEGED_REPAIR"
            ) from None
        if isinstance(exc, (release.ReleaseHeld, ProvisionHeld)):
            raise ProvisionHeld(str(exc)) from None
        raise ProvisionHeld("DEDICATED_READER_RELEASE_FAILED") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-time dedicated Founder reply reader")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approved-dedicated-reader-and-reply-view-only",
                        action="store_true")
    args = parser.parse_args(argv)
    response: dict[str, object] = {
        "schema_version": "empire.founder.dedicated_reply_reader_release.v1",
        "status": "REVIEW_ONLY",
        "requested_scope": PROVISION_ACTION,
        "database_role_created": False,
        "mail_sent": False,
        "outbound_enabled": False,
        "dns_changed": False,
        "secrets_printed": False,
    }
    if not args.apply:
        print(json.dumps(response, sort_keys=True))
        return 0
    try:
        if not args.approved_dedicated_reader_and_reply_view_only:
            raise ProvisionHeld("EXPLICIT_DEDICATED_LOGIN_APPROVAL_REQUIRED")
        result = provision_and_activate()
        response.update(result)
        response["database_role_created"] = True
        print(json.dumps(response, sort_keys=True))
        return 0
    except ProvisionHeld as exc:
        response["status"] = "HELD"
        response["reason"] = str(exc)
        print(json.dumps(response, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
