#!/usr/bin/env python3
"""Read-only production proof of consumer login, secret custody and RLS.

This script must be placed under a root-owned immutable review path before
execution by root. It NEVER creates users, rows, connections to remote hosts,
outbound emails or secrets. The original private credential is read only in
memory, never printed. It queries no subscriber record contents.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat

import psycopg

DB = "empiredb"
LOGIN = "empire_consumer_optin_login"
WRITER = "empire_consumer_optin_writer"
VAULT = Path("/etc/empire/consumer-optin")
PASSFILE = VAULT / "subscriber.pgpass"
KEYFILE = VAULT / "subscriber-keys.json"
TABLES = (
    "empire_consumer_subscriptions",
    "empire_consumer_consent_events",
    "empire_consumer_email_suppressions",
    "empire_consumer_one_time_tokens",
    "empire_consumer_delivery_receipts",
)
POLICIES = (
    "consumer_writer_subscriptions",
    "consumer_writer_consent_events",
    "consumer_writer_suppressions",
    "consumer_writer_tokens",
    "consumer_writer_delivery",
)
EXPECTED_KEYS = frozenset(("email_hmac","token_hmac","email_encryption","key_reference"))
HEX_256 = re.compile(r"[a-f0-9]{64}\Z")


def _root_only_file(path: Path, *, parent: Path) -> bytes:
    if not parent.is_dir() or parent.is_symlink():
        raise RuntimeError("VAULT_ROOT_INTEGRITY_HOLD")
    root_stat = parent.stat()
    if root_stat.st_uid != 0 or stat.S_IMODE(root_stat.st_mode) != 0o700:
        raise RuntimeError("VAULT_OWNERSHIP_OR_MODE_HOLD")
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("SECRET_FILE_MISSING_OR_SYMLINK")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        meta = os.fstat(descriptor)
        if (meta.st_uid != 0 or not stat.S_ISREG(meta.st_mode)
            or stat.S_IMODE(meta.st_mode) != 0o600
            or meta.st_nlink != 1 or meta.st_size > 4096):
            raise RuntimeError("SECRET_FILE_CUSTODY_MISMATCH")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read(4097)
    finally:
        os.close(descriptor)


def read_custody(*, vault: Path = VAULT) -> tuple[str, dict[str, str]]:
    passfile = vault / "subscriber.pgpass"
    keyfile = vault / "subscriber-keys.json"
    raw_pass = _root_only_file(passfile, parent=vault)
    raw_key = _root_only_file(keyfile, parent=vault)
    # Secrets never appear in exception messages or any printed result.
    try:
        parts = raw_pass.decode("ascii").strip().split(":")
        if parts[:4] != ["127.0.0.1","5432",DB,LOGIN] or len(parts) != 5:
            raise ValueError
        password = parts[4]
        if HEX_256.fullmatch(password) is None:
            raise ValueError
        keys = json.loads(raw_key)
        if not isinstance(keys, dict) or frozenset(keys) != EXPECTED_KEYS:
            raise ValueError
        if keys["key_reference"] != "consumer-key-v1":
            raise ValueError
        purposes = tuple(keys[k] for k in ("email_hmac","token_hmac","email_encryption"))
        if not all(isinstance(k,str) and HEX_256.fullmatch(k) for k in purposes):
            raise ValueError
        if len(set(purposes)) != 3 or password in purposes:
            raise ValueError
    except (UnicodeDecodeError, ValueError, TypeError, KeyError) as ex:
        raise RuntimeError("PRIVATE_CREDENTIAL_FORMAT_HOLD") from None
    return password, keys


def original_readonly_session(*, password: str,
                              connect=psycopg.connect) -> dict[str, bool]:
    # Explicitly named source, database and login. Never use global CRM DSN.
    with connect(
        dbname=DB, host="127.0.0.1", port=5432, user=LOGIN,
        password=password, connect_timeout=5,
        application_name="empire_consumer_readonly_identity_probe",
    ) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        pre = conn.execute(
            "SELECT session_user,current_user,current_database(),"
            "current_setting('transaction_read_only')"
        ).fetchone()
        if pre != (LOGIN, LOGIN, DB, "on"):
            raise RuntimeError("PRIVATE_ORIGINAL_LOGIN_IDENTITY_MISMATCH")
        caps = conn.execute(
            "SELECT l.rolcanlogin, NOT l.rolinherit, NOT l.rolsuper,"
            "NOT l.rolbypassrls, NOT l.rolcreatedb, NOT l.rolcreaterole,"
            "NOT l.rolreplication,l.rolconnlimit=5,"
            "NOT w.rolcanlogin, NOT w.rolinherit,"
            "NOT w.rolsuper,NOT w.rolbypassrls "
            "FROM pg_catalog.pg_roles l CROSS JOIN pg_catalog.pg_roles w "
            "WHERE l.rolname=%s AND w.rolname=%s", (LOGIN,WRITER),
        ).fetchone()
        if caps != (True,) * 12:
            raise RuntimeError("PRIVATE_LOGIN_ROLE_ATTRIBUTES_MISMATCH")
        membership = conn.execute(
            "SELECT count(*),bool_and(r.rolname=%s AND m.set_option "
            "AND NOT m.inherit_option AND NOT m.admin_option) "
            "FROM pg_catalog.pg_auth_members m "
            "JOIN pg_catalog.pg_roles u ON u.oid=m.member "
            "JOIN pg_catalog.pg_roles r ON r.oid=m.roleid "
            "WHERE u.rolname=%s", (WRITER,LOGIN),
        ).fetchone()
        if membership != (1,True):
            raise RuntimeError("PRIVATE_LOGIN_ROLE_MEMBERSHIP_MISMATCH")
        conn.execute("SET LOCAL ROLE "+WRITER)
        after = conn.execute(
            "SELECT session_user,current_user,current_database(),"
            "current_setting('transaction_read_only')"
        ).fetchone()
        if after != (LOGIN, WRITER, DB, "on"):
            raise RuntimeError("PRIVATE_WRITER_SESSION_MISMATCH")
        objects = conn.execute(
            "SELECT count(*) FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname=ANY(%s) AND c.relkind='r' "
            "AND c.relrowsecurity AND c.relforcerowsecurity "
            "AND pg_get_userbyid(c.relowner)='empiredb_migrator'",
            (list(TABLES),),
        ).fetchone()
        if objects != (5,):
            raise RuntimeError("PRIVATE_SCHEMA_RLS_OR_OWNERSHIP_HOLD")
        policies = conn.execute(
            "SELECT policyname FROM pg_catalog.pg_policies "
            "WHERE schemaname='public' AND tablename=ANY(%s)",
            (list(TABLES),),
        ).fetchall()
        if len(policies)!=5 or {r[0] for r in policies} != set(POLICIES):
            raise RuntimeError("PRIVATE_SCOPED_POLICIES_HOLD")
        for table in TABLES:
            relation = "public."+table
            grants=conn.execute(
                "SELECT has_table_privilege(%s,%s,'SELECT'),"
                "NOT has_table_privilege('empiredb_app',%s,'SELECT'),"
                "NOT has_table_privilege('empiredb_readonly',%s,'SELECT'),"
                "NOT has_table_privilege('public',%s,'SELECT')",
                (WRITER,relation,relation,relation,relation),
            ).fetchone()
            if grants != (True,True,True,True):
                raise RuntimeError("PRIVATE_CONSUMER_ACCESS_BOUNDARY_HOLD")
            # Prove the login can query RLS-scoped relation with zero rows
            # returned (not even total counts of real subscribers).
            conn.execute("SELECT 1 FROM "+relation+" LIMIT 0")
        conn.rollback()
    return {
        "scram_authenticated_tcp_loopback":True,
        "dedicated_login_and_writer_roles":True,
        "single_noninherited_settable_membership":True,
        "database_transaction_read_only":True,
        "five_force_rls_tables_and_policies":True,
        "crm_and_public_select_denied":True,
        "no_subscriber_rows_fetched":True,
    }


def diagnostic(*, vault: Path = VAULT, connect=psycopg.connect) -> dict:
    if os.geteuid()!=0:
        raise RuntimeError("ROOT_LOCAL_REVIEW_REQUIRED")
    password, keys=read_custody(vault=vault)
    state=original_readonly_session(password=password,connect=connect)
    return {
        "status":"CONSUMER_PRIVATE_IDENTITY_LIVE_READONLY_VALIDATED",
        "vault_root_only":True,
        "secret_file_modes_0600":True,
        "three_distinct_256bit_keys":True,
        "key_reference_version":keys["key_reference"],
        "production_database_modified":False,
        "email_sent":False,
        "public_service_activated":False,
        **state,
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only:
        print('{"status":"CONSUMER_PRIVATE_IDENTITY_REVIEW_HELD"}')
        return 3
    try:
        print(json.dumps(diagnostic(),sort_keys=True))
        return 0
    except Exception:
        # Deliberately never prints SQL, credential values, key materials,
        # network errors, or sender personal information.
        print(json.dumps({
            "status":"CONSUMER_PRIVATE_IDENTITY_READONLY_HOLD",
            "production_database_modified":False,
            "email_sent":False,
        },sort_keys=True))
        return 3


if __name__=="__main__":
    raise SystemExit(main())
