"""Real PostgreSQL 18 V15 custody integration gauntlet, isolated/unprivileged.

Creates one transient PG data directory and private UNIX socket with TCP
disabled. Applies PREPARED SQL to a fixture database only; verifies custodian
role, RLS, append, readback, duplicate/noop and mutation barriers, then stops
and deletes the ephemeral cluster. It does not connect to production.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import pwd
import subprocess

import psycopg

from empire_os.data_exchange_construction import build_construction_preview
from empire_os.data_exchange_custody_transport import EmpireDBConstructionCustody
from empire_os.data_exchange_observation_custody import verify_custody_window

NOW = datetime.now(timezone.utc)


def snapshot(*, days_ago: int, status: str) -> dict:
    when = NOW - timedelta(days=days_ago)
    return build_construction_preview([{
        "record_id": "1739547", "source_id": "gb_planning_data",
        "dataset_id": "brownfield-land", "region": "north_west_england",
        "record_type": "brownfield_land",
        "source_url": "https://www.planning.data.gov.uk/entity/1739547",
        "source_observed_at": when.isoformat(),
        "planning_permission_status": status,
        "site_area_hectares": "0.125127",
        "source_entry_date": "2024-11-29",
    }], observed_at=when)


def first() -> dict:
    return snapshot(days_ago=2, status="non-permissioned")


def second() -> dict:
    return snapshot(days_ago=1, status="permissioned")

BIN = Path("/usr/lib/postgresql/18/bin")
ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "docs/commercial/prepared_sql/PREPARED_ONLY_data_exchange_observation_custody_20261015.sql"


def _run(*cmd: str) -> None:
    subprocess.run(list(cmd), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=40)


def _expect_db_denial(connection: str, statement: str, *, like: str | None = None,
                      as_custodian: bool = False) -> None:
    try:
        with psycopg.connect(connection, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                if as_custodian:
                    cur.execute("SET LOCAL ROLE empire_data_exchange_custodian")
                cur.execute(statement)
    except psycopg.Error as exc:
        if like is not None and like not in str(exc):
            raise AssertionError("unexpected SQL rejection class: " + str(exc.sqlstate)) from None
        if exc.sqlstate not in ("23502", "23514", "42501", "P0001", "22P02"):
            raise AssertionError("unexpected SQLSTATE " + str(exc.sqlstate)) from None
    else:
        raise AssertionError("operation bypassed database protection")


def main() -> int:
    if os.geteuid() == 0:
        raise ValueError("fixture PostgreSQL MUST NOT run as root")
    if not all((BIN / item).is_file() for item in ("initdb", "pg_ctl", "postgres")):
        raise ValueError("PostgreSQL 18 fixture binaries missing")
    result = {
        "schema_version":"empire.data_exchange.isolated_postgres_gauntlet.v15",
        "mode":"DISPOSABLE_POSTGRES_FIXTURE",
        "used_production_database":False,
        "network_tcp_enabled":False,
        "production_writes":False,
        "customer_delivery_enabled":False,
        "external_anchor_verified":False,
        "migration_applied_to_production":False,
    }
    with TemporaryDirectory(prefix="empire_de_pg_fixture_") as root:
        basedir = Path(root)
        cluster = basedir / "pgdata"
        sockets = basedir / "socket"
        sockets.mkdir(mode=0o700)
        log = basedir / "pg.log"
        _run(str(BIN/"initdb"), "-D", str(cluster), "-A", "trust", "--no-instructions")
        port = 55439
        options = f"-k {sockets} -c listen_addresses='' -p {port} -c unix_socket_permissions=0700"
        _run(str(BIN/"pg_ctl"), "-D", str(cluster), "-l", str(log), "-o", options, "-w", "start")
        try:
            admin_user = pwd.getpwuid(os.getuid()).pw_name
            admin_dsn = f"host={sockets} port={port} dbname=postgres user={admin_user}"
            with psycopg.connect(admin_dsn, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute("CREATE ROLE empiredb_migrator NOLOGIN NOINHERIT")
                    cur.execute("CREATE ROLE empire_data_exchange_custodian NOLOGIN NOINHERIT")
                    cur.execute("CREATE ROLE custody_fixture_login LOGIN NOINHERIT")
                    cur.execute("GRANT empire_data_exchange_custodian TO custody_fixture_login")
                    cur.execute("CREATE DATABASE data_exchange_custody_fixture")
            fixture_admin = f"host={sockets} port={port} dbname=data_exchange_custody_fixture user={admin_user}"
            fixture_writer = f"host={sockets} port={port} dbname=data_exchange_custody_fixture user=custody_fixture_login"
            with psycopg.connect(fixture_admin) as conn:
                with conn.cursor() as cur:
                    cur.execute("GRANT USAGE, CREATE ON SCHEMA public TO empiredb_migrator")
                conn.commit()
            sql = MIGRATION.read_text(encoding="utf-8")
            with psycopg.connect(fixture_admin) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
            result["postgres_schema_applied_in_fixture"] = True
            store = EmpireDBConstructionCustody(fixture_writer)
            first_receipt = store.append_once(first(), now=NOW)
            assert first_receipt["mode"] == "CANONICAL_APPEND_COMMITTED"
            duplicate = store.append_once(first(), now=NOW)
            assert duplicate["mode"] == "ALREADY_OBSERVED"
            second_receipt = store.append_once(second(), now=NOW)
            assert second_receipt["mode"] == "CANONICAL_APPEND_COMMITTED"
            assert first_receipt["sequence"] == 0 and second_receipt["sequence"] == 1
            rows = store.read_window()
            assert len(rows) == 2
            assert verify_custody_window(rows)["head_chain_sha256"] == second_receipt["head_chain_sha256"]
            board = store.read_signal_board(now=NOW)
            assert board["total_validated_changes"] == 1
            assert board["customer_delivery_enabled"] is False
            result["first_append_committed"] = True
            result["exact_duplicate_noop"] = True
            result["second_append_committed"] = True
            result["hash_chain_validated_on_readback"] = True
            result["existing_v14_signal_board_rebuilt"] = True
            _expect_db_denial(
                fixture_writer,
                "INSERT INTO public.empire_data_exchange_observations (sequence) VALUES (2)",
                as_custodian=True,
            )
            result["unreviewed_row_insertion_denied"] = True
            # Complete-looking, forged public source identity or private
            # contact fields must be denied by PostgreSQL, not just Python.
            base_insert = (
                "INSERT INTO public.empire_data_exchange_observations "
                "(sequence,schema_version,source_id,dataset_id,region,"
                "source_observed_at,snapshot_sha256,previous_chain_sha256,"
                "chain_sha256,snapshot_json) "
                "SELECT 2,schema_version,source_id,dataset_id,region,"
                "source_observed_at + interval '1 hour',snapshot_sha256,"
                "chain_sha256,repeat('f',64),"
            )
            updated_time = (
                "jsonb_set(snapshot_json,'{records,0,source_observed_at}',"
                "to_jsonb((source_observed_at + interval '1 hour')::text))"
            )
            _expect_db_denial(
                fixture_admin,
                base_insert + "jsonb_set(" + updated_time
                + ",'{records,0,source_url}',"
                + "to_jsonb('https://evil.invalid/entity/1739547'::text)) "
                + "FROM public.empire_data_exchange_observations WHERE sequence=1",
                like="Data Exchange record identity or observation invalid",
            )
            _expect_db_denial(
                fixture_admin,
                base_insert + "jsonb_set(" + updated_time
                + ",'{records,0,contact_email}',"
                + "to_jsonb('private@example.org'::text)) "
                + "FROM public.empire_data_exchange_observations WHERE sequence=1",
                like="unreviewed Data Exchange source field",
            )
            result["forged_official_url_and_private_contact_denied"] = True
            for statement in (
                "UPDATE public.empire_data_exchange_observations SET region='north_west_england' WHERE sequence=0",
                "DELETE FROM public.empire_data_exchange_observations WHERE sequence=0",
                "TRUNCATE public.empire_data_exchange_observations",
            ):
                _expect_db_denial(fixture_admin, statement, like="append-only Data Exchange custody")
            result["update_delete_truncate_denied_by_db"] = True
            with psycopg.connect(fixture_admin) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT count(*) FROM public.empire_data_exchange_observations")
                    assert cur.fetchone()[0] == 2
            result["rows_after_adversarial_tests"] = 2
        finally:
            _run(str(BIN/"pg_ctl"), "-D", str(cluster), "-m", "immediate", "-w", "stop")
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
