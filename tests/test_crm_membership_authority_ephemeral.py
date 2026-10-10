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


def test_prepared_042_invite_only_login_and_signed_crm_token(membership_pg):
    """End-to-end local PG18: credential -> membership -> Ed25519 read JWT."""
    from datetime import datetime, timezone
    import time
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from empire_os.revenue_crm_first_party_login import (
        hash_invited_password, PostgresCrmPasswordLogin,
        build_account_bound_membership_lookup, create_crm_login_router,
    )
    from empire_os.revenue_crm_signed_auth import (
        EmpireDbCrmMembershipReader, SignedCrmTenantVerifier,
    )

    run, sock, port = membership_pg
    root = Path(__file__).resolve().parents[1]
    migration42 = root / "migrations/empiredb/042_crm_first_party_login.sql"
    assert "PREPARED ONLY" in migration42.read_text()
    run(file=migration42)

    # NO rights for any application by default; 042 applies zero real users.
    assert run("SELECT count(*) FROM public.empire_crm_login_credentials") == "0"
    assert run("""SELECT has_table_privilege(
        'empiredb_app','public.empire_crm_login_credentials','SELECT');""") == "f"
    run("SELECT count(*) FROM public.empire_crm_login_credentials;",
        user="crm_unbound_fixture", check=False)
    assert run("""SELECT relrowsecurity FROM pg_class
        WHERE oid='public.empire_crm_login_credentials'::regclass;""") == "t"

    # Fixture operator actions ONLY: no production role, secret or membership.
    import secrets
    salt = secrets.token_bytes(32)
    password = "test-only-long-invite-passphrase-123"
    digest = hash_invited_password(password, salt)
    subject = "pilot:verified"
    email = "pilot@example.invalid"
    run("""
        CREATE ROLE empire_crm_auth_login LOGIN NOINHERIT;
        GRANT SELECT ON public.empire_crm_login_credentials
          TO empire_crm_auth_login;
        GRANT UPDATE(failed_attempts,locked_until,last_login_at,updated_at)
          ON public.empire_crm_login_credentials TO empire_crm_auth_login;
        GRANT EXECUTE ON FUNCTION public.empire_crm_read_member(text,uuid)
          TO empire_crm_membership_login;
    """)
    run(f"""
        INSERT INTO public.empire_crm_login_credentials
          (subject,login_email,password_salt,password_digest,status,
           evidence_ref,password_change_required,verified_at)
        VALUES ('{subject}','{email}',decode('{salt.hex()}','hex'),
            decode('{digest.hex()}','hex'),'active','fixture:pilot-proof',false,now());
        INSERT INTO public.empire_crm_tenant_memberships
          (tenant_id,subject,role,status,evidence_ref,verified_at)
        VALUES ('{A}','{subject}','viewer','active','fixture:pilot-proof',now());
    """)
    auth_dsn = (f"host={sock} port={port} dbname=crm_membership_fixture "
                "user=empire_crm_auth_login")
    membership_dsn = auth_dsn.replace(
        "user=empire_crm_auth_login", "user=empire_crm_membership_login"
    )
    password_login = PostgresCrmPasswordLogin(auth_dsn)
    member_reader = EmpireDbCrmMembershipReader(membership_dsn)
    active_member = build_account_bound_membership_lookup(
        password_login, member_reader,
    )
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    app = FastAPI()
    app.include_router(create_crm_login_router(
        password_login=password_login,
        load_membership=active_member,
        signing_key=private_key, key_id="test-issuer",
    ))
    client = TestClient(app)
    data = {"email": email, "password": password, "tenant_id": A}

    # Signed token was really derived from a user credential and live evidence.
    success = client.post("/v1/revenue-crm/auth/login", json=data)
    assert success.status_code == 200, success.text
    assert success.headers["cache-control"] == "no-store"
    token = success.json()["access_token"]
    verifier = SignedCrmTenantVerifier(
        {"test-issuer": public_key}, load_membership=active_member
    )
    assert verifier.authenticate(token) == A
    assert success.json()["expires_in"] == 300

    # Can't spoof another tenant, even with correct human password.
    assert client.post("/v1/revenue-crm/auth/login", json={
        **data, "tenant_id": B,
    }).status_code == 401

    # Credentialed login, but zero membership after revoke.
    run(f"""UPDATE public.empire_crm_tenant_memberships
             SET status='disabled',revoked_at=now()
             WHERE subject='{subject}' AND tenant_id='{A}';""")
    assert client.post("/v1/revenue-crm/auth/login", json=data).status_code == 401
    import pytest
    with pytest.raises(ValueError, match="membership"):
        verifier.authenticate(token)

    # Restore fixture membership to prove password failure counter/lockout.
    run(f"""UPDATE public.empire_crm_tenant_memberships
             SET status='active',revoked_at=NULL
             WHERE subject='{subject}' AND tenant_id='{A}';""")
    for attempt in range(5):
        bad = client.post("/v1/revenue-crm/auth/login", json={
            **data, "password": "incorrect-test-password-over-14",
        })
        assert bad.status_code == 401
    assert run(f"""SELECT failed_attempts FROM public.empire_crm_login_credentials
        WHERE subject='{subject}';""") == "5"
    # Correct secret does NOT bypass the lockout.
    assert client.post("/v1/revenue-crm/auth/login", json=data).status_code == 401

    # Disabled identity is not valid even if operator resets failed attempts.
    run(f"""UPDATE public.empire_crm_login_credentials
        SET failed_attempts=0,locked_until=NULL,status='disabled'
        WHERE subject='{subject}';""")
    assert client.post("/v1/revenue-crm/auth/login", json=data).status_code == 401
    with pytest.raises(ValueError, match="membership"):
        verifier.authenticate(token)  # disabled account revokes existing JWT

    # Unbound login has no credential authority even if given a matching DSN.
    assert PostgresCrmPasswordLogin(
        auth_dsn.replace("user=empire_crm_auth_login", "user=crm_unbound_fixture")
    ).authenticate(email, password) is None
    run(file=migration42,check=False)
