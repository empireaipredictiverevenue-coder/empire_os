"""Empirically verify prepared CRM membership SQL 041 on disposable PG18.

No production connections, imports of production credentials, role changes,
HTTP activation, or claims of live customer login.
"""
from __future__ import annotations

import socket
import subprocess
import tempfile
from pathlib import Path

import pytest

from empire_os.revenue_crm_signed_auth import EmpireDbCrmMembershipReader

BIN = Path("/usr/lib/postgresql/18/bin")
MIGRATION = (Path(__file__).resolve().parents[1]
             / "migrations/empiredb/041_crm_membership_authority.sql")
A = "00000000-0000-0000-0000-000000000101"
B = "00000000-0000-0000-0000-000000000102"


@pytest.fixture(scope="module")
def membership_pg():
    if not (BIN / "pg_ctl").exists():
        pytest.skip("disposable PostgreSQL 18 not available")
    with tempfile.TemporaryDirectory(prefix="empire-membership-041-",
                                     dir="/tmp") as temp:
        root = Path(temp)
        sock = root / "socket"
        sock.mkdir(mode=0o700)
        data = root / "db"
        initialized = subprocess.run(
            [str(BIN / "initdb"), "-D", str(data), "-A", "trust",
             "--no-locale", "-E", "UTF8"],
            capture_output=True, text=True, timeout=20,
        )
        assert initialized.returncode == 0, initialized.stderr
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        started = subprocess.run(
            [str(BIN / "pg_ctl"), "-D", str(data),
             "-l", str(root / "test-only.log"),
             "-o", f"-c listen_addresses='' -k {sock} -p {port}",
             "-w", "start"],
            capture_output=True, text=True, timeout=20,
        )
        assert started.returncode == 0, started.stderr

        def run(statement=None, *, user="ubuntu", database="crm_membership_fixture",
                check=True, file=None):
            args = [str(BIN / "psql"), "-X", "-At",
                    "-v", "ON_ERROR_STOP=1", "-h", str(sock),
                    "-p", str(port), "-U", user, "-d", database]
            args += ["-f", str(file)] if file else ["-c", statement]
            process = subprocess.run(args, text=True, capture_output=True, timeout=20)
            if check:
                assert process.returncode == 0, process.stderr
            else:
                assert process.returncode != 0
            return process.stdout.strip()

        try:
            run("CREATE DATABASE crm_membership_fixture;", database="postgres")
            run("""
                CREATE ROLE empiredb_migrator NOLOGIN;
                CREATE ROLE empiredb_app NOLOGIN;
                CREATE ROLE empiredb_readonly NOLOGIN;
                CREATE ROLE empiredb_tenant_reader NOLOGIN;
                CREATE ROLE empire_revenue_crm_reader NOLOGIN;
                CREATE ROLE empire_crm_membership_login LOGIN NOINHERIT;
                CREATE ROLE crm_unbound_fixture LOGIN NOINHERIT;
                GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator;
                GRANT empiredb_migrator TO ubuntu;
            """)
            run(file=MIGRATION)
            yield run, str(sock), port
        finally:
            subprocess.run(
                [str(BIN / "pg_ctl"), "-D", str(data),
                 "-m", "immediate", "-w", "stop"],
                capture_output=True, text=True, timeout=20,
            )


def test_migration_is_denied_by_default_and_has_no_members(membership_pg):
    run, _, _ = membership_pg
    assert run("SELECT count(*) FROM public.empire_crm_tenant_memberships;") == "0"
    assert run("""
        SELECT has_function_privilege(
          'empire_crm_membership_login',
          'public.empire_crm_read_member(text,uuid)', 'EXECUTE'
        );
    """) == "f"
    run("SELECT public.empire_crm_read_member('none',"
        f"'{A}'::uuid);", user="empire_crm_membership_login", check=False)
    run("SELECT count(*) FROM public.empire_crm_tenant_memberships;",
        user="empire_crm_membership_login", check=False)
    assert run("""
        SELECT relrowsecurity FROM pg_class
        WHERE oid='public.empire_crm_tenant_memberships'::regclass;
    """) == "t"
    assert run("""
        SELECT prosecdef FROM pg_proc
        WHERE oid='public.empire_crm_read_member(text,uuid)'::regprocedure;
    """) == "t"


def test_fixture_operator_grants_bounded_membership_then_revokes(membership_pg):
    run, sock, port = membership_pg
    # ONLY disposable fixture: operator boots dedicated LOGIN EXECUTE and
    # private evidence-backed memberships. Migration never performs this.
    run("""
        GRANT EXECUTE ON FUNCTION
          public.empire_crm_read_member(text,uuid)
          TO empire_crm_membership_login;
        INSERT INTO public.empire_crm_tenant_memberships
          (tenant_id, subject, role, status, evidence_ref, verified_at)
        VALUES
          ('00000000-0000-0000-0000-000000000101',
           'founder:verified', 'owner', 'active', 'fixture:proof', now()),
          ('00000000-0000-0000-0000-000000000102',
           'founder:verified', 'viewer', 'disabled', 'fixture:proof', now());
    """)
    try:
        sql = ("SELECT user_id,tenant_id,role,status FROM "
               "public.empire_crm_read_member('founder:verified',"
               f"'{A}'::uuid);")
        result = run(sql, user="empire_crm_membership_login")
        assert result == f"founder:verified|{A}|owner|active"
        assert run(sql, user="crm_unbound_fixture", check=False) == ""
        assert run(sql.replace(A, B), user="empire_crm_membership_login") == ""

        # psycopg connection: one trusted session_user, no direct table access.
        dsn = (f"host={sock} port={port} dbname=crm_membership_fixture "
               "user=empire_crm_membership_login")
        membership_reader = EmpireDbCrmMembershipReader(dsn)
        member = membership_reader("founder:verified", A)
        assert member is not None
        assert member.can("read")
        assert member.tenant_id == A
        assert membership_reader("founder:verified", B) is None
        assert membership_reader("another:person", A) is None
        # A shared or unbound app LOGIN cannot silently become the verifier.
        unbound_dsn = dsn.replace(
            "user=empire_crm_membership_login", "user=crm_unbound_fixture"
        )
        assert EmpireDbCrmMembershipReader(unbound_dsn)("founder:verified", A) is None
        # Validity and evidence changes are checked on each new DB session.
        run("UPDATE public.empire_crm_tenant_memberships SET "
            "verified_at=now()-interval '1 hour',"
            "valid_until=now()-interval '5 seconds' "
            f"WHERE tenant_id='{A}'::uuid AND subject='founder:verified';")
        assert membership_reader("founder:verified", A) is None
        run("UPDATE public.empire_crm_tenant_memberships SET "
            "valid_until=NULL,verified_at=now()+interval '10 minutes' "
            f"WHERE tenant_id='{A}'::uuid AND subject='founder:verified';")
        assert membership_reader("founder:verified", A) is None
        run("UPDATE public.empire_crm_tenant_memberships SET "
            "verified_at=now(),valid_until=NULL "
            f"WHERE tenant_id='{A}'::uuid AND subject='founder:verified';")
        assert membership_reader("founder:verified", A) is not None

        # A valid user loses access as soon as evidence record is disabled.
        run("UPDATE public.empire_crm_tenant_memberships SET "
            "status='disabled',revoked_at=now() "
            f"WHERE tenant_id='{A}'::uuid AND subject='founder:verified';")
        assert membership_reader("founder:verified", A) is None
    finally:
        run("REVOKE EXECUTE ON FUNCTION "
            "public.empire_crm_read_member(text,uuid) "
            "FROM empire_crm_membership_login;")
    # Applying again must not silently rewrite an existing authority.
    run(file=MIGRATION, check=False)


def test_migration_is_no_auto_credentials_or_authority():
    sql = MIGRATION.read_text()
    assert "PREPARED ONLY" in sql
    assert "SET LOCAL ROLE empiredb_migrator" in sql
    assert "REVOKE ALL ON FUNCTION" in sql
    assert "FROM PUBLIC" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "session_user = 'empire_crm_membership_login'" in sql
    assert "GRANT EXECUTE ON FUNCTION" not in sql
    assert "CREATE ROLE " not in sql
    assert "INSERT INTO " not in sql
    assert "PASSWORD " not in sql
