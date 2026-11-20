"""Read-only, no-secret Mautic 7 / existing Smart CRM production release preflight.

No Docker writes, service reload/restart, migration, customer row read, or send.
Use the canonical running CRM login; don't trust HTTP caller tenant claims.
"""
from __future__ import annotations

import json
import os
import socket
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
SERVICE = "empire-revenue-crm-pilot.service"
ENV = Path("/home/ubuntu/.config/empireos/mautic_review/private.env")
COMPOSE = ROOT / "deploy/mautic/compose.mautic7.private-nosend.yaml"
RELEASE_SQL = ROOT / "docs/integrations/sql/MAUTIC_CRM_EVENT_INBOX_PREPARED_ONLY_20261119.sql"


def _run(*command: str, timeout: int = 8) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, capture_output=True, text=True, timeout=timeout, check=False,
    )


def _safe_env() -> bool:
    try:
        s = ENV.lstat()
        if (
            not stat.S_ISREG(s.st_mode)
            or stat.S_IMODE(s.st_mode) != 0o600
            or s.st_uid != os.getuid()
        ):
            return False
        data = ENV.read_text(encoding="utf-8")
        rows = [x for x in data.splitlines() if x]
        keys = {x.partition("=")[0] for x in rows}
        return (
            len(rows) == 2
            and keys == {"EMPIRE_MAUTIC_DB_ROOT_PASSWORD", "EMPIRE_MAUTIC_DB_PASSWORD"}
            and all(len(x.partition("=")[2]) >= 48 for x in rows)
        )
    except (OSError, UnicodeError):
        return False


def _compose_valid() -> bool:
    if not _safe_env():
        return False
    try:
        result = _run(
            "docker", "compose", "--env-file", str(ENV),
            "-f", str(COMPOSE), "config", "--quiet",
            timeout=15,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _socket_listening() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 18784), timeout=1):
            return True
    except OSError:
        return False


def _db_catalog() -> dict[str, object]:
    output: dict[str, object] = {
        "canonical_empiredb_login_confirmed": False,
        "mautic_event_inbox_exists": None,
        "mautic_writer_role_exists": None,
        "mautic_tenant_login_count": None,
        "service_mautic_mode": "UNKNOWN",
        "service_mautic_source_configured": False,
    }
    try:
        proc = _run("systemctl", "show", SERVICE, "--value", "-p", "MainPID")
        pid = int(proc.stdout.strip())
        if pid <= 1:
            return output
        env = dict(
            part.split(b"=", 1)
            for part in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
            if b"=" in part
        )
        output["service_mautic_mode"] = (
            "UNSET" if not env.get(b"EMPIRE_CRM_MAUTIC_MODE")
            else "CONFIGURED"
        )
        output["service_mautic_source_configured"] = bool(
            env.get(b"EMPIRE_CRM_MAUTIC_CONFIG_FILE")
        )
        pilot_config = env.get(b"EMPIRE_CRM_PILOT_CONFIG_FILE")
        pgpassfile = env.get(b"PGPASSFILE")
        if not pilot_config or not pgpassfile:
            return output
        config = json.loads(Path(pilot_config.decode()).read_text())
        tenant_dsns = config.get("tenant_dsns")
        if not isinstance(tenant_dsns, dict) or len(tenant_dsns) != 1:
            return output
        previous = os.environ.get("PGPASSFILE")
        try:
            os.environ["PGPASSFILE"] = pgpassfile.decode()
            with psycopg.connect(next(iter(tenant_dsns.values())), connect_timeout=3) as con:
                with con.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    cur.execute("SET LOCAL statement_timeout='4000ms'")
                    cur.execute("""
                        SELECT current_database() = 'empiredb',
                          to_regclass('public.empire_crm_mautic_event_inbox') IS NOT NULL,
                          EXISTS(SELECT 1 FROM pg_roles
                            WHERE rolname='empire_mautic_crm_inbox_writer'),
                          (SELECT count(*) FROM pg_roles
                           WHERE rolname LIKE 'empire_mautic_tenant_%')
                    """)
                    db, table, role, logins = cur.fetchone()
                    output["canonical_empiredb_login_confirmed"] = bool(db)
                    output["mautic_event_inbox_exists"] = bool(table)
                    output["mautic_writer_role_exists"] = bool(role)
                    output["mautic_tenant_login_count"] = int(logins)
        finally:
            if previous is None:
                os.environ.pop("PGPASSFILE", None)
            else:
                os.environ["PGPASSFILE"] = previous
    except (OSError, ValueError, KeyError, psycopg.Error, json.JSONDecodeError):
        pass
    return output


def review() -> dict[str, object]:
    db = _db_catalog()
    service = _run("systemctl", "is-active", SERVICE).stdout.strip()
    postgres = _run("systemctl", "is-active", "postgresql@18-main.service").stdout.strip()
    try:
        docker_access = _run("docker", "ps", "--format", "{{.Names}}").returncode == 0
    except OSError:
        docker_access = False
    private = _safe_env()
    compose_ok = _compose_valid()
    port_listening = _socket_listening()
    blockers = []
    if service != "active" or postgres != "active":
        blockers.append("EXISTING_CRM_OR_POSTGRES_NOT_ACTIVE")
    if not db["canonical_empiredb_login_confirmed"]:
        blockers.append("AUTHENTICATED_CANONICAL_DB_CATALOG_UNAVAILABLE")
    if not docker_access:
        blockers.append("DOCKER_PRIVILEGED_OWNER_REQUIRED")
    if not private or not compose_ok:
        blockers.append("PRIVATE_MAUTIC_COMPOSE_OR_CREDENTIALS_INVALID")
    if not port_listening:
        blockers.append("NO_LIVE_MAUTIC_HTTP_INSTANCE")
    if db["mautic_event_inbox_exists"] is not True or db["mautic_writer_role_exists"] is not True:
        blockers.append("DBA_GUARDED_MAUTIC_ROLE_AND_INBOX_NOT_PROVISIONED")
    if db["mautic_tenant_login_count"] == 0:
        blockers.append("NO_MAUTIC_TENANT_WRITER_IDENTITY")
    if db["service_mautic_source_configured"] is not True:
        blockers.append("NO_LIVE_APPROVED_MAUTIC_SOURCE_OR_EXACT_CONTACT_BINDINGS")
    return {
        "schema_version": "empire.mautic_release_readonly_preflight.v1",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "no_database_writes": True,
        "no_service_restart": True,
        "no_outbound_send": True,
        "existing_crm_service_active": service == "active",
        "postgresql_service_active": postgres == "active",
        "private_db_secrets_owner_only": private,
        "private_compose_config_valid": compose_ok,
        "docker_daemon_accessible_to_connected_operator": docker_access,
        "private_mautic_http_listener_present": port_listening,
        "prepared_inbox_sql_present": RELEASE_SQL.is_file(),
        "database": db,
        "blockers": blockers,
        "result": "LIVE_NOT_READY" if blockers else "READINESS_PROVISIONALLY_PASS_REVIEW_REQUIRED",
    }


if __name__ == "__main__":
    print(json.dumps(review(), sort_keys=True, indent=2))
