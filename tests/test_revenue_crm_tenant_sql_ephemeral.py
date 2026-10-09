"""Verify tenant isolation under real PostgreSQL LOGIN sessions, not --single.

Ephemeral PG18 Unix socket, isolated fixtures, read-only application queries.
No production database/credentials or persistent service.
"""
from __future__ import annotations

from pathlib import Path
import socket
import subprocess
import tempfile

import pytest

from empire_os.revenue_crm_transport import (
    PROSPECT_COLUMNS, BUYER_COLUMNS,
    PostgresRevenueCrmRepository, RevenueCrmTransportError,
)

BIN = Path("/usr/lib/postgresql/18/bin")
A = "00000000-0000-0000-0000-000000000101"
B = "00000000-0000-0000-0000-000000000102"
PA = "00000000-0000-0000-0000-000000000001"
PB = "00000000-0000-0000-0000-000000000002"


@pytest.fixture(scope="module")
def pg():
    if not (BIN / "pg_ctl").exists():
        pytest.skip("PostgreSQL 18 binaries unavailable")
    with tempfile.TemporaryDirectory(prefix="empire-crm-pg-", dir="/tmp") as temp:
        root = Path(temp)
        (root / "socket").mkdir(mode=0o700)
        data = root / "db"
        init = subprocess.run(
            [str(BIN / "initdb"), "-D", str(data), "-A", "trust",
             "--no-locale", "-E", "UTF8"],
            capture_output=True, text=True, timeout=20,
        )
        assert init.returncode == 0, init.stderr
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as port_probe:
            port_probe.bind(("127.0.0.1", 0))
            port = port_probe.getsockname()[1]
        sock = str(root / "socket")
        started = subprocess.run(
            [str(BIN / "pg_ctl"), "-D", str(data),
             "-l", str(root / "postgres-test-only.log"),
             "-o", f"-c listen_addresses='' -k {sock} -p {port}",
             "-w", "start"],
            capture_output=True, text=True, timeout=20,
        )
        assert started.returncode == 0, started.stderr
        def run(db: str, query: str, *, user="ubuntu", expect_error=False):
            result = subprocess.run(
                [str(BIN / "psql"), "-X", "-At", "-v", "ON_ERROR_STOP=1",
                 "-h", sock, "-p", str(port), "-U", user, "-d", db,
                 "-c", query],
                capture_output=True, text=True, timeout=15,
            )
            if expect_error:
                assert result.returncode != 0, (result.stdout, result.stderr)
            else:
                assert result.returncode == 0, result.stderr
            return result.stdout.strip()
        try:
            run("postgres", "CREATE DATABASE crm_fixture;")
            prospect_extra = [
                c for c in PROSPECT_COLUMNS.split(",")
                if c not in ("tenant_id", "prospect_id", "business_name")
            ]
            buyer_extra = [
                c for c in BUYER_COLUMNS.split(",")
                if c not in ("tenant_id", "buyer_id", "buyer_name")
            ]
            prospect_view = ", ".join(
                ["tenant_id", "prospect_id", "business_name"]
                + [f"NULL::text AS {c}" for c in prospect_extra]
            )
            buyer_view = ", ".join(
                ["tenant_id", "buyer_id", "buyer_name"]
                + [f"NULL::text AS {c}" for c in buyer_extra]
            )
            run("crm_fixture", f"""
                CREATE ROLE empire_revenue_crm_reader NOLOGIN NOINHERIT
                    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
                CREATE ROLE crm_login_a LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS;
                CREATE ROLE crm_login_b LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS;
                CREATE ROLE crm_login_unbound LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS;
                GRANT empire_revenue_crm_reader TO crm_login_a;
                GRANT empire_revenue_crm_reader TO crm_login_b;
                GRANT empire_revenue_crm_reader TO crm_login_unbound;
                CREATE TABLE public.empire_tenant_role_bindings(
                    role_name name PRIMARY KEY, tenant_id uuid, active boolean);
                INSERT INTO public.empire_tenant_role_bindings VALUES
                    ('crm_login_a','{A}',true),('crm_login_b','{B}',true);
                REVOKE ALL ON public.empire_tenant_role_bindings FROM PUBLIC;
                CREATE FUNCTION public.empire_current_tenant_id()
                RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER
                SET search_path=pg_catalog, public AS $$
                    SELECT tenant_id FROM public.empire_tenant_role_bindings
                    WHERE role_name=session_user AND active LIMIT 1
                $$;
                REVOKE ALL ON FUNCTION public.empire_current_tenant_id() FROM PUBLIC;
                GRANT EXECUTE ON FUNCTION public.empire_current_tenant_id()
                    TO empire_revenue_crm_reader;
                CREATE TABLE public.prospects(
                    tenant_id uuid NOT NULL, prospect_id uuid NOT NULL,
                    business_name text NOT NULL);
                CREATE TABLE public.buyers(
                    tenant_id uuid NOT NULL, buyer_id uuid NOT NULL,
                    buyer_name text NOT NULL);
                INSERT INTO public.prospects VALUES
                    ('{A}','{PA}','FIXTURE_ONLY_TENANT_A'),
                    ('{B}','{PB}','FIXTURE_ONLY_TENANT_B');
                INSERT INTO public.buyers VALUES
                    ('{A}','00000000-0000-0000-0000-000000000003','FIXTURE_BUYER_A'),
                    ('{B}','00000000-0000-0000-0000-000000000004','FIXTURE_BUYER_B');
                ALTER TABLE public.prospects ENABLE ROW LEVEL SECURITY;
                ALTER TABLE public.buyers ENABLE ROW LEVEL SECURITY;
                CREATE POLICY crm_prospect_tenant ON public.prospects
                    FOR SELECT TO empire_revenue_crm_reader USING (
                        tenant_id=public.empire_current_tenant_id());
                CREATE POLICY crm_buyer_tenant ON public.buyers
                    FOR SELECT TO empire_revenue_crm_reader USING (
                        tenant_id=public.empire_current_tenant_id());
                CREATE VIEW public.revenue_crm_prospects
                    WITH (security_invoker=true)
                    AS SELECT {prospect_view} FROM public.prospects;
                CREATE VIEW public.revenue_crm_buyers
                    WITH (security_invoker=true)
                    AS SELECT {buyer_view} FROM public.buyers;
                GRANT USAGE ON SCHEMA public TO empire_revenue_crm_reader;
                GRANT SELECT ON public.prospects,public.buyers,
                    public.revenue_crm_prospects,public.revenue_crm_buyers
                    TO empire_revenue_crm_reader;
            """)
            yield run, sock, port
        finally:
            subprocess.run(
                [str(BIN / "pg_ctl"), "-D", str(data), "-m", "immediate",
                 "-w", "stop"],
                capture_output=True, text=True, timeout=20,
            )


def test_normal_login_proves_tenant_a_and_b_isolation(pg):
    run, _, _ = pg
    for login, wanted, unwanted in (
        ("crm_login_a", "FIXTURE_ONLY_TENANT_A", "FIXTURE_ONLY_TENANT_B"),
        ("crm_login_b", "FIXTURE_ONLY_TENANT_B", "FIXTURE_ONLY_TENANT_A"),
    ):
        result = run("crm_fixture", """
            BEGIN READ ONLY;
            SET LOCAL ROLE empire_revenue_crm_reader;
            SELECT public.empire_current_tenant_id();
            SELECT business_name FROM public.revenue_crm_prospects;
            SELECT buyer_name FROM public.revenue_crm_buyers;
            ROLLBACK;
        """, user=login)
        assert wanted in result
        assert unwanted not in result
        assert ("FIXTURE_BUYER_A" in result) == (login == "crm_login_a")
        assert ("FIXTURE_BUYER_B" in result) == (login == "crm_login_b")


def test_unbound_login_denied_every_row(pg):
    run, _, _ = pg
    result = run("crm_fixture", """
        BEGIN READ ONLY;
        SET LOCAL ROLE empire_revenue_crm_reader;
        SELECT business_name FROM public.revenue_crm_prospects;
        SELECT buyer_name FROM public.revenue_crm_buyers;
        ROLLBACK;
    """, user="crm_login_unbound")
    assert "FIXTURE_ONLY_TENANT_A" not in result
    assert "FIXTURE_ONLY_TENANT_B" not in result
    assert "FIXTURE_BUYER_A" not in result
    assert "FIXTURE_BUYER_B" not in result


def test_direct_login_without_assumed_role_cannot_read_crm_view(pg):
    run, _, _ = pg
    result = run(
        "crm_fixture",
        "SELECT business_name FROM public.revenue_crm_prospects;",
        user="crm_login_a", expect_error=True,
    )
    assert "FIXTURE_ONLY_TENANT_A" not in result


def test_real_psycopg_adapter_returns_only_authenticated_tenant(pg):
    _, sock, port = pg
    for username, scope, allowed, forbidden, prospect in (
        ("crm_login_a", A, "FIXTURE_ONLY_TENANT_A", "FIXTURE_ONLY_TENANT_B", PA),
        ("crm_login_b", B, "FIXTURE_ONLY_TENANT_B", "FIXTURE_ONLY_TENANT_A", PB),
    ):
        dsn = f"host={sock} port={port} dbname=crm_fixture user={username}"
        repo = PostgresRevenueCrmRepository(dsn, tenant_id=scope)
        rows = repo.prospects(limit=20)
        assert len(rows) == 1
        assert rows[0]["business_name"] == allowed
        assert forbidden not in repr(rows)
        buyers = repo.buyers(limit=20)
        assert len(buyers) == 1
        assert str(buyers[0]["tenant_id"]) == scope
        assert repo.prospect(prospect)["business_name"] == allowed
        assert repo.prospect(PB if scope == A else PA) is None


def test_tenant_mismatch_is_blocked_before_crm_query(pg):
    _, sock, port = pg
    dsn = f"host={sock} port={port} dbname=crm_fixture user=crm_login_a"
    wrong = PostgresRevenueCrmRepository(dsn, tenant_id=B)
    with pytest.raises(RevenueCrmTransportError, match="tenant scope unverified"):
        wrong.prospects(limit=10)


def test_catalog_probe_checks_actual_restricted_pg18_catalog(pg):
    from importlib.util import spec_from_file_location, module_from_spec
    from pathlib import Path
    import psycopg
    root = Path(__file__).resolve().parents[1]
    spec = spec_from_file_location(
        "crm_catalog_real_pg_test",
        root / "scripts/verify_revenue_crm_live_contract.py",
    )
    assert spec and spec.loader
    probe = module_from_spec(spec)
    spec.loader.exec_module(probe)
    _, sock, port = pg
    dsn = f"host={sock} port={port} dbname=crm_fixture user=ubuntu"
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            report = probe.inspect_crm_catalog(cursor)
    assert report["status"] == "CATALOG_PRECONDITIONS_VERIFIED", report["blockers"]
    assert report["role_safe"] is True
    assert report["trusted_tenant_function_present"] is True
    for name in ("prospects", "buyers"):
        assert report["views"][name] == {
            "present": True, "columns_complete": True,
            "security_invoker": True,
            "base_rls_verified": True,
            "role_select_only": True,
        }
    assert report["actual_cross_tenant_read_verified"] is False
    assert report["public_api_activation_authorized"] is False


def test_catalog_probe_rejects_removed_tenant_policy_on_pg18(pg):
    from importlib.util import spec_from_file_location, module_from_spec
    from pathlib import Path
    import psycopg
    root = Path(__file__).resolve().parents[1]
    spec = spec_from_file_location(
        "crm_catalog_pg_removed_policy",
        root / "scripts/verify_revenue_crm_live_contract.py",
    )
    assert spec and spec.loader
    probe = module_from_spec(spec)
    spec.loader.exec_module(probe)
    run, sock, port = pg
    run("crm_fixture", "DROP POLICY crm_prospect_tenant ON public.prospects;")
    dsn = f"host={sock} port={port} dbname=crm_fixture user=ubuntu"
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            report = probe.inspect_crm_catalog(cursor)
    assert report["status"] == "BLOCKED"
    assert "PROSPECTS_BASE_RLS_NOT_VERIFIED" in report["blockers"]
    assert report["public_api_activation_authorized"] is False
