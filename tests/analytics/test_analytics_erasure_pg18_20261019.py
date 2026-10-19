"""Analytics055 actual PostgreSQL 18 isolated temp DB erasure/retention tests.

Reuses Analytics054 fixture's PRIVATE UNIX socket cluster. Never uses a
live DB, remote host, ambient PG credentials, service or systemd action.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import uuid

import psycopg
import pytest

from tests.analytics.test_analytics_ledger_pg18_20261019 import (
    db_socket, ADMIN, TENANT_A, TENANT_B, PROP, POLICY,
    new_session, decide, record,
)

MIGRATION = (Path(__file__).resolve().parents[2]
             / "migrations/empiredb/055_first_party_analytics_erasure_held.sql")
FUNC = "public.empire_analytics_erase_session(uuid,text,text,text,text)"
ERASE_SQL = """
 SELECT * FROM public.empire_analytics_erase_session(%s,%s,%s,%s,%s)
"""
MAINT = "empire_analytics_maintenance_login"
REFERENCE = "e" * 64


@pytest.fixture(scope="module")
def held_db(db_socket):
    dsn, script = db_socket
    # Existing migration 054 has been applied to a completely disposable
    # PostgreSQL 18 cluster. Apply the HELD 055 ONLY there.
    base = Path(dsn.split("host=")[1].split(" ")[0])
    import os,subprocess
    env={k:v for k,v in os.environ.items() if not k.startswith("PG")}
    env.update(PGHOST=str(base), PGPORT="56652", PGUSER=ADMIN, PGSSLMODE="disable")
    cmd=["/usr/lib/postgresql/18/bin/psql", "-X","-v","ON_ERROR_STOP=1",
         "-d","empire_analytics_fixture","-f",str(MIGRATION)]
    proc=subprocess.run(cmd, env=env,capture_output=True,text=True,timeout=20)
    assert proc.returncode==0, proc.stderr[-1300:]
    yield dsn,script,env


@pytest.fixture(scope="module")
def granted_maintenance(held_db):
    dsn,script,_=held_db
    # IMPORTANT: not in the prepared migration. Fixture-only simulated
    # role/permission provision for real database end-to-end tests.
    with psycopg.connect(dsn,autocommit=True) as conn:
        conn.execute(
          "CREATE ROLE empire_analytics_maintenance_login LOGIN "
          "NOSUPERUSER NOBYPASSRLS NOINHERIT"
        )
        conn.execute("GRANT USAGE ON SCHEMA public TO empire_analytics_maintenance_login")
        conn.execute("GRANT EXECUTE ON FUNCTION "+FUNC+" TO empire_analytics_maintenance_login")
    # The parent psql fixture has trust auth but UNIX socket is private.
    maint_dsn=dsn.replace("user="+ADMIN,"user="+MAINT)
    return dsn, maint_dsn


def erase(conn, tenant, session, reason="VERIFIED_ERASURE_REQUEST", ref=REFERENCE):
    return conn.execute(ERASE_SQL, (tenant, PROP, session, reason, ref)).fetchone()


def fresh_data(admin, tenant=TENANT_A, *, make_events=2, revoke=False):
    session=new_session(admin,tenant=tenant)
    decide(admin,session,1,"granted",tenant=tenant)
    for _ in range(make_events):
        record(admin,session,tenant=tenant)
    if revoke:
        decide(admin,session,2,"revoked",tenant=tenant)
    return session


def get_count(admin, table, tenant, session):
    return admin.execute(
     "SELECT count(*) FROM public.empire_analytics_"+table
     +" WHERE tenant_id=%s AND property_key=%s AND session_digest=%s",
     (tenant,PROP,session)).fetchone()[0]


def test_held_055_adds_no_runtime_grants_for_any_role(held_db):
    dsn,_,_=held_db
    with psycopg.connect(dsn,autocommit=True) as conn:
        obj=conn.execute("""
          SELECT c.relrowsecurity,c.relforcerowsecurity
          FROM pg_catalog.pg_class c
          WHERE c.oid='public.empire_analytics_erasure_audit'::regclass
        """).fetchone()
        assert obj==(True,True)
        f=conn.execute("""
          SELECT p.prosecdef, r.rolname FROM pg_catalog.pg_proc p
          JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
          WHERE p.oid=%s::regprocedure
        """,(FUNC,)).fetchone()
        assert f==(True,"empiredb_migrator")
        assert conn.execute("""
          SELECT has_function_privilege('public',%s,'EXECUTE')
        """,(FUNC,)).fetchone()[0] is False
        roles=conn.execute("""
          SELECT count(*) FROM pg_catalog.pg_roles
          WHERE rolname='empire_analytics_maintenance_login'
        """).fetchone()[0]
        assert roles==0


def test_maintenance_actor_cannot_inherit_existing_migrator_role(held_db):
    dsn,_,_=held_db
    with psycopg.connect(dsn,autocommit=True) as conn:
        member=conn.execute("""
          SELECT count(*) FROM pg_catalog.pg_auth_members am
          JOIN pg_catalog.pg_roles r ON r.oid=am.roleid
          WHERE r.rolname='empiredb_migrator'
        """).fetchone()[0]
        assert member==0


def test_admin_cannot_impersonate_signed_erasure_request(granted_maintenance):
    admin_dsn,_=granted_maintenance
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        session=fresh_data(admin)
        with pytest.raises(psycopg.Error,match="TRUSTED_MAINTENANCE_LOGIN"):
            erase(admin,TENANT_A,session)
        assert get_count(admin,"sessions",TENANT_A,session)==1


def test_no_direct_maint_select_or_delete_even_with_erasure_execute(granted_maintenance):
    _,maint_dsn=granted_maintenance
    with psycopg.connect(maint_dsn,autocommit=True) as maint:
        for name in ("sessions","consent_decisions","event_receipts","erasure_audit"):
            with pytest.raises(psycopg.Error,match="permission denied"):
                maint.execute("SELECT count(*) FROM public.empire_analytics_"+name)
        with pytest.raises(psycopg.Error,match="permission denied"):
            maint.execute("DELETE FROM public.empire_analytics_sessions WHERE false")
        with pytest.raises(psycopg.Error,match="permission denied"):
            maint.execute("SET ROLE empiredb_migrator")


def test_restricted_function_erases_only_exact_session_then_audits(granted_maintenance):
    admin_dsn,maint_dsn=granted_maintenance
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        to_delete=fresh_data(admin,make_events=3,revoke=True)
        keep=fresh_data(admin,make_events=1)
        cross=fresh_data(admin,tenant=TENANT_B,make_events=1)
    with psycopg.connect(maint_dsn,autocommit=True) as maint:
        outcome=erase(maint,TENANT_A,to_delete)
        assert outcome[1:]==(1,2,3)
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        for table in ("sessions","consent_decisions","event_receipts"):
            assert get_count(admin,table,TENANT_A,to_delete)==0
            assert get_count(admin,table,TENANT_A,keep)>=1
            assert get_count(admin,table,TENANT_B,cross)>=1
        result=admin.execute("""
          SELECT tenant_id,property_key,erasure_reason,
                 verification_reference_sha256,
                 sessions_erased,decisions_erased,events_erased,
                 actor_role FROM public.empire_analytics_erasure_audit
          WHERE audit_id=%s
        """,(outcome[0],)).fetchone()
        assert result[0]==uuid.UUID(TENANT_A)
        assert result[1:]==(PROP,"VERIFIED_ERASURE_REQUEST",REFERENCE,1,2,3,MAINT)
        assert to_delete not in str(result)
        with pytest.raises(psycopg.Error,match="APPEND_ONLY"):
            admin.execute("DELETE FROM public.empire_analytics_erasure_audit WHERE audit_id=%s",
                          (outcome[0],))


def test_cross_tenant_erasure_refused(granted_maintenance):
    admin_dsn,maint_dsn=granted_maintenance
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        keep=fresh_data(admin,tenant=TENANT_B)
    with psycopg.connect(maint_dsn,autocommit=True) as maint:
        with pytest.raises(psycopg.Error,match="SESSION_NOT_PRESENT_IN_TENANT_SCOPE"):
            erase(maint,TENANT_A,keep)
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        assert get_count(admin,"sessions",TENANT_B,keep)==1


def test_expired_retention_reason_requires_elapsed_threshold(granted_maintenance):
    admin_dsn,maint_dsn=granted_maintenance
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        active=fresh_data(admin)
    with psycopg.connect(maint_dsn,autocommit=True) as maint:
        with pytest.raises(psycopg.Error,match="RETENTION_INTERVAL_NOT_REACHED"):
            erase(maint,TENANT_A,active,reason="EXPIRED_RETENTION")
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        assert get_count(admin,"sessions",TENANT_A,active)==1
        old_digest=uuid.uuid4().hex*2
        admin.execute("""
          INSERT INTO public.empire_analytics_sessions
          (tenant_id,property_key,session_digest,acquisition_channel,
           source_evidence_kind,policy_revision,opened_at,expires_at)
          VALUES (%s,%s,%s,'direct','server_observed_direct',%s,
                  clock_timestamp()-interval '9 days',
                  clock_timestamp()-interval '9 days'+interval '20 minutes')
        """,(TENANT_A,PROP,old_digest,POLICY))
    with psycopg.connect(maint_dsn,autocommit=True) as maint:
        assert erase(maint,TENANT_A,old_digest,reason="EXPIRED_RETENTION")[1:]==(1,0,0)
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        assert get_count(admin,"sessions",TENANT_A,old_digest)==0


@pytest.mark.parametrize("bad",[
    "PURCHASE", "UNKNOWN", "REVENUE", "", None,
])
def test_unknown_eraser_reason_denied(granted_maintenance,bad):
    admin_dsn,maint_dsn=granted_maintenance
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        session=fresh_data(admin)
    with psycopg.connect(maint_dsn,autocommit=True) as maint:
        with pytest.raises(psycopg.Error):
            erase(maint,TENANT_A,session,reason=bad)
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        assert get_count(admin,"sessions",TENANT_A,session)==1


def test_erasure_reference_cannot_retain_session_identifier(granted_maintenance):
    admin_dsn,maint_dsn=granted_maintenance
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        session=fresh_data(admin)
    with psycopg.connect(maint_dsn,autocommit=True) as maint:
        with pytest.raises(psycopg.Error,match="REFERENCE_MUST_NOT_BE_SESSION_DIGEST"):
            erase(maint,TENANT_A,session,ref=session)


def test_double_erasure_denied_without_duplicate_audit(granted_maintenance):
    admin_dsn,maint_dsn=granted_maintenance
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        session=fresh_data(admin)
    with psycopg.connect(maint_dsn,autocommit=True) as maint:
        assert erase(maint,TENANT_A,session)[1]==1
        with pytest.raises(psycopg.Error,match="SESSION_NOT_PRESENT"):
            erase(maint,TENANT_A,session)


def test_every_new_table_still_force_rls(granted_maintenance):
    admin_dsn,_=granted_maintenance
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        rows=admin.execute("""
           SELECT relname, relrowsecurity, relforcerowsecurity
           FROM pg_catalog.pg_class WHERE relname LIKE 'empire_analytics_%'
           AND relkind='r'
        """).fetchall()
        assert len(rows)==4
        assert all(row[1:] == (True,True) for row in rows)


def test_migrator_direct_update_and_delete_still_forbidden(granted_maintenance):
    admin_dsn,_=granted_maintenance
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        session=fresh_data(admin)
        admin.execute('SET ROLE empiredb_migrator')
        try:
            with pytest.raises(psycopg.Error):
                admin.execute("UPDATE public.empire_analytics_sessions SET policy_revision='hacked' WHERE session_digest=%s",(session,))
            with pytest.raises(psycopg.Error,match='APPEND_ONLY'):
                admin.execute('DELETE FROM public.empire_analytics_sessions WHERE session_digest=%s',(session,))
        finally:
            admin.execute('RESET ROLE')
        assert get_count(admin,'sessions',TENANT_A,session)==1


def test_erasure_audit_has_no_session_identity_columns(granted_maintenance):
    admin_dsn,_=granted_maintenance
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        columns={r[0] for r in admin.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='empire_analytics_erasure_audit'
        """).fetchall()}
        assert {'tenant_id','erasure_reason','events_erased','recorded_at'} <= columns
        assert not ({'session_digest','ip_address','user_agent','email','cookie','raw_url','referrer'} & columns)


def test_concurrent_erasure_can_record_only_one_receipt(granted_maintenance):
    admin_dsn,maint_dsn=granted_maintenance
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        session=fresh_data(admin)
    from concurrent.futures import ThreadPoolExecutor
    def attempt(_):
        with psycopg.connect(maint_dsn,autocommit=True) as maint:
            try:
                return erase(maint,TENANT_A,session)[1]==1
            except psycopg.Error:
                return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        result=list(pool.map(attempt,range(2)))
    assert sorted(result)==[False,True]
    with psycopg.connect(admin_dsn,autocommit=True) as admin:
        assert get_count(admin,'sessions',TENANT_A,session)==0
