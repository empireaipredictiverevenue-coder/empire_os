"""Single approved, root-operated V15 EmpireDB OBSERVE custody activation.

Never used by the everyday agent or Remote Commander without authorized root
execution. Pin source checksum, verify canonical DB, protect backup, create
ONLY one dedicated non-login custodian + one login, install tested SQL in one
database transaction, install root-owned service environment, issue one capture
and read back. NO mail, customer export, payment, timer, data sale or retry.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import subprocess
import sys

from empire_os.data_exchange_custody_transport import EmpireDBConstructionCustody
from empire_os.data_exchange_observation_custody import verify_custody_window

ROOT = Path("/srv/empire_os")
SQL_REL = "docs/commercial/prepared_sql/PREPARED_ONLY_data_exchange_observation_custody_20261015.sql"
SQL_HASH = "d0288b5d69e29da2759e4ba64d67f7399fd5271eb5fefb959a4986a3a2996769"
RELEASE_COMMIT = "3d7913b9"
LOGIN = "empire_data_exchange_custody_login"
CUSTODIAN = "empire_data_exchange_custodian"
APPROVAL = "--approved-data-exchange-v15-observe-only"
ENV_FILE = Path("/etc/empire/data-exchange-custody.env")
UNIT_FILE = Path("/etc/systemd/system/empire-data-exchange-custody-capture.service")
BACKUP_ROOT = Path("/var/backups/empiredb/data-exchange-custody-v15")
PGHOST = "/var/run/postgresql"
RUNUSER = "/usr/sbin/runuser"  # verified Ubuntu 26.04 path; never depend on a reduced PATH
RESULT_SCHEMA = "empire.data_exchange.production_custody_activation.v15"


class ReleaseHeld(RuntimeError):
    pass


def hold(reason: str) -> None:
    raise ReleaseHeld(reason)


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_schema() -> str:
    path = ROOT / SQL_REL
    if not path.is_file() or path.is_symlink() or checksum(path) != SQL_HASH:
        hold("APPROVED_SQL_HASH_MISMATCH")
    current = subprocess.run(
        ["git", "-C", str(ROOT), "hash-object", str(path)],
        capture_output=True, text=True, timeout=8, check=True,
    ).stdout.strip()
    approved = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", f"{RELEASE_COMMIT}:{SQL_REL}"],
        capture_output=True, text=True, timeout=8, check=True,
    ).stdout.strip()
    if current != approved:
        hold("RELEASE_COMMIT_SQL_DRIFT")
    return path.read_text(encoding="utf-8")


def transaction_sql(template: str, password: str) -> str:
    """One atomic SQL transaction: both roles, membership and tested DDL.

    Strip only the top-level BEGIN/COMMIT from the reviewed migration.
    Preserve all reviewed SQL in between unchanged. No dynamic table names.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{40,128}", password):
        hold("RUNTIME_PASSWORD_SHAPE_INVALID")
    lines = template.splitlines()
    boundaries = [(i, line.strip()) for i, line in enumerate(lines)
                  if line.strip() in {"BEGIN;", "COMMIT;"}]
    if (len(boundaries) != 2 or boundaries[0][1] != "BEGIN;"
        or boundaries[1][1] != "COMMIT;"
        or boundaries[0][0] >= boundaries[1][0]):
        hold("REVIEWED_MIGRATION_TRANSACTION_SHAPE_INVALID")
    core = "\n".join(lines[boundaries[0][0] + 1:boundaries[1][0]])
    return (
        "BEGIN;\n"
        "SET LOCAL password_encryption = 'scram-sha-256';\n"
        "CREATE ROLE empire_data_exchange_custodian "
        "NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
        "NOREPLICATION NOBYPASSRLS;\n"
        f"CREATE ROLE {LOGIN} LOGIN PASSWORD '{password}' "
        "NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
        "NOREPLICATION NOBYPASSRLS;\n"
        f"GRANT {CUSTODIAN} TO {LOGIN} WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;\n"
        + core + "\nCOMMIT;\n"
    )


def postgresql(query: str | None = None, *, stdin_sql: str | None = None,
               silent: bool = False) -> str:
    cmd = [RUNUSER, "-u", "postgres", "--", "/usr/bin/psql",
           "-X", "-w", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-d", "empiredb"]
    if query is not None:
        cmd.extend(["-c", query])
    env = {"PATH": "/usr/bin:/bin", "PGHOST": PGHOST, "PGPORT": "5432"}
    p = subprocess.run(cmd, input=stdin_sql, text=True, capture_output=True,
                       timeout=60, env=env)
    if p.returncode != 0:
        # Database errors can echo SQL with PASSWORD; never display stderr.
        hold("POSTGRESQL_ADMIN_ACTION_FAILED_PRIVATE_DIAGNOSTICS_ONLY")
    return "" if silent else p.stdout.strip()


def application_same_database() -> bool:
    """Verify configured application DSN targets this exact PG instance.

    Env output contains only database + postmaster epoch, never DSN.
    """
    code = (
        "import os,psycopg; d=os.getenv('EMPIREDB_DSN'); "
        "c=psycopg.connect(d,connect_timeout=5); "
        "q=c.execute(\"SELECT current_database()||'|'||"
        "extract(epoch from pg_postmaster_start_time())::bigint\"); "
        "print(q.fetchone()[0]); c.close()"
    )
    cmd = "set -a; source /etc/empiredb.env; exec /srv/empire_os/.venv/bin/python -c " + shlex.quote(code)
    try:
        p = subprocess.run(["bash", "-c", cmd], capture_output=True,
                           text=True, timeout=15)
        if p.returncode != 0:
            return False
        app = p.stdout.strip()
        admin = postgresql(
            "SELECT current_database()||'|'||"
            "extract(epoch from pg_postmaster_start_time())::bigint"
        )
        return bool(app) and app == admin
    except Exception:
        return False


def backup_canonical() -> Path:
    backup = BACKUP_ROOT / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if BACKUP_ROOT.is_symlink() or backup.exists():
        hold("BACKUP_PATH_CONFLICT")
    BACKUP_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(BACKUP_ROOT, 0o700)
    db_bytes = postgresql("SELECT pg_database_size('empiredb')")
    if not db_bytes.isdigit():
        hold("DATABASE_SIZE_UNAVAILABLE")
    free = shutil.disk_usage(BACKUP_ROOT).free
    if free < int(db_bytes) * 2 + 512 * 1024 * 1024:
        hold("INSUFFICIENT_DISK_FOR_BACKUP")
    backup.mkdir(mode=0o700)
    for filename, args in (
        ("empiredb-before-v15.dump",
         [RUNUSER, "-u", "postgres", "--", "/usr/bin/pg_dump", "-w", "-Fc", "-d", "empiredb"]),
        ("postgres-globals-before-v15.sql",
         [RUNUSER, "-u", "postgres", "--", "/usr/bin/pg_dumpall", "-w", "--globals-only"]),
    ):
        target = backup / filename
        with target.open("xb") as fd:
            r = subprocess.run(args, stdout=fd, stderr=subprocess.DEVNULL,
                               timeout=600,
                               env={"PATH":"/usr/bin:/bin", "PGHOST":PGHOST, "PGPORT":"5432"})
        os.chmod(target, 0o600)
        if r.returncode != 0 or target.stat().st_size == 0:
            hold("CANONICAL_BACKUP_UNVERIFIED")
    archive = backup / "empiredb-before-v15.dump"
    listing = subprocess.run(["pg_restore", "--list", str(archive)],
                             capture_output=True, text=True, timeout=60)
    if listing.returncode != 0:
        hold("BACKUP_ARCHIVE_CANNOT_BE_READ")
    (backup / "backup-sha256.json").write_text(json.dumps({
        "db_dump": checksum(archive),
        "role_globals": checksum(backup / "postgres-globals-before-v15.sql"),
        "source_sql_sha256": SQL_HASH,
    }, sort_keys=True), encoding="utf-8")
    os.chmod(backup / "backup-sha256.json", 0o600)
    return backup


def install_env_and_service(password: str) -> str:
    from psycopg.conninfo import make_conninfo
    conninfo = make_conninfo(
        host="127.0.0.1", port=5432, dbname="empiredb", user=LOGIN,
        password=password, connect_timeout=5,
    )
    envtext = (
        "EMPIRE_DATA_EXCHANGE_CUSTODIAN_DSN=" + shlex.quote(conninfo) + "\n"
        "EMPIRE_DATA_EXCHANGE_CUSTODY_RELEASE=FOUNDER_APPROVED_OBSERVATION_APPEND_ONLY\n"
    )
    if ENV_FILE.exists() or ENV_FILE.is_symlink() or UNIT_FILE.exists() or UNIT_FILE.is_symlink():
        hold("CUSTODY_ENV_OR_UNIT_ALREADY_EXISTS")
    fd = os.open(ENV_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(envtext)
    os.chmod(ENV_FILE, 0o600)
    unit = f"""[Unit]
Description=Empire Data Exchange V15 - one approved public-source custody capture
After=postgresql@18-main.service
Requires=postgresql@18-main.service

[Service]
Type=oneshot
User=ubuntu
Group=ubuntu
WorkingDirectory=/srv/empire_os
EnvironmentFile={ENV_FILE}
ExecStart=/srv/empire_os/.venv/bin/python -m scripts.operate_data_exchange_observation_custody --append --approved-custody-only
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
PrivateDevices=true
CapabilityBoundingSet=
RestrictSUIDSGID=true
LockPersonality=true
RestrictNamespaces=true
"""
    fd2 = os.open(UNIT_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd2, "w", encoding="utf-8") as out:
        out.write(unit)
    subprocess.run(["systemctl", "daemon-reload"], check=True, timeout=25,
                   stdout=subprocess.DEVNULL)
    return conninfo


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true")
    p.add_argument(APPROVAL, action="store_true")
    args = p.parse_args(argv)
    report = {"schema_version":RESULT_SCHEMA, "status":"HOLD",
              "scope":"OFFICIAL_SOURCE_OBSERVATION_CUSTODY_ONLY",
              "outbound_enabled":False,"customer_delivery_enabled":False,
              "payment_execution":False}
    phase = "BEFORE_RELEASE_CHECKS"
    try:
        if not args.apply or not getattr(args, APPROVAL.lstrip("-").replace("-","_")):
            hold("EXACT_FOUNDER_APPROVED_APPLY_FLAGS_REQUIRED")
        if os.geteuid() != 0:
            hold("AUTHORISED_ROOT_OPERATOR_REQUIRED")
        if Path.cwd().resolve() != ROOT.resolve():
            hold("CANONICAL_REPOSITORY_REQUIRED")
        phase = "VERIFY_RELEASE_COMMIT_AND_SQL"
        template = checked_schema()
        for name in ("psql","pg_dump","pg_dumpall","pg_restore","systemctl"):
            if shutil.which(name) is None:
                hold("REQUIRED_FIRST_PARTY_DATABASE_TOOL_MISSING")
        if not Path(RUNUSER).is_file() or not os.access(RUNUSER, os.X_OK):
            hold("VERIFIED_RUNUSER_EXECUTABLE_MISSING")
        if not Path("/etc/empiredb.env").is_file():
            hold("CANONICAL_DATABASE_CONFIGURATION_MISSING")
        if ENV_FILE.exists() or UNIT_FILE.exists():
            hold("POSSIBLE_PRIOR_ACTIVATION_RECONCILE_NO_RETRY")
        phase = "ACQUIRE_RELEASE_LOCK"
        with Path("/run/lock/empire-data-exchange-v15.lock").open("a+") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                hold("ANOTHER_RELEASE_IN_PROGRESS")
            phase = "VERIFY_POSTGRES_IDENTITY"
            identity = postgresql(
                "SELECT current_database()||'|'||current_setting('data_directory')"
                "||'|'||pg_is_in_recovery()"
            )
            if identity != "empiredb|/var/lib/postgresql/18/main|f":
                hold("CANONICAL_DATABASE_IDENTITY_UNVERIFIED")
            phase = "VERIFY_APP_DATABASE_MATCH"
            if not application_same_database():
                hold("APPLICATION_DATABASE_INSTANCE_MISMATCH")
            phase = "CHECK_EXISTING_CUSTODY_SCHEMA_AND_ROLES"
            absent = postgresql(
                "SELECT (to_regclass('public.empire_data_exchange_observations') IS NULL)::int"
                "||'|'||(SELECT count(*) FROM pg_roles WHERE rolname IN "
                "('empire_data_exchange_custodian','empire_data_exchange_custody_login'))"
            )
            if absent != "1|0":
                hold("CUSTODY_SCHEMA_OR_ROLE_ALREADY_EXISTS_RECONCILE")
            password = secrets.token_urlsafe(48)
            sql = transaction_sql(template, password)
            phase = "BACKUP_CANONICAL_DB"
            backup = backup_canonical()
            try:
                phase = "APPLY_SCHEMA_TRANSACTION"
                postgresql(stdin_sql=sql, silent=True)
            except ReleaseHeld:
                report["status"] = "HOLD_SCHEMA_TRANSACTION_FAILED"
                report["backup_recorded"] = True
                raise
            phase = "VERIFY_POSTCOMMIT_RLS_AND_TRIGGERS"
            contract = postgresql(
                "SELECT (relrowsecurity AND relforcerowsecurity)::int"
                "||'|'||(SELECT count(*) FROM pg_trigger t "
                "WHERE t.tgrelid='public.empire_data_exchange_observations'::regclass "
                "AND NOT t.tgisinternal)"
                " FROM pg_class WHERE oid='public.empire_data_exchange_observations'::regclass"
            )
            if contract != "1|3":
                hold("POSTCOMMIT_CUSTODY_RLS_OR_TRIGGER_CHECK_FAILED_NO_RETRY")
            phase = "INSTALL_ENV_AND_ONESHOT_UNIT"
            conninfo = install_env_and_service(password)
            import psycopg
            with psycopg.connect(conninfo, connect_timeout=5) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute("SET LOCAL ROLE empire_data_exchange_custodian")
                    cursor.execute("SELECT count(*) FROM public.empire_data_exchange_observations")
                    if cursor.fetchone() != (0,):
                        hold("UNEXPECTED_PRE_EXISTING_CUSTODY_ROWS")
            # Explicitly one run, with no timer or enable command.
            phase = "RUN_FIRST_OFFICIAL_SOURCE_CAPTURE"
            started = subprocess.run(
                ["systemctl","start","empire-data-exchange-custody-capture.service"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45,
            )
            if started.returncode != 0:
                hold("SCHEMA_INSTALLED_BUT_INITIAL_CAPTURE_HELD_NO_RETRY")
            phase = "VERIFY_CANONICAL_READBACK"
            rows = EmpireDBConstructionCustody(conninfo).read_window()
            if (len(rows) != 1 or rows[0]["sequence"] != 0
                or rows[0]["schema_version"] != "empire.data_exchange.observation_custody.v15"
                or len(rows[0]["snapshot_json"].get("records", [])) != 3):
                hold("SCHEMA_INSTALLED_BUT_CANONICAL_READBACK_UNVERIFIED")
            integrity = verify_custody_window(rows)
            if (integrity["first_sequence"] != 0
                or integrity["last_sequence"] != 0
                or integrity["head_chain_sha256"] != rows[0]["chain_sha256"]):
                hold("CANONICAL_HASH_CHAIN_READBACK_UNVERIFIED")
            report.update(
                status="PRODUCTION_OBSERVE_CUSTODY_ACTIVE",
                canonical_rows=1,
                first_sequence=0,
                canonical_head_sha256=rows[0]["chain_sha256"],
                customer_delivery_enabled=False,
                outbound_enabled=False,
                payment_execution=False,
                timer_installed=False,
                external_anchor_verified=False,
                independent_field_rights_review=False,
                actual_revenue_verified=False,
                backup_verified=True,
                released_sql_sha256=SQL_HASH,
            )
            receipt_file = backup / "v15-production-receipt.json"
            fd = os.open(receipt_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                out.write(json.dumps(report, sort_keys=True) + "\\n")
    except ReleaseHeld as exc:
        report.setdefault("reason_code", str(exc))
    except Exception as exc:
        report["reason_code"] = "UNEXPECTED_RELEASE_EXCEPTION_STOP_NO_RETRY"
        report["failed_phase"] = phase
        report["exception_type"] = type(exc).__name__
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PRODUCTION_OBSERVE_CUSTODY_ACTIVE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
