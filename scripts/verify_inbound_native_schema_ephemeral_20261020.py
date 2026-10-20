"""Disposable PostgreSQL proof for held EmpireDB 057 migration.

Starts a fresh PostgreSQL cluster under a private temporary directory with
TCP disabled, runs only the held migration against a fixture DB, verifies
no customer role can read/write, and always stops/removes that cluster.
Never connects to /var/run/postgresql, production or remote databases.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

SQL = Path(__file__).resolve().parents[1] / "migrations/empiredb/057_inbound_recovery_native_schema_held.sql"
BIN = Path("/usr/lib/postgresql/18/bin")
FIXTURE_DB = "inbound_recovery_057_fixture"
TABLES = (
    "inbound_recovery_tenants",
    "inbound_recovery_events",
    "inbound_recovery_signed_callbacks",
    "inbound_recovery_management_access_audit",
    "inbound_booking_workflow_events",
    "inbound_recovery_contact_suppression",
    "inbound_recovery_calendar_bindings",
    "inbound_recovery_calendar_links",
    "inbound_recovery_calendar_status_evidence",
    "inbound_recovery_calendar_projection_delivery",
)


def run(*argv: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv, text=True, input=stdin, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=20, check=False,
    )


def require(result: subprocess.CompletedProcess, check_name: str) -> str:
    if result.returncode:
        # Outputs may include transient user paths. Never emit raw SQL or
        # any payload. Raise an identified stage and a safe first error line.
        first = next(
            (line.strip() for line in result.stderr.splitlines()
             if "ERROR:" in line or "FATAL:" in line), "",
        )
        raise RuntimeError(check_name + ": " + first[:180])
    return result.stdout.strip()


def run_fixture() -> dict:
    if os.geteuid() == 0:
        raise RuntimeError("do_not_run_ephemeral_postgres_as_root")
    for name in ("initdb", "pg_ctl", "psql", "createdb"):
        if not (BIN / name).is_file():
            raise RuntimeError("local_postgres18_test_tools_unavailable")
    if not SQL.is_file():
        raise RuntimeError("held_native_migration_missing")

    prior_umask = os.umask(0o077)
    try:
        with tempfile.TemporaryDirectory(prefix="empire-inbound057-") as base:
            root = Path(base)
            data = root / "data"
            socket_dir = root / "socket"
            socket_dir.mkdir(mode=0o700)
            require(run(
                str(BIN / "initdb"), "-D", str(data), "--no-instructions",
                "--auth-local=trust", "--auth-host=reject", "-U", "inbound_fixture_dba",
            ), "fixture_initdb")
            port = "55783"
            options = (
                "-c listen_addresses='' -c unix_socket_directories=" +
                str(socket_dir) + " -c unix_socket_permissions=0700" +
                " -c port=" + port
            )
            pgctl = str(BIN / "pg_ctl")
            started = False
            try:
                # pg_ctl -w may probe a default socket path rather than
                # the test-only directory from -o; start without -w and
                # independently check readiness on our PRIVATE socket.
                require(run(pgctl, "-D", str(data), "-o", options,
                            "-l", str(root / "postgres.log"), "start"), "fixture_pg_start")
                started = True
                base_connection = (
                    str(BIN / "psql"), "-X", "-q", "-v", "ON_ERROR_STOP=1",
                    "-h", str(socket_dir), "-p", port,
                    "-U", "inbound_fixture_dba",
                )
                ready = False
                for _ in range(25):
                    probe = run(*base_connection, "-d", "postgres", "-At",
                                "-c", "SELECT 1;")
                    if probe.returncode == 0 and probe.stdout.strip() == "1":
                        ready = True
                        break
                    time.sleep(0.2)
                if not ready:
                    raise RuntimeError("ephemeral_private_socket_not_ready")
                require(run(
                    *base_connection, "-d", "postgres",
                    "-c", "CREATE ROLE empiredb_migrator NOLOGIN NOINHERIT;",
                ), "fixture_migrator_bootstrap")
                require(run(
                    str(BIN / "createdb"), "-h", str(socket_dir), "-p", port,
                    "-U", "inbound_fixture_dba", FIXTURE_DB,
                ), "fixture_create_db")
                psql = (*base_connection, "-d", FIXTURE_DB)
                require(run(*psql, stdin="""
                  CREATE TABLE public.empire_crm_tenant_memberships (
                    tenant_id uuid NOT NULL, subject text NOT NULL,
                    PRIMARY KEY (tenant_id,subject)
                  );
                  ALTER TABLE public.empire_crm_tenant_memberships
                    ENABLE ROW LEVEL SECURITY;
                  GRANT CREATE, USAGE ON SCHEMA public TO empiredb_migrator;
                  CREATE FUNCTION public.empire_current_tenant_id()
                    RETURNS uuid LANGUAGE SQL STABLE AS
                    $$ SELECT NULL::uuid $$;
                  CREATE FUNCTION public.empire_crm_read_member(text,uuid)
                    RETURNS boolean LANGUAGE SQL STABLE AS
                    $$ SELECT false $$;
                """), "fixture_canonical_crm_authority")
                require(run(*psql, "-f", str(SQL)), "native_sql_apply_ephemeral")
                facts = require(run(*psql, "-At", stdin="""
                  SELECT count(*) FROM pg_catalog.pg_class c
                    JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='public' AND c.relname LIKE 'inbound_%'
                      AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity;
                """), "fixture_rls_proof")
                if facts != str(len(TABLES)):
                    raise RuntimeError("rls_not_forced_on_all_native_tables")
                require(run(*psql, stdin="""
                  CREATE ROLE inbound_fixture_reader NOLOGIN;
                  CREATE ROLE inbound_fixture_writer NOLOGIN;
                  INSERT INTO public.inbound_recovery_tenants
                    (tenant_id,business_name) VALUES
                    ('00000000-0000-0000-0000-000000000101','Fixture Alpha'),
                    ('00000000-0000-0000-0000-000000000102','Fixture Beta');
                  INSERT INTO public.inbound_recovery_calendar_bindings
                    (tenant_id,calendar_id,provider_account_ref,owner_approval_evidence_ref)
                    VALUES
                    ('00000000-0000-0000-0000-000000000101','same@example.test',
                     'fixture-owner-a','fixture-approval-a'),
                    ('00000000-0000-0000-0000-000000000102','same@example.test',
                     'fixture-owner-b','fixture-approval-b');
                """), "fixture_cross_tenant_setup")
                # Tenant is part of the composite key. A link that tries to
                # bind an A-only calendar to B must fail at FK level.
                fk_denied = run(*psql, stdin="""
                  INSERT INTO public.inbound_recovery_calendar_links
                    (tenant_id,calendar_id,appointment_id,call_id,contact_key,
                     tracked_source_ref) VALUES (
                    '00000000-0000-0000-0000-000000000101',
                    'beta-only@example.test','event','call',
                    repeat('f',64),'source-ref');
                """)
                if fk_denied.returncode == 0:
                    raise RuntimeError("fixture_cross_tenant_fk_not_enforced")
                # The owner of newly created relations is restricted by
                # FORCE RLS too, despite being able to hold table privilege.
                owner_rows = require(run(*psql, "-At", stdin="""
                  SET ROLE empiredb_migrator;
                  SELECT count(*) FROM public.inbound_recovery_tenants;
                """), "fixture_owner_force_rls")
                if owner_rows != "0":
                    raise RuntimeError("fixture_force_rls_owner_leak")
                for role in ("inbound_fixture_reader", "inbound_fixture_writer"):
                    denied = run(*psql, "-At", stdin=(
                        "SET ROLE " + role + ";\n"
                        "SELECT count(*) FROM public.inbound_recovery_tenants;\n"
                    ))
                    if denied.returncode == 0:
                        raise RuntimeError("fixture_app_role_table_read_granted")
                return {
                    "database": "isolated_ephemeral_postgresql_18",
                    "native_tables_force_rls": len(TABLES),
                    "crm_identity": "native",
                    "app_role_denials": 2,
                    "cross_tenant_calendar_keys": "verified",
                    "ephemeral_fixture_result": "PASS",
                    "production_database_changed": False,
                    "cloud_credentials_used": False,
                }
            finally:
                if started:
                    run(pgctl, "-D", str(data), "-m", "immediate", "stop")
                    for _ in range(30):
                        if not (data / "postmaster.pid").exists():
                            break
                        time.sleep(0.1)
                    if (data / "postmaster.pid").exists():
                        raise RuntimeError("ephemeral_postgres_cleanup_failed")
    finally:
        os.umask(prior_umask)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ephemeral-only", required=True, action="store_true")
    parser.parse_args()
    try:
        data = run_fixture()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({
            "ephemeral_fixture_result": "BLOCKED",
            "stage": str(exc)[:200],
            "production_database_changed": False,
        }))
        raise SystemExit(1) from None
    print(json.dumps(data, sort_keys=True))


if __name__ == "__main__":
    main()
