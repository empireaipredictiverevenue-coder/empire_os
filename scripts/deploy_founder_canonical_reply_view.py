#!/usr/bin/env python3
"""Release *only* the read-only canonical reply view in the existing Founder API.

Dry-run by default. Actual activation requires root AND an exact approval flag.
Reuses an existing protected closer-observer credential, never EmpireDB admin or
sender login. No SQL mutation, outreach, DNS, payment action, or new worker.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path
from urllib.request import HTTPRedirectHandler, build_opener

from empire_os.empiredb_founder_reply_mailbox import EmpireDBFounderReplyMailbox

DB_ENV = Path("/etc/empiredb.env")
EXISTING_FOUNDER_ENV = (
    Path("/etc/empire_os.env"),
    Path("/etc/empire/founder-imap.env"),
)
PRIVATE_DSN_FILE = Path("/etc/empire/founder_reply_reader.dsn")
SYSTEMD_DROPIN = Path(
    "/etc/systemd/system/empire-founder-dashboard-api.service.d/"
    "30-canonical-reply-view.conf"
)
UNIT = "empire-founder-dashboard-api.service"
DROPIN_CONTENT = (
    "[Service]\n"
    "LoadCredential=founder_reply_reader_dsn:/etc/empire/founder_reply_reader.dsn\n"
    "Environment=EMPIRE_FOUNDER_MAILBOX_PROVIDER=empiredb_canonical_replies\n"
)
READINESS_URL = "http://127.0.0.1:8766/v1/founder-mailbox/readiness"
SUMMARY_URL = "http://127.0.0.1:8766/v1/founder-mailbox/summary?limit=1"


class ReleaseHeld(RuntimeError):
    pass


def _protected_dsn() -> str:
    if os.geteuid() != 0:
        raise ReleaseHeld("ROOT_ACCESS_REQUIRED")
    try:
        from dotenv import dotenv_values
        info = DB_ENV.stat()
        if info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o077:
            raise ReleaseHeld("DB_ENV_FILE_NOT_ROOT_PRIVATE")
        data = dotenv_values(DB_ENV)
        candidate = str(
            data.get("EMPIRE_CLOSER_OBSERVER_DSN")
            or data.get("EMPIRE_FOUNDER_REPLY_READER_DSN")
            or ""
        ).strip()
        if not candidate or "\n" in candidate or "\r" in candidate or len(candidate) > 4096:
            raise ReleaseHeld("DEDICATED_CLOSER_OBSERVER_LOGIN_UNAVAILABLE")
        for config in EXISTING_FOUNDER_ENV:
            if config.is_file():
                current = dotenv_values(config).get("EMPIRE_FOUNDER_MAILBOX_PROVIDER")
                if current and current.strip() != "empiredb_canonical_replies":
                    raise ReleaseHeld("CONFLICTING_FOUNDER_PROVIDER_SETTING")
        return candidate
    except ReleaseHeld:
        raise
    except Exception:
        raise ReleaseHeld("PROTECTED_CREDENTIAL_READ_UNAVAILABLE") from None


def _preflight_role(dsn: str) -> None:
    """Require exact read rights and verify both real queries before release."""
    try:
        import psycopg
        with psycopg.connect(dsn, connect_timeout=5) as con:
            with con.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                # Reject an otherwise convenient DBA/sender login even if it
                # can SET ROLE to the observer. The credential itself must
                # have no write/create authority or other role memberships.
                cur.execute(
                    """SELECT rolsuper, rolcreatedb, rolcreaterole,
                              rolreplication, rolbypassrls
                         FROM pg_catalog.pg_roles WHERE rolname=session_user"""
                )
                flags = cur.fetchone()
                if flags is None or any(flags):
                    raise ReleaseHeld("READER_LOGIN_HAS_ELEVATED_ROLE_ATTRIBUTES")
                cur.execute(
                    """SELECT EXISTS(
                         SELECT 1 FROM pg_catalog.pg_class c
                         JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                         WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
                         AND (
                           pg_catalog.has_table_privilege(session_user, c.oid, 'INSERT')
                           OR pg_catalog.has_table_privilege(session_user, c.oid, 'UPDATE')
                           OR pg_catalog.has_table_privilege(session_user, c.oid, 'DELETE')
                           OR pg_catalog.has_table_privilege(session_user, c.oid, 'TRUNCATE')
                         )
                       ),
                       pg_catalog.has_database_privilege(session_user, current_database(), 'CREATE'),
                       pg_catalog.has_schema_privilege(session_user, 'public', 'CREATE')"""
                )
                write_privs = cur.fetchone()
                if write_privs is None or any(write_privs):
                    raise ReleaseHeld("READER_LOGIN_NOT_STRICTLY_READ_ONLY")
                cur.execute(
                    """SELECT r.rolname FROM pg_catalog.pg_auth_members m
                       JOIN pg_catalog.pg_roles r ON r.oid=m.roleid
                       JOIN pg_catalog.pg_roles u ON u.oid=m.member
                       WHERE u.rolname=session_user"""
                )
                memberships = [name for (name,) in cur.fetchall()]
                if any(name != "empire_closer_observer" for name in memberships):
                    raise ReleaseHeld("READER_LOGIN_HAS_OTHER_ROLE_MEMBERSHIPS")
                cur.execute("SET LOCAL ROLE empire_closer_observer")
                cur.execute("SET LOCAL statement_timeout = '4000ms'")
                cur.execute(
                    """SELECT current_user,
                     has_table_privilege(current_user, 'public.outbound_replies', 'SELECT'),
                     has_table_privilege(current_user, 'public.outbound_intents', 'SELECT'),
                     has_table_privilege(current_user, 'public.outbound_replies', 'INSERT'),
                     has_table_privilege(current_user, 'public.outbound_replies', 'UPDATE'),
                     has_table_privilege(current_user, 'public.outbound_replies', 'DELETE'),
                     has_table_privilege(current_user, 'public.outbound_intents', 'INSERT'),
                     has_table_privilege(current_user, 'public.outbound_intents', 'UPDATE'),
                     has_table_privilege(current_user, 'public.outbound_intents', 'DELETE')"""
                )
                row = cur.fetchone()
                if row != ("empire_closer_observer", True, True,
                           False, False, False, False, False, False):
                    raise ReleaseHeld("CLOSER_ROLE_NOT_STRICTLY_READ_ONLY")
                cur.execute("ROLLBACK")
        provider = EmpireDBFounderReplyMailbox(dsn=dsn)
        provider.list_received(limit=1)
        provider.list_sent(limit=1)
    except ReleaseHeld:
        raise
    except Exception:
        raise ReleaseHeld("CLOSER_READ_ONLY_SQL_PROBE_FAILED") from None


def _write_private(path: Path, value: str, mode: int) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".empire-release-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _systemctl(action: str) -> None:
    if action not in ("daemon-reload", "restart"):
        raise ReleaseHeld("UNSUPPORTED_SERVICE_OPERATION")
    command = ["systemctl", action]
    if action == "restart":
        command.append(UNIT)
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   check=True, timeout=25)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _json_probe(url: str) -> dict:
    if url not in (READINESS_URL, SUMMARY_URL):
        raise ReleaseHeld("UNAPPROVED_RELEASE_PROBE_URL")
    try:
        with build_opener(_NoRedirect()).open(url, timeout=5) as response:
            if response.status != 200:
                raise ReleaseHeld("FOUNDER_READ_ENDPOINT_NON_200")
            data = json.loads(response.read(20000))
        return data if isinstance(data, dict) else {}
    except ReleaseHeld:
        raise
    except Exception:
        raise ReleaseHeld("FOUNDER_READ_ENDPOINT_UNAVAILABLE") from None


def activate(*, verified_dsn: str | None = None) -> dict:
    if verified_dsn is not None and os.geteuid() != 0:
        raise ReleaseHeld("ROOT_ACCESS_REQUIRED")
    if PRIVATE_DSN_FILE.exists() or SYSTEMD_DROPIN.exists():
        raise ReleaseHeld("EXISTING_REPLY_RELEASE_FILES_REQUIRE_REVIEW")
    secret = verified_dsn if verified_dsn is not None else _protected_dsn()
    if not isinstance(secret, str) or not secret.strip():
        raise ReleaseHeld("DEDICATED_CLOSER_OBSERVER_LOGIN_UNAVAILABLE")
    _preflight_role(secret)
    installed_private = installed_dropin = False
    try:
        _write_private(PRIVATE_DSN_FILE, secret, 0o600)
        installed_private = True
        _write_private(SYSTEMD_DROPIN, DROPIN_CONTENT, 0o644)
        installed_dropin = True
        _systemctl("daemon-reload")
        _systemctl("restart")
        ready = _json_probe(READINESS_URL)
        summary = _json_probe(SUMMARY_URL)
        if (ready.get("provider") != "empiredb_canonical_replies"
                or ready.get("configured") is not True
                or ready.get("execution_authority") != "none"
                or summary.get("read_only") is not True
                or summary.get("provider") != "empiredb_canonical_replies"
                or summary.get("execution_authority") != "none"
                or summary.get("suppression_evidence_complete") is not False):
            raise ReleaseHeld("LIVE_CANONICAL_REPLY_CONTRACT_UNVERIFIED")
        return {
            "status": "CANONICAL_REPLY_VIEW_ACTIVE",
            "provider": "empiredb_canonical_replies",
            "read_only": True,
            "general_gmail_inbox_connected": False,
            "send_authorized": False,
            "service_restarted": True,
            "new_workers_created": False,
        }
    except Exception:
        # Never abandon a broken dashboard; restore the original systemd unit.
        if installed_dropin:
            SYSTEMD_DROPIN.unlink(missing_ok=True)
        if installed_private:
            PRIVATE_DSN_FILE.unlink(missing_ok=True)
        try:
            _systemctl("daemon-reload")
            _systemctl("restart")
        except Exception:
            raise ReleaseHeld("ROLLBACK_NEEDS_PRIVILEGED_REPAIR") from None
        raise ReleaseHeld("CANONICAL_REPLY_RELEASE_ROLLED_BACK") from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Founder canonical reply viewer release")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approved-canonical-reply-view-only", action="store_true")
    args = parser.parse_args(argv)
    report = {
        "schema_version": "empire.founder.canonical_reply_release.v1",
        "status": "REVIEW_ONLY",
        "database_writes": False,
        "mail_sent": False,
        "dns_changed": False,
        "outbound_activated": False,
        "credentials_disclosed": False,
    }
    if not args.apply:
        print(json.dumps(report, sort_keys=True))
        return 0
    try:
        if not args.approved_canonical_reply_view_only:
            raise ReleaseHeld("EXPLICIT_BOUNDED_RELEASE_REQUIRED")
        report.update(activate())
        print(json.dumps(report, sort_keys=True))
        return 0
    except ReleaseHeld as exc:
        report["status"] = "HELD"
        report["reason"] = str(exc)
        print(json.dumps(report, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
