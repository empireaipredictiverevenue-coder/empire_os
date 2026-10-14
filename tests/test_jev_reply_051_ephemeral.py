"""Prepared-only 051 migration: actual disposable PG login and tenant tests.

Independent of production EmpireDB. This fixture has its own DB and role
memberships and is destroyed after testing.
"""
from __future__ import annotations

from pathlib import Path
import socket
import subprocess
import tempfile

import pytest

BIN = Path("/usr/lib/postgresql/18/bin")
ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "migrations/empiredb/051_jev_crm_reply_candidates.sql"
TENANT_A = "00000000-0000-0000-0000-000000000101"
TENANT_B = "00000000-0000-0000-0000-000000000102"
PROSPECT_A = "00000000-0000-0000-0000-000000000201"
PROSPECT_B = "00000000-0000-0000-0000-000000000202"
INTENT_A = "00000000-0000-0000-0000-000000000301"
INTENT_B = "00000000-0000-0000-0000-000000000302"
REPLY_A = "00000000-0000-0000-0000-000000000401"
REPLY_B = "00000000-0000-0000-0000-000000000402"


def test_051_source_contract_is_provenance_only():
    sql = SQL.read_text(encoding="utf8")
    assert "PREPARED ONLY" in sql
    assert "SECURITY DEFINER" in sql
    assert "SET search_path = ''" in sql
    assert "public.empire_current_tenant_id()" in sql
    assert "public.empire_crm_prospect_authorized(p_prospect_id)" in sql
    assert "p_limit > 100" in sql
    assert "i.prospect_id = p_prospect_id" in sql
    assert "i.channel = 'email'" in sql
    assert "FALSE AS original_provider_authenticated" in sql
    assert "FALSE AS contact_binding_verified" in sql
    assert "GRANT EXECUTE ON FUNCTION" in sql
    assert "TO empire_revenue_crm_reader;" in sql
    assert "REVOKE ALL ON FUNCTION" in sql
    for forbidden in (
        "r.body_text", "r.from_contact", "r.normalized_from_contact",
        "r.metadata", "i.recipient", "i.body_text",
    ):
        assert forbidden not in sql
    assert "GRANT SELECT ON public.outbound_replies" not in sql


@pytest.fixture(scope="module")
def pg():
    if not (BIN / "pg_ctl").exists():
        pytest.skip("disposable PostgreSQL 18 not installed")
    with tempfile.TemporaryDirectory(prefix="empire-jev051-", dir="/tmp") as temp:
        root = Path(temp)
        socket_path = root / "socket"
        socket_path.mkdir(mode=0o700)
        dbpath = root / "db"
        init = subprocess.run(
            [str(BIN/"initdb"), "-D", str(dbpath), "-A", "trust",
             "--no-locale", "-E", "UTF8"],
            text=True, capture_output=True, timeout=25,
        )
        assert init.returncode == 0, init.stderr
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as portprobe:
            portprobe.bind(("127.0.0.1", 0))
            port = portprobe.getsockname()[1]
        start = subprocess.run(
            [str(BIN/"pg_ctl"), "-D", str(dbpath), "-l", str(root/"pg.log"),
             "-o", f"-c listen_addresses='' -k {socket_path} -p {port}",
             "-w", "start"],
            text=True, capture_output=True, timeout=25,
        )
        assert start.returncode == 0, start.stderr

        def run(sql, *, user="ubuntu", db="empiredb", error=False, file=None):
            command = [
                str(BIN/"psql"), "-X", "-At", "-v", "ON_ERROR_STOP=1",
                "-h", str(socket_path), "-p", str(port), "-U", user,
                "-d", db,
            ]
            command += ["-f", str(file)] if file is not None else ["-c", sql]
            response = subprocess.run(
                command, capture_output=True, text=True, timeout=20,
            )
            if error:
                assert response.returncode != 0, (response.stdout, response.stderr)
            else:
                assert response.returncode == 0, response.stderr
            return response.stdout.strip()

        try:
            run("CREATE DATABASE empiredb", db="postgres")
            run(f"""
                CREATE ROLE empiredb_migrator NOLOGIN NOINHERIT;
                GRANT empiredb_migrator TO ubuntu;
                CREATE ROLE empiredb_app NOLOGIN NOINHERIT;
                CREATE ROLE empiredb_readonly NOLOGIN NOINHERIT;
                CREATE ROLE empiredb_tenant_reader NOLOGIN NOINHERIT;
                CREATE ROLE empire_revenue_crm_reader NOLOGIN NOINHERIT
                  NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
                CREATE ROLE jev_login_a LOGIN NOINHERIT;
                CREATE ROLE jev_login_b LOGIN NOINHERIT;
                CREATE ROLE jev_login_unbound LOGIN NOINHERIT;
                GRANT empire_revenue_crm_reader TO
                  jev_login_a,jev_login_b,jev_login_unbound;
                GRANT USAGE ON SCHEMA public TO empire_revenue_crm_reader;
                GRANT CREATE ON SCHEMA public TO empiredb_migrator;
                SET ROLE empiredb_migrator;
                CREATE TABLE public.test_tenant_bindings (
                  role_name name PRIMARY KEY,tenant_id uuid,active boolean
                );
                CREATE TABLE public.test_prospect_bindings (
                  prospect_id uuid PRIMARY KEY,tenant_id uuid,active boolean
                );
                CREATE FUNCTION public.empire_current_tenant_id()
                RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER
                SET search_path = '' AS $$
                  SELECT tenant_id FROM public.test_tenant_bindings
                  WHERE role_name=session_user AND active LIMIT 1
                $$;
                REVOKE ALL ON FUNCTION public.empire_current_tenant_id()
                FROM PUBLIC;
                GRANT EXECUTE ON FUNCTION public.empire_current_tenant_id()
                  TO empire_revenue_crm_reader;
                CREATE FUNCTION public.empire_crm_prospect_authorized(p uuid)
                RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
                SET search_path = '' AS $$
                  SELECT EXISTS(
                    SELECT 1 FROM public.test_prospect_bindings b
                    WHERE b.prospect_id=p
                      AND b.tenant_id=public.empire_current_tenant_id()
                      AND b.active
                  )
                $$;
                REVOKE ALL ON FUNCTION public.empire_crm_prospect_authorized(uuid)
                  FROM PUBLIC;
                GRANT EXECUTE ON FUNCTION public.empire_crm_prospect_authorized(uuid)
                  TO empire_revenue_crm_reader;
                CREATE TABLE public.outbound_intents(
                  id uuid PRIMARY KEY,prospect_id uuid,channel text,status text
                );
                CREATE TABLE public.outbound_replies(
                  id uuid PRIMARY KEY,intent_id uuid,received_at timestamptz,
                  classification text,provider_message_id text,
                  body_text text,from_contact text
                );
                CREATE TABLE public.empire_conversations(
                  id uuid PRIMARY KEY,outbound_intent_id uuid,
                  channel text,prospect_id uuid
                );
                RESET ROLE;
                INSERT INTO public.test_tenant_bindings VALUES
                  ('jev_login_a','{TENANT_A}',true),
                  ('jev_login_b','{TENANT_B}',true);
                INSERT INTO public.test_prospect_bindings VALUES
                  ('{PROSPECT_A}','{TENANT_A}',true),
                  ('{PROSPECT_B}','{TENANT_B}',true);
                INSERT INTO public.outbound_intents VALUES
                  ('{INTENT_A}','{PROSPECT_A}','email','replied'),
                  ('{INTENT_B}','{PROSPECT_B}','email','replied');
                INSERT INTO public.outbound_replies VALUES
                  ('{REPLY_A}','{INTENT_A}',CURRENT_TIMESTAMP - INTERVAL '1 hour',
                   'positive','fixture:a','SENSITIVE BODY A','private@fixture.invalid'),
                  ('{REPLY_B}','{INTENT_B}',CURRENT_TIMESTAMP - INTERVAL '1 hour',
                   'positive','fixture:b','SENSITIVE BODY B','private_b@fixture.invalid');
                INSERT INTO public.empire_conversations VALUES
                  ('00000000-0000-0000-0000-000000000501',
                   '{INTENT_A}','email','{PROSPECT_A}'),
                  ('00000000-0000-0000-0000-000000000502',
                   '{INTENT_B}','email','{PROSPECT_B}');
            """)
            run("", file=SQL)
            run.socket_path = str(socket_path)
            run.port = port
            yield run
        finally:
            subprocess.run(
                [str(BIN/"pg_ctl"), "-D", str(dbpath),
                 "-m", "immediate", "-w", "stop"],
                capture_output=True, text=True, timeout=25,
            )


def statement(prospect=PROSPECT_A, limit=25):
    return (
        "BEGIN READ ONLY;"
        "SET LOCAL ROLE empire_revenue_crm_reader;"
        "SELECT prospect_id,reply_id,reply_classification,"
        "provider_reference_present,matching_conversation_count,"
        "original_provider_authenticated,contact_binding_verified "
        "FROM public.empire_read_crm_reply_candidates("
        f"'{prospect}'::uuid,{limit});"
        "ROLLBACK;"
    )


def test_real_login_a_sees_only_own_reply_candidate(pg):
    text = pg(statement(), user="jev_login_a")
    assert REPLY_A in text
    assert PROSPECT_A in text
    assert REPLY_B not in text
    assert "positive|t|1|f|f" in text
    assert "SENSITIVE BODY" not in text
    assert "private@" not in text


def test_real_login_b_sees_only_tenant_b(pg):
    text = pg(statement(prospect=PROSPECT_B), user="jev_login_b")
    assert REPLY_B in text
    assert REPLY_A not in text


def test_cross_tenant_requested_prospect_is_denied(pg):
    pg(statement(prospect=PROSPECT_A), user="jev_login_b", error=True)


def test_unbound_login_denied(pg):
    pg(statement(prospect=PROSPECT_A), user="jev_login_unbound", error=True)


def test_unbounded_call_rejected(pg):
    pg(statement(limit=1000), user="jev_login_a", error=True)


def test_direct_reply_table_read_is_denied(pg):
    pg(
        "BEGIN READ ONLY;SET LOCAL ROLE empire_revenue_crm_reader;"
        "SELECT body_text FROM public.outbound_replies;",
        user="jev_login_a", error=True,
    )


def test_no_public_rpc_access_without_explicit_role(pg):
    pg(
        f"SELECT count(*) FROM public.empire_read_crm_reply_candidates('{PROSPECT_A}',10)",
        user="jev_login_a", error=True,
    )


def test_python_adapter_real_session_matches_privileged_sql_isolation(pg):
    from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
    from empire_os.jev_gtm_reply_candidate_reader import review_jev_reply_candidates

    for login, tenant, target, own_reply in (
        ("jev_login_a", TENANT_A, PROSPECT_A, REPLY_A),
        ("jev_login_b", TENANT_B, PROSPECT_B, REPLY_B),
    ):
        dsn = (
            f"host={pg.socket_path} port={pg.port} "
            f"dbname=empiredb user={login}"
        )
        repository = PostgresRevenueCrmRepository(dsn, tenant_id=tenant)
        result = review_jev_reply_candidates(
            repository, prospect_id=target,
        )
        assert result["candidate_count"] == 1
        assert result["items"][0]["reply_ref"] == own_reply
        assert result["items"][0]["positive_buyer_reply_verified"] is False
        assert result["items"][0]["outbound_authorized"] is False
        assert result["genuine_buying_conversations_verified"] is None


def test_python_adapter_real_session_refuses_cross_tenant_request(pg):
    from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
    from empire_os.revenue_crm_transport import RevenueCrmTransportError
    from empire_os.jev_gtm_reply_candidate_reader import review_jev_reply_candidates

    dsn = (
        f"host={pg.socket_path} port={pg.port} "
        "dbname=empiredb user=jev_login_a"
    )
    repository = PostgresRevenueCrmRepository(dsn, tenant_id=TENANT_A)
    with pytest.raises(RevenueCrmTransportError):
        review_jev_reply_candidates(repository, prospect_id=PROSPECT_B)
