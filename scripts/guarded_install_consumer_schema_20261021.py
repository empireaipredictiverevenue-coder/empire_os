"""Atomic guarded consumer-only DB install. No default mutation.

Usage, as the PostgreSQL operator:
  python -B scripts/guarded_install_consumer_schema_20261021.py --read-only
  python -B scripts/guarded_install_consumer_schema_20261021.py \
      --apply-owner-approved EXACT_RELEASE_SHA256

For ephemeral tests ONLY, pg_virtualenv/fixture DB and port > 5432:
  python -B scripts/guarded_install_consumer_schema_20261021.py --test-ephemeral

No DB login, key, marketing send, web publication or subscriber service is
activated by installation. The production apply option requires a separate
explicit owner permission. Backup readiness is independently verified first.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
from pathlib import Path
from typing import Any

import psycopg

ROOT = Path(__file__).resolve().parents[1]
SQL057 = ROOT / "migrations/empiredb/057_consumer_roofing_optin_staged_20261020.sql"
SQL058 = ROOT / "migrations/empiredb/058_consumer_optin_private_role_staged_20261020.sql"
ROLE_SQL = (
    "CREATE ROLE empire_consumer_optin_writer "
    "NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS "
    "NOCREATEDB NOCREATEROLE NOREPLICATION"
)
ROLE = "empire_consumer_optin_writer"
TABLES = (
    "empire_consumer_subscriptions",
    "empire_consumer_consent_events",
    "empire_consumer_email_suppressions",
    "empire_consumer_one_time_tokens",
    "empire_consumer_delivery_receipts",
)
FIXTURE = "empire_consumer_optin_fixture"
LIVE = "empiredb"


def fingerprint() -> str:
    h = hashlib.sha256()
    for filename, raw in (
        ("ROLE_SQL", ROLE_SQL.encode("utf8")),
        (SQL057.name, SQL057.read_bytes()),
        (SQL058.name, SQL058.read_bytes()),
    ):
        h.update(filename.encode("ascii") + b"\\0")
        h.update(len(raw).to_bytes(8, "big") + raw)
    return h.hexdigest()


def strip_transaction_boundaries(path: Path) -> str:
    text = path.read_text(encoding="utf8").strip()
    if not text.startswith("-- CONSUMER0") or not text.endswith("COMMIT;"):
        raise RuntimeError("MIGRATION_FORMAT_CHANGED")
    start = text.find("\nBEGIN;")
    if start < 0 or text.count("\nBEGIN;") != 1 or text.count("\nCOMMIT;") != 1:
        raise RuntimeError("MIGRATION_TRANSACTION_BOUNDARIES_CHANGED")
    return text[:start] + "\n" + text[start + len("\nBEGIN;"): -len("COMMIT;")]


def query_state(conn) -> dict[str, Any]:
    role = conn.execute(
        "SELECT rolcanlogin,rolinherit,rolsuper,rolbypassrls,"
        "rolcreatedb,rolcreaterole,rolreplication "
        "FROM pg_roles WHERE rolname=%s", (ROLE,),
    ).fetchone()
    migrator = conn.execute(
        "SELECT NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls "
        "FROM pg_roles WHERE rolname='empiredb_migrator'",
    ).fetchone()
    existing = conn.execute(
        "SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,"
        "pg_get_userbyid(c.relowner) "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relname=ANY(%s) AND c.relkind='r'",
        (list(TABLES),),
    ).fetchall()
    policies = conn.execute(
        "SELECT tablename,policyname FROM pg_policies "
        "WHERE schemaname='public' AND tablename=ANY(%s)",
        (list(TABLES),),
    ).fetchall()
    safe_role = bool(role and role == (False, False, False, False, False, False, False))
    return {
        "database": conn.execute("SELECT current_database()").fetchone()[0],
        "migrator_ready": bool(migrator and migrator[0]),
        "writer_exists": role is not None,
        "writer_compliant": safe_role,
        "consumer_table_count": len(existing),
        "consumer_policy_count": len(policies),
        "all_existing_tables_forced_rls": all(
            row[1] is True and row[2] is True and row[3] == "empiredb_migrator"
            for row in existing
        ),
    }


def verify_installed(conn) -> dict[str, Any]:
    state = query_state(conn)
    expected = (
        state["migrator_ready"]
        and state["writer_compliant"]
        and state["consumer_table_count"] == 5
        and state["consumer_policy_count"] == 5
        and state["all_existing_tables_forced_rls"]
    )
    assert expected, "SCHEMA_REVIEW_READBACK_MISMATCH"
    assert conn.execute(
        "SELECT count(*) FROM pg_policies WHERE schemaname='public' "
        "AND policyname LIKE 'consumer_writer_%'"
    ).fetchone()[0] == 5, "NONCANONICAL_RLS_POLICY_COUNT"
    for table in TABLES:
        quoted = "public." + table
        assert conn.execute(
            "SELECT NOT has_table_privilege('public',%s,'SELECT') "
            "AND NOT has_table_privilege('public',%s,'INSERT')",
            (quoted, quoted),
        ).fetchone()[0] is True, "PUBLIC_DATA_GRANT_DETECTED"
        role_known = conn.execute(
            "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='empiredb_app')"
        ).fetchone()[0]
        if role_known:
            assert conn.execute(
                "SELECT NOT has_table_privilege('empiredb_app',%s,'SELECT')",
                (quoted,),
            ).fetchone()[0] is True, "COMPANY_CRM_READ_ACCESS_DETECTED"
    return state


def installer(mode: str, approved_digest: str = "") -> dict[str, Any]:
    envhost = os.getenv("PGHOST")
    envport = os.getenv("PGPORT", "")
    ephemeral = (
        os.getenv("PGHOST") == "localhost"
        and envport.isdecimal() and 5433 <= int(envport) <= 65535
        and not os.getenv("EMPIREDB_DSN")
    )
    database = FIXTURE if mode == "test" else LIVE
    if mode == "test" and not ephemeral:
        raise RuntimeError("EPHEMERAL_FIXTURE_CLUSTER_REQUIRED")
    if mode == "apply":
        if pwd.getpwuid(os.geteuid()).pw_name != "postgres":
            raise RuntimeError("OPERATE_UNDER_POSTGRES_IDENTITY")
        if envhost or envport or os.getenv("EMPIREDB_DSN"):
            raise RuntimeError("PRODUCTION_DB_CONNECTION_MUST_USE_LOCAL_PEER")
        if approved_digest != fingerprint():
            raise RuntimeError("EXACT_RELEASE_DIGEST_APPROVAL_REQUIRED")
    with psycopg.connect(dbname=database, connect_timeout=6) as conn:
        before = query_state(conn)
        if before["database"] != database or not before["migrator_ready"]:
            raise RuntimeError("TARGET_DB_OR_MIGRATOR_INVALID")
        if mode == "read-only":
            return {
                "status": "CONSUMER_DB_READ_ONLY_PREFLIGHT",
                "release_sha256": fingerprint(),
                "backup_validation": "SEPARATE_PRIVILEGED_RECEIPT_REQUIRED",
                "database_mutation": False,
                **before,
            }
        if before["consumer_table_count"] or before["consumer_policy_count"]:
            raise RuntimeError("OBJECTS_ALREADY_PRESENT_REFRESH_AND_RECONCILE")
        if before["writer_exists"] and not before["writer_compliant"]:
            raise RuntimeError("EXISTING_WRITER_ROLE_IS_NONCOMPLIANT")
        with conn.transaction():
            if not before["writer_exists"]:
                conn.execute(ROLE_SQL)
            conn.execute(strip_transaction_boundaries(SQL057))
            conn.execute("SET LOCAL ROLE NONE")
            conn.execute(strip_transaction_boundaries(SQL058))
            conn.execute("SET LOCAL ROLE NONE")
            after = verify_installed(conn)
        # Everything above (including role creation) is one transaction.
        return {
            "status": (
                "CONSUMER_EPHEMERAL_ATOMIC_INSTALL_VERIFIED"
                if mode == "test" else "CONSUMER_SCHEMA_INSTALLED_READBACK_VERIFIED"
            ),
            "release_sha256": fingerprint(),
            "database_mutation": True,
            "public_collection_enabled": False,
            "outbound_enabled": False,
            "payments_enabled": False,
            "consumer_service_login_created": False,
            **after,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--read-only", action="store_true")
    group.add_argument("--test-ephemeral", action="store_true")
    group.add_argument("--apply-owner-approved", metavar="SHA256")
    args = parser.parse_args()
    mode = "read-only" if args.read_only else "test" if args.test_ephemeral else "apply"
    try:
        result = installer(mode, args.apply_owner_approved or "")
    except Exception as ex:
        # No leaking credentials or SQL statement parameters in the error.
        print(json.dumps({
            "status": "CONSUMER_INSTALL_HELD",
            "reason": str(ex).splitlines()[0][:200],
            "database_mutation_completed": False,
        }, sort_keys=True))
        raise SystemExit(3)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
